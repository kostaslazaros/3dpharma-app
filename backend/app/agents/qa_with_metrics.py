#!/usr/bin/env python3
"""
Trustworthy Question Answering agent with evaluation metrics.

This module extends the base AtheroQAAgent by computing a suite of quality metrics
for every generated answer:
    1. Semantic Similarity          – cosine similarity between question and answer.
    2. Grounding Score             – average max-similarity of answer sentences vs. context sentences.
    3. Faithfulness (NLI)          – entailment probability using an NLI model.
    4. Cross-Encoder Relevance     – intent-aware relevance between question and answer.
    5. Context Precision           – proportion of retrieved docs closely aligned with the question.

Each metric guards against a different failure mode (topic drift, hallucinations,
unsupported claims, evasive answers, and noisy retrieval).
"""

from __future__ import annotations

import math
import os
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from dotenv import load_dotenv

from agents.qa_agent import AtheroQAAgent

load_dotenv()

try:
    from openai import OpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None  # type: ignore

try:
    from sentence_transformers import CrossEncoder

    CROSS_ENCODER_AVAILABLE = True
except ImportError:
    CROSS_ENCODER_AVAILABLE = False
    CrossEncoder = None  # type: ignore

try:
    from transformers import pipeline

    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    pipeline = None  # type: ignore


