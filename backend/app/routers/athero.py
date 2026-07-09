"""Atherosclerosis AI Agent API routes"""
import os
import json
from typing import List, Dict, Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/athero", tags=["athero"])

# Load athero data on module import
ATHERO_DATA: List[Dict] = []

def find_athero_data_path():
    """Find the athero data file in various possible locations"""
    possible_paths = [
        # Relative to this file
        Path(__file__).parent.parent.parent.parent / "drug-app" / "athero_nlp_with_relationships.json",
        Path(__file__).parent.parent.parent.parent.parent / "drug-app" / "athero_nlp_with_relationships.json",
        # From backend folder
        Path(__file__).parent.parent.parent / ".." / "drug-app" / "athero_nlp_with_relationships.json",
        # Absolute path as fallback
        Path("C:/Users/cbour/Downloads/chrysaDrugs/drug-app/athero_nlp_with_relationships.json"),
    ]
    
    for p in possible_paths:
        resolved = p.resolve()
        print(f"Checking path: {resolved}")
        if resolved.exists():
            print(f"Found athero data at: {resolved}")
            return resolved
    
    print("Athero data file not found in any location")
    return None

ATHERO_DATA_PATH = find_athero_data_path()


def load_athero_data():
    """Load atherosclerosis research data"""
    global ATHERO_DATA
    if ATHERO_DATA:
        return ATHERO_DATA
    
    if ATHERO_DATA_PATH is None:
        print("Athero data file not found in any expected location")
        return ATHERO_DATA
    
    try:
        with open(ATHERO_DATA_PATH, 'r', encoding='utf-8') as f:
            ATHERO_DATA = json.load(f)
        print(f"Loaded {len(ATHERO_DATA)} atherosclerosis papers from {ATHERO_DATA_PATH}")
    except Exception as e:
        print(f"Error loading athero data: {e}")
    
    return ATHERO_DATA


class AtheroQueryRequest(BaseModel):
    query: str
    num_sources: int = 5


class AtheroQueryResponse(BaseModel):
    answer: str
    sources: List[Dict]
    error: Optional[str] = None


def search_relevant_papers(query: str, papers: List[Dict], top_k: int = 5) -> List[Dict]:
    """Simple keyword-based search for relevant papers"""
    query_lower = query.lower()
    keywords = query_lower.split()
    
    scored_papers = []
    for paper in papers:
        score = 0
        title = (paper.get('title') or '').lower()
        abstract = (paper.get('abstract') or '').lower()
        text = f"{title} {abstract}"
        
        # Score based on keyword matches
        for kw in keywords:
            if len(kw) > 2:
                if kw in title:
                    score += 3
                if kw in abstract:
                    score += 1
        
        # Boost for entity matches
        entities = []
        entities.extend(paper.get('extracted_lipoproteins', []))
        entities.extend(paper.get('extracted_biomarkers', []))
        entities.extend([d.get('name', '') for d in paper.get('extracted_drugs', [])])
        entities.extend(paper.get('extracted_genes', []))
        entities.extend(paper.get('extracted_risk_factors', []))
        
        for entity in entities:
            if isinstance(entity, str) and entity.lower() in query_lower:
                score += 5
        
        if score > 0:
            scored_papers.append((score, paper))
    
    # Sort by score and return top_k
    scored_papers.sort(key=lambda x: x[0], reverse=True)
    return [p[1] for p in scored_papers[:top_k]]


def format_papers_for_context(papers: List[Dict]) -> str:
    """Format papers for LLM context"""
    context_parts = []
    for i, paper in enumerate(papers, 1):
        title = paper.get('title', 'No title')
        abstract = (paper.get('abstract') or '')[:800]
        year = paper.get('publication_date', '')[:4] if paper.get('publication_date') else 'Unknown'
        pmid = paper.get('pmid', 'Unknown')
        journal = paper.get('journal', 'Unknown journal')
        
        # Extract key entities
        lipoproteins = paper.get('extracted_lipoproteins', [])
        biomarkers = paper.get('extracted_biomarkers', [])
        drugs = [d.get('name', '') for d in paper.get('extracted_drugs', [])]
        risk_factors = paper.get('extracted_risk_factors', [])
        correlations = paper.get('extracted_correlations', [])
        
        entities_str = ""
        if lipoproteins:
            entities_str += f"\n  Lipoproteins: {', '.join(lipoproteins[:5])}"
        if biomarkers:
            entities_str += f"\n  Biomarkers: {', '.join(biomarkers[:5])}"
        if drugs:
            entities_str += f"\n  Drugs: {', '.join(drugs[:5])}"
        if risk_factors:
            entities_str += f"\n  Risk Factors: {', '.join(risk_factors[:5])}"
        if correlations:
            entities_str += f"\n  Key Findings: {'; '.join(correlations[:3])}"
        
        context_parts.append(
            f"\n[{i}] {title}\n"
            f"Year: {year} | Journal: {journal} | PMID: {pmid}{entities_str}\n"
            f"Abstract: {abstract}...\n"
        )
    
    return "\n".join(context_parts)


