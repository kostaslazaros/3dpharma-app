#!/usr/bin/env python3
"""
Literature Review Agent for Atherosclerosis Research
Performs systematic literature analysis across publications to identify
key findings, research gaps, and emerging trends.
"""

import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import Counter, defaultdict
from dotenv import load_dotenv

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


class LiteratureReviewAgent:
    """Agent for systematic literature review and analysis"""
    
    def __init__(self, model: str = "gpt-4o"):
        """
        Initialize Literature Review Agent
        
        Args:
            model: LLM model to use ('gpt-4o', 'claude-sonnet-4', etc.)
        """
        self.model = model
        self.openai_client = None
        self.anthropic_client = None
        
        if "gpt" in model.lower() and OPENAI_AVAILABLE:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self.openai_client = OpenAI(api_key=api_key)
        
        if "claude" in model.lower() and ANTHROPIC_AVAILABLE:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                self.anthropic_client = Anthropic(api_key=api_key)
    
    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Call the LLM with the given prompts"""
        if self.openai_client:
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=4000
            )
            return response.choices[0].message.content
        
        elif self.anthropic_client:
            response = self.anthropic_client.messages.create(
                model=self.model,
                max_tokens=4000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            return response.content[0].text
        
        return "Error: No LLM client available. Please configure OPENAI_API_KEY or ANTHROPIC_API_KEY."
    
    def extract_statistics(self, publications: List[Dict]) -> Dict[str, Any]:
        """Extract statistical overview from publications"""
        if not publications:
            return {}
        
        years = [p.get('year') for p in publications if p.get('year')]
        journals = [p.get('journal', p.get('journal_name', '')) for p in publications]
        
        all_lipoproteins = []
        all_biomarkers = []
        all_genes = []
        all_drugs = []
        all_risk_factors = []
        all_comorbidities = []
        all_pathophysiology = []
        all_clinical_outcomes = []
        all_therapeutic_interventions = []
        
        for pub in publications:
            all_lipoproteins.extend(pub.get('extracted_lipoproteins', []))
            all_biomarkers.extend(pub.get('extracted_biomarkers', []))
            all_genes.extend(pub.get('extracted_genes', []))
            all_drugs.extend(pub.get('extracted_drugs', []))
            all_risk_factors.extend(pub.get('extracted_risk_factors', []))
            all_comorbidities.extend(pub.get('extracted_comorbidities', []))
            all_pathophysiology.extend(pub.get('extracted_pathophysiology', []))
            all_clinical_outcomes.extend(pub.get('extracted_clinical_outcomes', []))
            all_therapeutic_interventions.extend(pub.get('extracted_therapeutic_interventions', []))
        
        return {
            "total_papers": len(publications),
            "year_range": f"{min(years) if years else 'N/A'} - {max(years) if years else 'N/A'}",
            "year_distribution": dict(Counter(years).most_common(10)),
            "top_journals": dict(Counter(j for j in journals if j).most_common(10)),
            "entity_counts": {
                "lipoproteins": len(set(all_lipoproteins)),
                "biomarkers": len(set(all_biomarkers)),
                "genes": len(set(all_genes)),
                "drugs": len(set(all_drugs)),
                "risk_factors": len(set(all_risk_factors)),
                "comorbidities": len(set(all_comorbidities)),
            },
            "top_entities": {
                "lipoproteins": dict(Counter(all_lipoproteins).most_common(10)),
                "biomarkers": dict(Counter(all_biomarkers).most_common(10)),
                "genes": dict(Counter(all_genes).most_common(10)),
                "drugs": dict(Counter(all_drugs).most_common(10)),
                "risk_factors": dict(Counter(all_risk_factors).most_common(10)),
                "comorbidities": dict(Counter(all_comorbidities).most_common(10)),
                "pathophysiology": dict(Counter(all_pathophysiology).most_common(10)),
                "clinical_outcomes": dict(Counter(all_clinical_outcomes).most_common(10)),
                "therapeutic_interventions": dict(Counter(all_therapeutic_interventions).most_common(10)),
            }
        }
    
    def filter_publications_by_topic(self, publications: List[Dict], topic: str) -> List[Dict]:
        """Filter publications relevant to a specific topic"""
        topic_lower = topic.lower()
        keywords = topic_lower.split()
        
        relevant = []
        for pub in publications:
            title = (pub.get('title') or '').lower()
            abstract = (pub.get('abstract') or '').lower()
            text = f"{title} {abstract}"
            
            # Check for keyword matches
            matches = sum(1 for kw in keywords if kw in text)
            if matches >= len(keywords) * 0.5:  # At least 50% of keywords match
                relevant.append(pub)
        
        return relevant
    
    def perform_literature_review(
        self,
        publications: List[Dict],
        topic: str,
        review_type: str = "comprehensive",
        max_papers: int = 50
    ) -> Dict[str, Any]:
        """
        Perform a systematic literature review on a topic
        
        Args:
            publications: List of publications to analyze
            topic: Research topic to focus on
            review_type: Type of review ('comprehensive', 'therapeutic', 'mechanistic', 'clinical')
            max_papers: Maximum papers to include in analysis
        
        Returns:
            Literature review results
        """
        # Filter relevant publications
        relevant_pubs = self.filter_publications_by_topic(publications, topic)[:max_papers]
        
        if not relevant_pubs:
            return {
                "error": f"No publications found relevant to topic: {topic}",
                "topic": topic,
                "timestamp": datetime.now().isoformat()
            }
        
        # Get statistics
        stats = self.extract_statistics(relevant_pubs)
        
        # Format publications for LLM
        pubs_text = self._format_publications_for_review(relevant_pubs[:30])
        
        system_prompt = self._get_review_system_prompt(review_type)
        
        user_prompt = f"""
