#!/usr/bin/env python3
"""
Publication Analysis Agent for Atherosclerosis Research
Analyzes individual publications to extract key insights
"""

import os
import json
from typing import Dict, Any, Optional, List
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


class PublicationAnalyzer:
    """Agent for analyzing individual publications"""
    
    def __init__(self, model: str = "gpt-4o"):
        """
        Initialize Publication Analyzer
        
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
    
    def analyze_publication(self, publication: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a single publication and extract key insights
        
        Args:
            publication: Publication dictionary
        
        Returns:
            Analysis results with key insights
        """
        title = publication.get('title', '')
        abstract = publication.get('abstract', '')
        year = publication.get('year', '')
        journal = publication.get('journal', publication.get('journal_name', ''))
        pmid = publication.get('pmid', publication.get('id', ''))
        
        # Extract key fields
        lipoproteins = publication.get('extracted_lipoproteins', [])
        biomarkers = publication.get('extracted_biomarkers', [])
        genes = publication.get('extracted_genes', [])
        drugs = publication.get('extracted_drugs', [])
        risk_factors = publication.get('extracted_risk_factors', [])
        comorbidities = publication.get('extracted_comorbidities', [])
        pathophysiology = publication.get('extracted_pathophysiology', [])
        clinical_outcomes = publication.get('extracted_clinical_outcomes', [])
        
        if not abstract:
            return {
                "error": "No abstract available for analysis",
                "publication": {
                    "title": title,
                    "pmid": pmid,
                    "year": year
                }
            }
        
        # Format extracted data
        extracted_info = []
        if lipoproteins:
            extracted_info.append(f"Lipoproteins: {', '.join(lipoproteins[:10])}")
        if biomarkers:
            extracted_info.append(f"Biomarkers: {', '.join(biomarkers[:10])}")
        if genes:
            gene_names = [g if isinstance(g, str) else g.get('name', str(g)) for g in genes[:10]]
            extracted_info.append(f"Genes: {', '.join(gene_names)}")
        if drugs:
            drug_names = [d.get('name', str(d)) if isinstance(d, dict) else str(d) for d in drugs[:10]]
            extracted_info.append(f"Drugs: {', '.join(drug_names)}")
        if risk_factors:
            extracted_info.append(f"Risk Factors: {', '.join(risk_factors[:10])}")
        if comorbidities:
            extracted_info.append(f"Comorbidities: {', '.join(comorbidities[:10])}")
        
        extracted_text = "\n".join(extracted_info) if extracted_info else "None extracted"
        
        prompt = f"""Analyze this atherosclerosis/cardiovascular disease research publication and extract key insights.

Title: {title}
Year: {year}
Journal: {journal}
PMID: {pmid}

Abstract:
{abstract}

Extracted Entities:
{extracted_text}

Please provide a structured analysis with:
1. **Main Research Question**: What is the primary research question or hypothesis?
2. **Key Findings**: What are the 3-5 most important findings?
3. **Atherosclerosis Focus**: What aspects of atherosclerosis are studied? (plaque formation, progression, regression, inflammation, etc.)
4. **Lipoproteins & Biomarkers**: What lipoproteins, biomarkers, or genes are investigated?
5. **Therapeutic Interventions**: What drugs, treatments, or interventions are discussed?
6. **Risk Factors & Comorbidities**: What risk factors or comorbidities are mentioned?
7. **Mechanisms**: What molecular or pathophysiological mechanisms are described?
8. **Clinical Significance**: What are the clinical or therapeutic implications?
9. **Methodology**: What are the main experimental approaches or study design?
10. **Limitations**: What are potential limitations mentioned or implied?

Format your response as a structured analysis with clear sections."""

        try:
            if self.openai_client and "gpt" in self.model.lower():
                response = self.openai_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a biomedical research analyst specializing in atherosclerosis and cardiovascular disease research."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=2000
                )
                analysis = response.choices[0].message.content
            
            elif self.anthropic_client and "claude" in self.model.lower():
                response = self.anthropic_client.messages.create(
                    model=self.model,
                    max_tokens=2000,
                    temperature=0.3,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                analysis = response.content[0].text
            
            else:
                analysis = "LLM API not available. Please configure API keys in .env file."
            
            return {
                "analysis": analysis,
                "publication": {
                    "title": title,
                    "year": year,
                    "journal": journal,
                    "pmid": pmid
                },
                "model": self.model
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "publication": {
                    "title": title,
                    "pmid": pmid
                }
            }
    
    def batch_analyze(self, publications: List[Dict[str, Any]], max_papers: int = 10) -> List[Dict[str, Any]]:
        """
        Analyze multiple publications
        
        Args:
            publications: List of publications
            max_papers: Maximum number of papers to analyze
        
        Returns:
            List of analysis results
        """
        results = []
        for i, pub in enumerate(publications[:max_papers]):
            result = self.analyze_publication(pub)
            result["index"] = i + 1
            results.append(result)
        return results

