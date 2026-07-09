"""AI Chat API routes"""
import os
import re
from typing import List, Dict
from fastapi import APIRouter, HTTPException

from ..models.compatibility import ChatRequest, ChatResponse
from ..services.drug_service import get_drug_service

router = APIRouter(prefix="/chat", tags=["chat"])


def process_ai_query(query: str, history: List[Dict[str, str]] = None) -> dict:
    """Process user query with AI and database"""
    service = get_drug_service()
    
    # Check for API key
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return {
            'response': "OpenAI API key not configured. Please set the OPENAI_API_KEY environment variable.",
            'sources': [],
            'drugs_mentioned': []
        }
    
    # Extract drug names from query
    drug_names = []
    query_lower = query.lower()
    
    # Common drug category mappings
    category_mappings = {
        'nsaid': ['ibuprofen', 'aspirin', 'naproxen', 'diclofenac', 'indomethacin'],
        'nsaids': ['ibuprofen', 'aspirin', 'naproxen', 'diclofenac', 'indomethacin'],
        'ace inhibitor': ['lisinopril', 'enalapril', 'captopril', 'ramipril'],
        'ace inhibitors': ['lisinopril', 'enalapril', 'captopril', 'ramipril'],
        'beta blocker': ['metoprolol', 'atenolol', 'propranolol'],
        'beta blockers': ['metoprolol', 'atenolol', 'propranolol'],
    }
    
    # Check for category mentions
    for category, drugs in category_mappings.items():
        if category in query_lower:
            for cat_drug in drugs[:2]:
                drug_names.append(cat_drug.title())
    
    # Find specific drug names in query using the service's search index
    exact_matches = []
    query_words = [w.strip('.,!?;:()[]{}') for w in query_lower.split() if w.strip('.,!?;:()[]{}')]

    # Check each word (and pairs of words) as a potential drug name
    for word in query_words:
        if len(word) < 3:
            continue
        match = service.find_drug(word)
        if match and match['name'] not in exact_matches and match['name'] not in drug_names:
            exact_matches.append(match['name'])

    # Also try two-word combinations (e.g. "metformin hydrochloride")
    for i in range(len(query_words) - 1):
        phrase = f"{query_words[i]} {query_words[i+1]}"
        match = service.find_drug(phrase)
        if match and match['name'] not in exact_matches and match['name'] not in drug_names:
            exact_matches.append(match['name'])

    # Fall back to broader search if no exact hits found yet
    if not exact_matches and not drug_names:
        search_results = service.search_drugs(query)
        exact_matches = search_results[:3]

    drug_names = (exact_matches + drug_names)[:3]
    
    # Build context
    context = "Drug Database Information:\n"
    
    if drug_names:
        for drug_name in drug_names[:3]:
            summary = service.get_summary(drug_name)
            if 'error' not in summary:
                context += f"\n=== {drug_name} ===\n"
                context += f"- Type: {summary.get('type', 'Unknown')}\n"
                
                # Categories
                categories = summary.get('categories', [])
                if categories:
                    context += f"- Categories: {', '.join(categories[:5])}\n"
                
                context += f"- Total Interactions: {summary.get('interaction_count', 0)} known\n"
                
                # Physical properties
                properties = summary.get('properties', {})
                if properties:
                    context += f"- Physical Properties:\n"
                    for key, value in properties.items():
                        context += f"  * {key}: {value}\n"
                
                # Dosing info
                dosing = summary.get('dosing', {})
                frequency = dosing.get('frequency')
                times_per_day = dosing.get('times_per_day')
                
                if frequency or times_per_day:
                    context += f"- Dosing Frequency: {frequency or times_per_day}\n"
                
                routes = dosing.get('routes', [])
                if routes:
                    context += f"- Routes of Administration: {', '.join(str(r) for r in routes[:5])}\n"
                
                forms = summary.get('forms', [])
                if forms:
                    context += f"- Available Forms: {', '.join(forms[:5])}\n"
                
                # Food interactions
                food_interactions = summary.get('food_interactions', [])
                if food_interactions:
                    context += f"- Food Interactions:\n"
                    for fi in food_interactions[:3]:
                        context += f"  * {fi[:200]}\n"
                
                # Key drug interactions (for synopsis)
                interactions = summary.get('interactions', [])
                if interactions:
                    context += f"- Notable Drug Interactions:\n"
                    for inter in interactions[:5]:
                        drug = inter.get('drug', 'Unknown')
                        desc = inter.get('description', '')[:150]
                        severity = inter.get('severity', 'unknown')
                        context += f"  * {drug} ({severity}): {desc}\n"
    
    # Check compatibility if two drugs
    if len(drug_names) >= 2:
        result = service.check_compatibility(drug_names[0], drug_names[1])
        context += f"\n\nCompatibility Check Results for {drug_names[0]} + {drug_names[1]}:\n"
        context += f"- Compatibility Status: {'NOT COMPATIBLE' if not result.get('compatible', True) else 'Compatible'}\n"
        
        interactions = result.get('interactions', [])
        if interactions:
            context += f"- Interactions Found: {len(interactions)}\n"
            for inter in interactions[:3]:
                context += f"  * {inter.get('drug', 'Unknown')}: {inter.get('description', '')[:150]}\n"
        
        if result.get('issues'):
            for issue in result['issues'][:3]:
                context += f"- Issue: {issue}\n"
        
        if result.get('warnings'):
            for warning in result['warnings'][:3]:
                context += f"- Warning: {warning}\n"
    
    # Get alternatives if requested
    alternatives_info = ""
    if any(word in query_lower for word in ['alternative', 'substitute', 'replace', 'instead']):
        if drug_names:
            alternatives = service.get_alternatives_from_category(drug_names[0])
            if alternatives:
                alternatives_info = f"\n\nAlternatives for {drug_names[0]}: {', '.join(alternatives[:5])}\n"
    
    # Detect if user wants a drug synopsis
    is_synopsis_request = any(word in query_lower for word in ['synopsis', 'summary', 'overview', 'tell me about', 'what is', 'describe', 'information about', 'info about', 'details about'])
    
    # Build AI prompt
    if is_synopsis_request and drug_names:
        system_prompt = """You are a pharmaceutical research assistant providing comprehensive drug synopses.
When asked about a drug, provide a well-structured synopsis including:

1. **Overview**: What the drug is and its primary therapeutic use
2. **Mechanism of Action**: How the drug works at a molecular/cellular level
3. **Indications**: What conditions it treats
4. **Dosage Forms**: Available formulations (tablets, capsules, solutions, etc.)
5. **Key Physical Properties**: Relevant for pharmaceutical formulation
6. **Notable Interactions**: Major drug-drug interactions to be aware of
7. **3D Printing Considerations**: Suitability for additive manufacturing

Be concise but comprehensive. Use the database information provided and supplement with general pharmaceutical knowledge."""
    else:
        system_prompt = """You are a drug compatibility assistant for 3D PRINTING applications. 
Your focus is on 3D PRINTING COMPATIBILITY, not patient medication use. Consider:
- Physical properties (melting point, solubility, molecular weight)
- Chemical compatibility for 3D printing processes
- Routes of administration compatibility
- Dosing frequency compatibility (for timed-release formulations)
- Drug type (small molecule vs biologic - biologics cannot be 3D printed with standard methods)
- Drug-drug interactions (which may affect chemical stability in 3D printing)

IMPORTANT: Focus on 3D PRINTING compatibility, not patient safety. 
Do NOT provide medical advice - this is for 3D printing assessment only."""

    if is_synopsis_request and drug_names:
        user_prompt = f"""User Question: {query}

{context}{alternatives_info}

Please provide a comprehensive drug synopsis for the requested drug(s). Structure your response with clear sections."""
    else:
        user_prompt = f"""User Question: {query}

{context}{alternatives_info}

Please provide a comprehensive answer focused on 3D printing compatibility."""

    # Call OpenAI API
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add history if provided
        if history:
            for msg in history[-6:]:  # Last 6 messages for context
                messages.append({
                    "role": msg.get('role', 'user'),
                    "content": msg.get('content', '')
                })
        
        messages.append({"role": "user", "content": user_prompt})
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=1500,
            temperature=0.7
        )
        
        return {
            'response': response.choices[0].message.content,
            'sources': ['DrugBank Database'],
            'drugs_mentioned': drug_names
        }
    except ImportError:
        return {
            'response': "OpenAI library not installed. Please install with: pip install openai",
            'sources': [],
            'drugs_mentioned': drug_names
        }
    except Exception as e:
        return {
            'response': f"Error processing query: {str(e)}",
            'sources': [],
            'drugs_mentioned': drug_names
        }