class TrustworthyQAAgent(AtheroQAAgent):
    """Enhanced QA agent that augments answers with trust metrics."""

    MAX_ANSWER_SENTENCES = 12
    MAX_CONTEXT_SENTENCES = 80
    MAX_CONTEXT_DOCS = 10

    METRIC_DESCRIPTIONS = {
        "semantic_similarity": "Cosine similarity between embeddings of the question and answer.",
        "grounding_score": "Average max similarity between each answer sentence and retrieved context sentences.",
        "faithfulness": "Average entailment probability (NLI) that context supports each answer sentence.",
        "cross_encoder_relevance": "Cross-encoder probability that the answer addresses the question intent.",
        "context_precision": "Share of retrieved docs whose embeddings exceed the similarity threshold.",
    }

    def __init__(
        self,
        model: str = "gpt-4o",
        embedding_model: str = "text-embedding-3-small",
        cross_encoder_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        nli_model: str = "facebook/bart-large-mnli",
        context_precision_threshold: float = 0.3,
    ) -> None:
        super().__init__(model=model)
        self.embedding_model = embedding_model
        self.cross_encoder_model = cross_encoder_model
        self.nli_model = nli_model
        self.context_precision_threshold = context_precision_threshold

        self.embedding_client = None
        if OPENAI_AVAILABLE:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                # Reuse chat client when possible to avoid redundant auth.
                self.embedding_client = self.openai_client or OpenAI(api_key=api_key)

        self._cross_encoder = None
        self._cross_encoder_error = None

        self._nli_pipeline = None
        self._nli_error = None

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------
    def answer_question_with_metrics(
        self,
        query: str,
        publications: List[Dict[str, Any]],
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """
        Run the full QA pipeline and attach trust metrics.

        Returns:
            Dictionary with answer, sources, metrics, and diagnostic notes.
        """
        relevant_papers = self.find_relevant_papers(query, publications, top_k)
        if not relevant_papers:
            return {
                "answer": "No relevant publications found in the database for this question.",
                "sources": [],
                "timestamp": None,
                "metrics": {},
                "metric_notes": ["Retrieval returned zero candidate publications."],
            }

        context = self.format_context(relevant_papers)
        generation = self.generate_answer(query, context)

        if "error" in generation:
            generation.setdefault("sources", [])
            generation["metrics"] = {}
            generation["metric_notes"] = [
                "Skipped metric computation because answer generation failed."
            ]
            return generation

        generation["sources"] = [
            {
                "title": p.get("title", ""),
                "year": p.get("year", ""),
                "pmid": p.get("pmid", p.get("id", "")),
                "journal": p.get("journal", p.get("journal_name", "")),
                "relevance_score": p.get("relevance_score", 0),
            }
            for p in relevant_papers
        ]
        generation["num_sources"] = len(relevant_papers)

        metrics, notes = self._compute_metrics(
            query=query,
            answer=generation.get("answer", ""),
            retrieved_pubs=relevant_papers,
        )

        generation["metrics"] = metrics
        generation["metric_notes"] = notes
        generation["metrics_description"] = self.METRIC_DESCRIPTIONS
        return generation

    # -------------------------------------------------------------------------
    # Metric computation
    # -------------------------------------------------------------------------
    def _compute_metrics(
        self,
        query: str,
        answer: str,
        retrieved_pubs: Sequence[Dict[str, Any]],
    ) -> Tuple[Dict[str, Optional[float]], List[str]]:
        metrics: Dict[str, Optional[float]] = {}
        notes: List[str] = []

        if not answer.strip():
            notes.append("Answer text is empty; metrics are unavailable.")
            return metrics, notes

        # Metric 1: Semantic Similarity
        sem_sim, warn = self._compute_semantic_similarity(query, answer)
        metrics["semantic_similarity"] = sem_sim
        if warn:
            notes.append(f"Semantic Similarity: {warn}")

        # Collect sentences/context once for downstream metrics.
        answer_sentences = self._split_sentences(answer)[: self.MAX_ANSWER_SENTENCES]
        context_sentences = self._collect_context_sentences(retrieved_pubs)
        if not context_sentences:
            context_sentences = []
        context_sentences = context_sentences[: self.MAX_CONTEXT_SENTENCES]

        # Metric 2: Grounding Score
        grounding, warn = self._compute_grounding_score(
            answer_sentences, context_sentences
        )
        metrics["grounding_score"] = grounding
        if warn:
            notes.append(f"Grounding Score: {warn}")

        # Metric 3: Faithfulness (NLI)
        faithfulness, warn = self._compute_faithfulness(
            answer_sentences, context_sentences
        )
        metrics["faithfulness"] = faithfulness
        if warn:
            notes.append(f"Faithfulness: {warn}")

        # Metric 4: Cross-Encoder Relevance
        cross_rel, warn = self._compute_cross_encoder_relevance(query, answer)
        metrics["cross_encoder_relevance"] = cross_rel
        if warn:
            notes.append(f"Cross-Encoder Relevance: {warn}")

        # Metric 5: Context Precision
        context_prec, warn = self._compute_context_precision(query, retrieved_pubs)
        metrics["context_precision"] = context_prec
        if warn:
            notes.append(f"Context Precision: {warn}")

        return metrics, notes

    def _compute_semantic_similarity(
        self,
        question: str,
        answer: str,
    ) -> Tuple[Optional[float], Optional[str]]:
        if not self.embedding_client:
            return None, "OpenAI embeddings not configured. Set OPENAI_API_KEY."

        try:
            vectors = self._embed_texts([question, answer])
        except Exception as exc:  # pragma: no cover - defensive
            return None, f"Embedding call failed: {exc}"

        if len(vectors) != 2:
            return None, "Failed to compute embeddings for question/answer."

        similarity = self._cosine_similarity(vectors[0], vectors[1])
        return similarity, None

    def _compute_grounding_score(
        self,
        answer_sentences: Sequence[str],
        context_sentences: Sequence[str],
    ) -> Tuple[Optional[float], Optional[str]]:
        if not answer_sentences:
            return None, "No answer sentences available."
        if not context_sentences:
            return None, "No context sentences from retrieved publications."
        if not self.embedding_client:
            return None, "OpenAI embeddings not configured."

        try:
            answer_vectors = self._embed_texts(list(answer_sentences))
            context_vectors = self._embed_texts(list(context_sentences))
        except Exception as exc:  # pragma: no cover - defensive
            return None, f"Embedding call failed: {exc}"

        if not answer_vectors or not context_vectors:
            return None, "Unable to compute embeddings for grounding."

        sims: List[float] = []
        for ans_vec in answer_vectors:
            max_sim = max(
                (self._cosine_similarity(ans_vec, ctx_vec) for ctx_vec in context_vectors),
                default=0.0,
            )
            sims.append(max_sim)

        if not sims:
            return None, "Similarity calculation failed."
        return float(np.mean(sims)), None

    def _compute_faithfulness(
        self,
        answer_sentences: Sequence[str],
        context_sentences: Sequence[str],
    ) -> Tuple[Optional[float], Optional[str]]:
        if not answer_sentences:
            return None, "No answer sentences to score."
        if not context_sentences:
            return None, "No context sentences to compare against."
        if not self.embedding_client:
            return None, "OpenAI embeddings not configured for context alignment."

        self._ensure_nli_pipeline()
        if not self._nli_pipeline:
            return None, self._nli_error or "NLI pipeline unavailable."

        try:
            answer_vectors = self._embed_texts(list(answer_sentences))
            context_vectors = self._embed_texts(list(context_sentences))
        except Exception as exc:
            return None, f"Embedding call failed: {exc}"

        if not answer_vectors or not context_vectors:
            return None, "Unable to compute embeddings for faithfulness."

        faith_scores: List[float] = []
        for idx, ans_vec in enumerate(answer_vectors):
            similarities = [
                self._cosine_similarity(ans_vec, ctx_vec) for ctx_vec in context_vectors
            ]
            if not similarities:
                continue
            best_idx = int(np.argmax(similarities))
            premise = context_sentences[best_idx]
            hypothesis = answer_sentences[idx]
            entail_prob = self._nli_entailment(premise, hypothesis)
            faith_scores.append(entail_prob)

        if not faith_scores:
            return None, "Could not derive entailment scores."

        return float(np.mean(faith_scores)), None

    def _compute_cross_encoder_relevance(
        self,
        question: str,
        answer: str,
    ) -> Tuple[Optional[float], Optional[str]]:
        self._ensure_cross_encoder()
        if not self._cross_encoder:
            return None, self._cross_encoder_error or "Cross-encoder unavailable."

        try:
            score = self._cross_encoder.predict([(question, answer)])[0]
        except Exception as exc:  # pragma: no cover - defensive
            return None, f"Cross-encoder inference failed: {exc}"

        return self._sigmoid(score), None

    def _compute_context_precision(
        self,
        question: str,
        retrieved_pubs: Sequence[Dict[str, Any]],
    ) -> Tuple[Optional[float], Optional[str]]:
        if not retrieved_pubs:
            return None, "No retrieved publications."
        if not self.embedding_client:
            return None, "OpenAI embeddings not configured."

        limited_docs = list(retrieved_pubs)[: self.MAX_CONTEXT_DOCS]
        doc_texts = [self._concat_publication_text(pub) for pub in limited_docs]
        doc_texts = [text for text in doc_texts if text.strip()]
        if not doc_texts:
            return None, "Retrieved documents lack textual content."

        try:
            question_vec = self._embed_texts([question])[0]
            doc_vectors = self._embed_texts(doc_texts)
        except Exception as exc:
            return None, f"Embedding call failed: {exc}"

        if not doc_vectors:
            return None, "Unable to compute document embeddings."

        sims = [self._cosine_similarity(question_vec, doc_vec) for doc_vec in doc_vectors]
        if not sims:
            return None, "No similarity scores computed."

        hits = sum(sim >= self.context_precision_threshold for sim in sims)
        precision = hits / len(sims)
        return float(precision), None

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def _split_sentences(self, text: str) -> List[str]:
        if not text:
            return []
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        return [s.strip() for s in sentences if s.strip()]

    def _collect_context_sentences(
        self,
        publications: Sequence[Dict[str, Any]],
    ) -> List[str]:
        sentences: List[str] = []
        for pub in publications:
            if len(sentences) >= self.MAX_CONTEXT_SENTENCES:
                break
            title = pub.get("title") or ""
            abstract = pub.get("abstract") or ""
            if title:
                sentences.extend(self._split_sentences(title))
            if abstract:
                sentences.extend(self._split_sentences(abstract))
            if len(sentences) >= self.MAX_CONTEXT_SENTENCES:
                break
        return sentences

    def _concat_publication_text(self, publication: Dict[str, Any]) -> str:
        title = publication.get("title") or ""
        abstract = publication.get("abstract") or ""
        journal = publication.get("journal", publication.get("journal_name", "")) or ""
        return " ".join(part for part in [title, journal, abstract] if part).strip()

    def _embed_texts(self, texts: Sequence[str]) -> List[np.ndarray]:
        if not texts:
            return []
        if not self.embedding_client:
            raise RuntimeError("Embedding client unavailable.")

        vectors: List[np.ndarray] = []
        batch_size = 16
        for start in range(0, len(texts), batch_size):
            batch = list(texts)[start : start + batch_size]
            response = self.embedding_client.embeddings.create(
                model=self.embedding_model,
                input=batch,
            )
            for item in sorted(response.data, key=lambda d: d.index):
                vectors.append(np.asarray(item.embedding, dtype=np.float32))
        return vectors

    def _cosine_similarity(self, vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        denom = float(np.linalg.norm(vec_a) * np.linalg.norm(vec_b))
        if denom == 0:
            return 0.0
        return float(np.dot(vec_a, vec_b) / denom)

    def _sigmoid(self, value: float) -> float:
        return 1.0 / (1.0 + math.exp(-value))

    def _ensure_cross_encoder(self) -> None:
        if self._cross_encoder or self._cross_encoder_error:
            return
        if not CROSS_ENCODER_AVAILABLE:
            self._cross_encoder_error = (
                "sentence-transformers is not installed. "
                "Install with `pip install sentence-transformers`."
            )
            return
        try:
            self._cross_encoder = CrossEncoder(self.cross_encoder_model, max_length=512)
        except Exception as exc:  # pragma: no cover - model download errors
            self._cross_encoder_error = (
                f"Failed to load cross-encoder '{self.cross_encoder_model}': {exc}"
            )

    def _ensure_nli_pipeline(self) -> None:
        if self._nli_pipeline or self._nli_error:
            return
        if not TRANSFORMERS_AVAILABLE:
            self._nli_error = (
                "transformers is not installed. Install with `pip install transformers`."
            )
            return
        try:
            self._nli_pipeline = pipeline(
                "text-classification",
                model=self.nli_model,
                tokenizer=self.nli_model,
                return_all_scores=True,
                truncation=True,
            )
        except Exception as exc:  # pragma: no cover
            self._nli_error = f"Failed to load NLI model '{self.nli_model}': {exc}"

    def _nli_entailment(self, premise: str, hypothesis: str) -> float:
        if not self._nli_pipeline:
            return 0.0
        outputs = self._nli_pipeline(
            {"text": premise, "text_pair": hypothesis},
        )
        if not outputs:
            return 0.0
        entail_score = 0.0
        for item in outputs:
            label = item.get("label", "").upper()
            score = float(item.get("score", 0.0))
            if "ENTAIL" in label:
                entail_score = score
                break
        return entail_score