Perform a systematic literature review on the following topic:
**Topic:** {topic}

**Review Type:** {review_type}

**Statistics:**
- Total relevant papers: {stats.get('total_papers', 0)}
- Year range: {stats.get('year_range', 'N/A')}
- Top lipoproteins mentioned: {list(stats.get('top_entities', {}).get('lipoproteins', {}).keys())[:5]}
- Top biomarkers mentioned: {list(stats.get('top_entities', {}).get('biomarkers', {}).keys())[:5]}
- Top drugs mentioned: {list(stats.get('top_entities', {}).get('drugs', {}).keys())[:5]}
- Top genes mentioned: {list(stats.get('top_entities', {}).get('genes', {}).keys())[:5]}

**Publications for Review:**
{pubs_text}

Please provide a comprehensive literature review with:
1. **Executive Summary** - Key findings in 2-3 paragraphs
2. **Research Trends** - How has research evolved over time
3. **Key Findings** - Major discoveries and their implications
4. **Therapeutic Landscape** - Current and emerging treatments
5. **Research Gaps** - Areas needing more investigation
6. **Future Directions** - Promising areas for future research
7. **Clinical Implications** - Relevance to clinical practice

Include specific references to papers using [PMID:xxxxx] format.
"""
        
        review_text = self._call_llm(system_prompt, user_prompt)
        
        return {
            "topic": topic,
            "review_type": review_type,
            "statistics": stats,
            "review": review_text,
            "papers_analyzed": len(relevant_pubs),
            "paper_ids": [p.get('pmid', p.get('id', '')) for p in relevant_pubs],
            "timestamp": datetime.now().isoformat()
        }
    
    def identify_research_gaps(self, publications: List[Dict], domain: str = "general") -> Dict[str, Any]:
        """
        Identify research gaps and opportunities in the literature
        
        Args:
            publications: List of publications to analyze
            domain: Specific domain to focus on
        
        Returns:
            Research gaps analysis
        """
        stats = self.extract_statistics(publications)
        
        # Sample recent publications for analysis
        recent_pubs = sorted(
            [p for p in publications if p.get('year')],
            key=lambda x: x.get('year', 0),
            reverse=True
        )[:30]
        
        pubs_text = self._format_publications_for_review(recent_pubs)
        
        system_prompt = """You are a research analyst specializing in atherosclerosis and cardiovascular research.
Your task is to identify research gaps, understudied areas, and opportunities for future investigation.
Focus on actionable insights that could guide new research directions."""
        
        user_prompt = f"""
Analyze the following recent atherosclerosis research publications to identify research gaps.

**Domain focus:** {domain}

**Current landscape statistics:**
- Total papers: {stats.get('total_papers', 0)}
- Most studied lipoproteins: {list(stats.get('top_entities', {}).get('lipoproteins', {}).keys())[:5]}
- Most studied biomarkers: {list(stats.get('top_entities', {}).get('biomarkers', {}).keys())[:5]}
- Most studied drugs: {list(stats.get('top_entities', {}).get('drugs', {}).keys())[:5]}
- Most studied genes: {list(stats.get('top_entities', {}).get('genes', {}).keys())[:5]}

**Recent Publications:**
{pubs_text}

Please identify:

1. **Understudied Areas** - Topics/entities that deserve more attention
2. **Methodological Gaps** - Missing approaches or study types
3. **Population Gaps** - Underrepresented patient groups
4. **Translational Gaps** - Disconnect between basic and clinical research
5. **Therapeutic Gaps** - Unmet medical needs
6. **Emerging Opportunities** - New directions suggested by recent findings