@router.post("/message")
async def chat_message(request: ChatRequest) -> ChatResponse:
    """
    Send a message to the AI drug assistant.
    """
    result = process_ai_query(request.message, request.history)
    
    return ChatResponse(
        response=result['response'],
        sources=result['sources'],
        drugs_mentioned=result['drugs_mentioned']
    )


@router.get("/status")
async def chat_status() -> dict:
    """
    Check if AI chat is available (API key configured).
    """
    api_key = os.getenv("OPENAI_API_KEY", "")
    return {
        'available': bool(api_key),
        'message': 'AI chat is ready' if api_key else 'OpenAI API key not configured'
    }


@router.get("/coadmin/status")
async def coadmin_status() -> dict:
    """Check if the clinical co-administration agent is available."""
    provider = os.getenv("COADMIN_LLM_PROVIDER", "openai").lower()
    key = os.getenv("ANTHROPIC_API_KEY", "") if provider == "anthropic" else os.getenv("OPENAI_API_KEY", "")
    return {
        'available': bool(key),
        'provider': provider,
        'model': os.getenv("COADMIN_LLM_MODEL", "claude-haiku-4-5" if provider == "anthropic" else "gpt-4o-mini"),
        'message': 'Clinical AI assistant is ready' if key else 'AI API key not configured',
    }


@router.post("/coadmin")
async def coadmin_chat(request: ChatRequest) -> ChatResponse:
    """
    Clinical co-administration assistant (tool-using, grounded in openFDA/DrugBank
    data). Distinct from /chat/message, which focuses on 3D-printing compatibility.
    """
    from ..agents.coadmin_agent import run_coadmin_agent
    result = run_coadmin_agent(request.message, request.history)
    return ChatResponse(
        response=result['response'],
        sources=result.get('sources', []),
        drugs_mentioned=result.get('drugs_mentioned', []),
    )


@router.get("/synopsis/{drug_name}")
async def get_drug_synopsis(drug_name: str) -> dict:
    """
    Get a comprehensive AI-generated synopsis for a specific drug.
    """
    query = f"Give me a comprehensive synopsis of {drug_name}"
    result = process_ai_query(query)
    
    return {
        'drug_name': drug_name,
        'synopsis': result['response'],
        'sources': result['sources']
    }
