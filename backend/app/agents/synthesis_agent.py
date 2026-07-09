#!/usr/bin/env python3
"""
Research Synthesis Agent for Atherosclerosis Research
Synthesizes insights across multiple publications to identify trends
"""

import os
from typing import List, Dict, Any
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


class ResearchSynthesisAgent:
    """Agent for synthesizing research across multiple publications"""
    
    def __init__(self, model: str = "gpt-4o"):
        """
        Initialize Synthesis Agent
        
        Args:
            model: LLM model to use
        """
        self.model = model
        self.openai_client = None
        self.anthropic_client = None
        
        # Initialize clients
        if "gpt" in model.lower() and OPENAI_AVAILABLE:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self.openai_client = OpenAI(api_key=api_key)
        
        if "claude" in model.lower() and ANTHROPIC_AVAILABLE:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                self.anthropic_client = Anthropic(api_key=api_key)
    
    def format_publications_summary(self, publications: List[Dict]) -> str:
        """Format publications for synthesis"""
        summary_parts = []
        for i, pub in enumerate(publications, 1):
            title = pub.get('title', 'No title')
            abstract = (pub.get('abstract') or '')[:400]  # Limit length
            year = pub.get('year', 'Unknown')
            pmid = pub.get('pmid', pub.get('id', 'Unknown'))
            
            # Add extracted entities summary
            entities = []
            if pub.get('extracted_lipoproteins'):
                entities.append(f"Lipoproteins: {len(pub.get('extracted_lipoproteins', []))}")
            if pub.get('extracted_biomarkers'):
                entities.append(f"Biomarkers: {len(pub.get('extracted_biomarkers', []))}")
            if pub.get('extracted_genes'):
                entities.append(f"Genes: {len(pub.get('extracted_genes', []))}")
            if pub.get('extracted_drugs'):
                entities.append(f"Drugs: {len(pub.get('extracted_drugs', []))}")
            
            entities_str = f" | Entities: {', '.join(entities)}" if entities else ""
            
            summary_parts.append(
                f"\n[{i}] {title}\n"
                f"Year: {year} | PMID: {pmid}{entities_str}\n"
                f"Abstract: {abstract}...\n"
            )
        
        return "\n".join(summary_parts)
    
    def synthesize_research(self, publications: List[Dict], focus: str = "general") -> Dict[str, Any]:
        """
        Synthesize insights from multiple publications
        
        Args:
            publications: List of publications to synthesize
            focus: Focus area ('general', 'trends', 'mechanisms', 'clinical', 'therapeutics')
        
        Returns:
            Synthesis results
        """
        if not publications:
            return {
                "error": "No publications provided for synthesis",
                "timestamp": datetime.now().isoformat()
            }
        
        # Format publications
        pub_summary = self.format_publications_summary(publications)
        
        # Determine focus-specific prompt
        if focus == "trends":
            prompt_section = """
Please identify:
1. **Emerging Trends**: What are the new research directions in atherosclerosis?
2. **Evolving Themes**: How has the research focus changed over time?
3. **Key Discoveries**: What are the major recent findings?
4. **Research Gaps**: What areas need more investigation?
"""
        elif focus == "mechanisms":
            prompt_section = """
Please identify:
1. **Common Mechanisms**: What pathophysiological mechanisms are frequently described?
2. **Pathway Interactions**: How do lipoproteins, inflammation, and other factors interact?
3. **Key Genes & Proteins**: What are the most studied genes and proteins?
4. **Regulatory Networks**: What regulatory networks emerge in atherosclerosis?
"""
        elif focus == "clinical":
            prompt_section = """
Please identify:
1. **Clinical Applications**: What are the clinical implications?
2. **Therapeutic Targets**: What are potential therapeutic targets?
3. **Biomarkers**: What biomarkers are identified for diagnosis or prognosis?
4. **Treatment Strategies**: What treatment approaches are discussed?
"""
        elif focus == "therapeutics":
            prompt_section = """
Please identify:
1. **Drug Targets**: What are the main drug targets being investigated?
2. **Therapeutic Interventions**: What drugs and interventions show promise?
3. **Mechanisms of Action**: How do these therapeutics work?
4. **Clinical Outcomes**: What clinical outcomes are reported?
"""
        else:  # general
            prompt_section = """
Please provide:
1. **Main Themes**: What are the overarching research themes in atherosclerosis?
2. **Key Findings**: What are the most important discoveries?
3. **Research Focus**: What aspects of atherosclerosis research are emphasized?
4. **Significance**: What is the overall significance of this research?
"""
        
        prompt = f"""You are a research synthesis specialist analyzing atherosclerosis and cardiovascular disease research publications.

Analyze the following {len(publications)} publications and provide a comprehensive synthesis:

{pub_summary}

{prompt_section}

5. **Publication Overview**: Provide a brief summary of what these {len(publications)} publications are about
6. **Consensus Findings**: What findings are consistent across multiple papers?
7. **Contradictions**: Are there any conflicting findings or debates?
8. **Future Directions**: What are the suggested future research directions?

Format your response as a structured synthesis report focusing on atherosclerosis, cardiovascular disease, lipoproteins, biomarkers, and therapeutic interventions."""

        try:
            if self.openai_client and "gpt" in self.model.lower():
                response = self.openai_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a research synthesis specialist in atherosclerosis and cardiovascular disease research."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=2500
                )
                synthesis = response.choices[0].message.content
            
            elif self.anthropic_client and "claude" in self.model.lower():
                response = self.anthropic_client.messages.create(
                    model=self.model,
                    max_tokens=2500,
                    temperature=0.3,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                synthesis = response.content[0].text
            
            else:
                synthesis = "LLM API not available. Please configure API keys in .env file."
            
            return {
                "synthesis": synthesis,
                "num_publications": len(publications),
                "focus": focus,
                "timestamp": datetime.now().isoformat(),
                "model": self.model
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "num_publications": len(publications),
                "timestamp": datetime.now().isoformat()
            }
    
    def synthesize_recent_research(self, all_publications: List[Dict], num_papers: int = 10, 
                                    focus: str = "general") -> Dict[str, Any]:
        """
        Synthesize the most recent N publications
        
        Args:
            all_publications: All available publications
            num_papers: Number of recent papers to analyze
            focus: Focus area for synthesis
        """
        # Get recent publications (exclude 2026)
        recent_pubs = sorted(
            [p for p in all_publications if p.get('year') and p.get('year') != 2026],
            key=lambda x: int(x.get('year', 0)),
            reverse=True
        )[:num_papers]
        
        return self.synthesize_research(recent_pubs, focus)