For each gap, explain:
- Why it matters
- Current state of knowledge
- Suggested research approaches
"""
        
        analysis = self._call_llm(system_prompt, user_prompt)
        
        return {
            "domain": domain,
            "analysis": analysis,
            "statistics": stats,
            "papers_analyzed": len(recent_pubs),
            "timestamp": datetime.now().isoformat()
        }
    
    def compare_treatment_approaches(
        self,
        publications: List[Dict],
        treatment1: str,
        treatment2: str
    ) -> Dict[str, Any]:
        """
        Compare two treatment approaches based on literature
        
        Args:
            publications: List of publications
            treatment1: First treatment to compare
            treatment2: Second treatment to compare
        
        Returns:
            Comparative analysis
        """
        # Filter publications for each treatment
        pubs1 = self.filter_publications_by_topic(publications, treatment1)[:25]
        pubs2 = self.filter_publications_by_topic(publications, treatment2)[:25]
        
        if not pubs1 and not pubs2:
            return {
                "error": f"No publications found for either {treatment1} or {treatment2}",
                "timestamp": datetime.now().isoformat()
            }
        
        system_prompt = """You are a clinical research analyst comparing treatment approaches for atherosclerosis.
Provide an objective, evidence-based comparison including efficacy, safety, and practical considerations."""
        
        pubs1_text = self._format_publications_for_review(pubs1[:15])
        pubs2_text = self._format_publications_for_review(pubs2[:15])
        
        user_prompt = f"""
Compare the following two treatment approaches for atherosclerosis based on the literature:

**Treatment 1: {treatment1}**
Papers found: {len(pubs1)}
{pubs1_text}

**Treatment 2: {treatment2}**
Papers found: {len(pubs2)}
{pubs2_text}

Please provide a comprehensive comparison including:

1. **Mechanism of Action** - How each treatment works
2. **Efficacy Evidence** - Clinical outcomes data
3. **Safety Profile** - Adverse effects and tolerability
4. **Patient Selection** - Who benefits most from each
5. **Cost-Effectiveness** - Economic considerations
6. **Combination Potential** - Can they be used together
7. **Research Maturity** - How well-studied is each approach
8. **Clinical Recommendations** - When to prefer one over the other

Include specific references using [PMID:xxxxx] format.
"""
        
        comparison = self._call_llm(system_prompt, user_prompt)
        
        return {
            "treatment1": treatment1,
            "treatment2": treatment2,
            "treatment1_papers": len(pubs1),
            "treatment2_papers": len(pubs2),
            "comparison": comparison,
            "timestamp": datetime.now().isoformat()
        }
    
    def _format_publications_for_review(self, publications: List[Dict]) -> str:
        """Format publications for review prompt"""
        parts = []
        for i, pub in enumerate(publications, 1):
            title = pub.get('title', 'No title')
            abstract = (pub.get('abstract') or '')[:500]
            year = pub.get('year', 'Unknown')
            pmid = pub.get('pmid', pub.get('id', 'Unknown'))
            journal = pub.get('journal', pub.get('journal_name', ''))
            
            # Extract key entities
            entities = []
            if pub.get('extracted_lipoproteins'):
                entities.append(f"Lipoproteins: {', '.join(pub['extracted_lipoproteins'][:5])}")
            if pub.get('extracted_drugs'):
                entities.append(f"Drugs: {', '.join(pub['extracted_drugs'][:5])}")
            if pub.get('extracted_biomarkers'):
                entities.append(f"Biomarkers: {', '.join(pub['extracted_biomarkers'][:3])}")
            
            entities_str = f"\nEntities: {' | '.join(entities)}" if entities else ""
            
            parts.append(
                f"\n[{i}] **{title}**\n"
                f"Year: {year} | Journal: {journal} | PMID: {pmid}{entities_str}\n"
                f"Abstract: {abstract}...\n"
            )
        
        return "\n".join(parts)
    
    def _get_review_system_prompt(self, review_type: str) -> str:
        """Get system prompt based on review type"""
        base = """You are an expert systematic reviewer specializing in atherosclerosis and cardiovascular research.
You provide evidence-based, well-structured literature reviews with proper citations."""
        
        type_specific = {
            "comprehensive": """
Focus on providing a complete overview of the research landscape including:
- Basic science findings
- Clinical evidence
- Therapeutic developments
- Future directions""",
            "therapeutic": """
Focus on therapeutic aspects including:
- Drug mechanisms and targets
- Clinical trial evidence
- Comparative effectiveness
- Treatment guidelines
- Emerging therapies""",
            "mechanistic": """
Focus on biological mechanisms including:
- Pathophysiology
- Molecular pathways
- Cellular processes
- Genetic factors
- Biomarker relationships""",
            "clinical": """
Focus on clinical aspects including:
- Diagnostic approaches
- Risk stratification
- Treatment outcomes
- Patient management
- Guidelines and recommendations"""
        }
        
        return base + type_specific.get(review_type, type_specific["comprehensive"])
