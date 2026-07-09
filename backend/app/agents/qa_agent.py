#!/usr/bin/env python3
"""
Q&A Agent for Atherosclerosis Research
Answers questions using the publication database with PubMed references
"""

import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class AtheroQAAgent:
    """Question-Answering agent for atherosclerosis research"""
    
    def __init__(self, model: str = "gpt-4o"):
        """
        Initialize Q&A Agent
        
        Args:
            model: LLM model to use ('gpt-4o', 'claude-sonnet-4', etc.)
        """
        self.model = model
        self.openai_client = None
        self.anthropic_client = None
        
        # Initialize clients based on model
        if "gpt" in model.lower() and OPENAI_AVAILABLE:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self.openai_client = OpenAI(api_key=api_key)
        
        if "claude" in model.lower() and ANTHROPIC_AVAILABLE:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                self.anthropic_client = Anthropic(api_key=api_key)
    
    def find_relevant_papers(self, query: str, publications: List[Dict], top_k: int = 5) -> List[Dict]:
        """
        Find relevant papers using semantic/keyword search
        
        Args:
            query: User question
            publications: List of publication dictionaries
            top_k: Number of papers to retrieve
        
        Returns:
            List of relevant publications with similarity scores
        """
        # Simple keyword-based search (can be enhanced with vector search)
        query_lower = query.lower()
        relevant = []
        
        for pub in publications:
            title = (pub.get('title') or '').lower()
            abstract = (pub.get('abstract') or '').lower()
            
            # Simple relevance scoring
            score = 0
            if query_lower in title:
                score += 10
            if query_lower in abstract:
                score += 5
            
            # Check for key terms
            query_terms = query_lower.split()
            for term in query_terms:
                if len(term) > 3:  # Skip short words
                    if term in title:
                        score += 2
                    if term in abstract:
                        score += 1
            
            if score > 0:
                pub_copy = pub.copy()
                pub_copy['relevance_score'] = score
                relevant.append(pub_copy)
        
        # Sort by relevance and return top_k
        relevant.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        return relevant[:top_k]
    
    def format_context(self, papers: List[Dict]) -> str:
        """Format papers as context for LLM"""
        context_parts = []
        for i, paper in enumerate(papers, 1):
            title = paper.get('title', 'No title')
            abstract = (paper.get('abstract') or '')[:500]  # Limit abstract length
            year = paper.get('year', 'Unknown')
            pmid = paper.get('pmid', paper.get('id', 'Unknown'))
            journal = paper.get('journal', paper.get('journal_name', ''))
            
            context_parts.append(
                f"\n[{i}] {title}\n"
                f"Year: {year} | Journal: {journal} | PMID: {pmid}\n"
                f"Abstract: {abstract}...\n"
            )
        
        return "\n".join(context_parts)
    
    def generate_answer(self, query: str, context: str) -> Dict[str, Any]:
        """
        Generate answer using LLM with context
        
        Returns:
            Dictionary with answer, sources, and metadata
        """
        prompt = f"""You are a biomedical research assistant specializing in atherosclerosis, cardiovascular disease, and lipoprotein research.

Answer the following question based on the provided research publications. Be precise, cite specific findings, and always reference the papers by their numbers.

Question: {query}

Relevant Research Publications:
{context}

Instructions:
1. Provide a clear, evidence-based answer
2. Cite specific papers using [1], [2], etc.
3. Include key findings and mechanisms when relevant
4. Mention PMIDs when available
5. Focus on atherosclerosis, cardiovascular disease, lipoproteins, biomarkers, therapeutic interventions, and related topics
6. If the answer cannot be determined from the provided papers, state that clearly

Answer:"""

        try:
            if self.openai_client and "gpt" in self.model.lower():
                response = self.openai_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a biomedical research assistant specializing in atherosclerosis and cardiovascular disease research."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=1500
                )
                answer = response.choices[0].message.content
            
            elif self.anthropic_client and "claude" in self.model.lower():
                response = self.anthropic_client.messages.create(
                    model=self.model,
                    max_tokens=1500,
                    temperature=0.3,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                answer = response.content[0].text
            
            else:
                # Fallback
                answer = "LLM API not available. Please configure API keys in .env file."
            
            return {
                "answer": answer,
                "timestamp": datetime.now().isoformat(),
                "model": self.model
            }
            
        except Exception as e:
            return {
                "answer": f"Error generating answer: {str(e)}",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def answer_question(self, query: str, publications: List[Dict], top_k: int = 5) -> Dict[str, Any]:
        """
        Complete Q&A pipeline
        
        Args:
            query: User question
            publications: All available publications
            top_k: Number of relevant papers to use
        
        Returns:
            Complete answer with sources and metadata
        """
        # Step 1: Find relevant papers
        relevant_papers = self.find_relevant_papers(query, publications, top_k)
        
        if not relevant_papers:
            return {
                "answer": "No relevant publications found in the database for this question.",
                "sources": [],
                "timestamp": datetime.now().isoformat()
            }
        
        # Step 2: Format context
        context = self.format_context(relevant_papers)
        
        # Step 3: Generate answer
        result = self.generate_answer(query, context)
        
        # Step 4: Add sources
        result["sources"] = [
            {
                "title": p.get('title', ''),
                "year": p.get('year', ''),
                "pmid": p.get('pmid', p.get('id', '')),
                "journal": p.get('journal', p.get('journal_name', '')),
                "relevance_score": p.get('relevance_score', 0)
            }
            for p in relevant_papers
        ]
        
        result["num_sources"] = len(relevant_papers)
        
        return result