@router.post("/query", response_model=AtheroQueryResponse)
async def query_athero_literature(request: AtheroQueryRequest):
    """Query atherosclerosis literature using AI"""
    
    # Check for API key
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return AtheroQueryResponse(
            answer="OpenAI API key not configured. Please set OPENAI_API_KEY in your .env file.",
            sources=[],
            error="API key not configured"
        )
    
    # Load data
    papers = load_athero_data()
    if not papers:
        return AtheroQueryResponse(
            answer="Atherosclerosis research database not loaded.",
            sources=[],
            error="Database not available"
        )
    
    # Find relevant papers
    relevant_papers = search_relevant_papers(request.query, papers, request.num_sources)
    
    if not relevant_papers:
        return AtheroQueryResponse(
            answer="No relevant papers found for your query. Try different keywords related to atherosclerosis, lipoproteins, cardiovascular disease, or specific treatments.",
            sources=[],
            error=None
        )
    
    # Format context
    context = format_papers_for_context(relevant_papers)
    
    # Build prompt
    system_prompt = """You are an expert research assistant specializing in atherosclerosis and cardiovascular research.
Answer questions based on the provided research papers. Be specific and cite sources using [PMID:xxxxx] format.
Focus on scientific accuracy and provide evidence-based responses.
If the papers don't contain enough information to fully answer the question, say so clearly."""

    user_prompt = f"""Based on the following atherosclerosis research papers, please answer this question:

**Question:** {request.query}

**Research Papers:**
{context}

Please provide a comprehensive answer with citations to specific papers using [PMID:xxxxx] format."""

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        
        answer = response.choices[0].message.content
        
        # Format sources for response
        sources = []
        for paper in relevant_papers:
            sources.append({
                "title": paper.get('title', 'Unknown'),
                "pmid": paper.get('pmid', 'Unknown'),
                "year": paper.get('publication_date', '')[:4] if paper.get('publication_date') else 'Unknown',
                "journal": paper.get('journal', 'Unknown'),
                "lipoproteins": paper.get('extracted_lipoproteins', [])[:5],
                "drugs": [d.get('name', '') for d in paper.get('extracted_drugs', [])][:5],
                "correlations": paper.get('extracted_correlations', [])[:3]
            })
        
        return AtheroQueryResponse(
            answer=answer,
            sources=sources,
            error=None
        )
        
    except Exception as e:
        return AtheroQueryResponse(
            answer=f"Error querying AI: {str(e)}",
            sources=[],
            error=str(e)
        )


@router.get("/stats")
async def get_athero_stats():
    """Get statistics about the atherosclerosis database"""
    papers = load_athero_data()
    
    if not papers:
        return {"error": "Database not loaded", "total_papers": 0}
    
    # Collect stats
    all_lipoproteins = []
    all_biomarkers = []
    all_drugs = []
    all_genes = []
    all_risk_factors = []
    years = []
    
    for paper in papers:
        all_lipoproteins.extend(paper.get('extracted_lipoproteins', []))
        all_biomarkers.extend(paper.get('extracted_biomarkers', []))
        all_drugs.extend([d.get('name', '') for d in paper.get('extracted_drugs', [])])
        all_genes.extend(paper.get('extracted_genes', []))
        all_risk_factors.extend(paper.get('extracted_risk_factors', []))
        
        pub_date = paper.get('publication_date', '')
        if pub_date:
            years.append(pub_date[:4])
    
    from collections import Counter
    
    return {
        "total_papers": len(papers),
        "year_range": f"{min(years) if years else 'N/A'} - {max(years) if years else 'N/A'}",
        "top_lipoproteins": dict(Counter(all_lipoproteins).most_common(10)),
        "top_biomarkers": dict(Counter(all_biomarkers).most_common(10)),
        "top_drugs": dict(Counter(all_drugs).most_common(10)),
        "top_genes": dict(Counter(all_genes).most_common(10)),
        "top_risk_factors": dict(Counter(all_risk_factors).most_common(10))
    }
