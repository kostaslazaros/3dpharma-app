"""
Clinical co-administration AI agent (tool-using, provider-agnostic).

Unlike the 3D-printing chat, this agent answers patient-safety questions about
co-administering drugs. It is GROUNDED: it must call tools that return real data
(drug search, drug details, condition flags, the co-administration checker) and
summarise those results, rather than relying on the model's own recall. This keeps
answers accurate and lets us run a cheap model.

Provider/model are configurable:
    COADMIN_LLM_PROVIDER = openai (default) | anthropic
    COADMIN_LLM_MODEL    = gpt-4o-mini (default) | claude-haiku-4-5 | ...
"""

from __future__ import annotations

import json
import os
from typing import Dict, List

from app.services.drug_service import get_drug_service
from app.services import condition_service as cs
from app.services.coadmin_service import check_coadministration, DISCLAIMER

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5"
MAX_TOOL_ITERATIONS = 5

SYSTEM_PROMPT = (
    "You are a clinical co-administration assistant for pharmacists and prescribers. "
    "You assess whether drugs can be safely co-administered and whether they are "
    "contraindicated given patient conditions (pregnancy, lactation, renal or hepatic "
    "impairment, alcohol use, G6PD deficiency, myelosuppression, driving), plus any "
    "stated diseases.\n\n"
    "RULES:\n"
    "1. ALWAYS use the tools to get real data before answering. Never state a "
    "contraindication or interaction from memory alone — call check_coadministration "
    "or get_condition_flags and base your answer on what they return.\n"
    "2. Cite the source (e.g. 'per the openFDA label' or 'DrugBank interaction data').\n"
    "3. If a tool returns nothing for a drug, say the data was not found rather than "
    "guessing.\n"
    "4. Be concise and structured: lead with the bottom line (safe / caution / avoid), "
    "then the key contraindications, interactions, and adverse effects with severity.\n"
    "5. Always end with a one-line disclaimer that this is decision support, not a "
    "substitute for professional judgement."
)

# Canonical tool definitions (provider-neutral JSON schema).
TOOL_DEFS = [
    {
        "name": "search_drug",
        "description": "Search the drug database for drug/active-substance names matching a query.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Partial or full drug name"}},
            "required": ["query"],
        },
    },
    {
        "name": "get_drug_details",
        "description": "Get summary details (type, categories, dosing, notable interactions) for one drug.",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Exact drug name"}},
            "required": ["name"],
        },
    },
    {
        "name": "get_condition_flags",
        "description": (
            "Check whether a single drug's label flags a concern for one patient condition. "
            "condition must be one of: " + ", ".join(sorted(cs.VALID_CONDITIONS)) + "."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "drug": {"type": "string"},
                "condition": {"type": "string"},
            },
            "required": ["drug", "condition"],
        },
    },
    {
        "name": "check_coadministration",
        "description": (
            "Run a full co-administration check for one or more drugs against optional "
            "patient context. Returns contraindications, drug-drug interactions, and "
            "adverse effects, each severity-graded."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "drugs": {"type": "array", "items": {"type": "string"}},
                "conditions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Patient conditions, e.g. pregnancy, renal_impairment, g6pd_deficiency",
                },
                "diseases": {"type": "array", "items": {"type": "string"}},
                "sex": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["drugs"],
        },
    },
]


# ----------------------------------------------------------------------------
# Tool execution
# ----------------------------------------------------------------------------

def _execute_tool(name: str, args: Dict) -> Dict:
    service = get_drug_service()
    try:
        if name == "search_drug":
            return {"results": service.search_drugs(args.get("query", ""))[:15]}
        if name == "get_drug_details":
            summary = service.get_summary(args.get("name", ""))
            if "error" in summary:
                return summary
            # Trim to what the model needs (keep the payload small/cheap).
            return {
                "name": summary.get("name"),
                "type": summary.get("type"),
                "categories": summary.get("categories", [])[:6],
                "dosing": summary.get("dosing", {}),
                "interaction_count": summary.get("interaction_count", 0),
                "notable_interactions": [
                    {"drug": i.get("name") or i.get("drug"),
                     "description": (i.get("description") or "")[:200]}
                    for i in summary.get("interactions_list", [])[:5]
                ],
            }
        if name == "get_condition_flags":
            drug = args.get("drug", "")
            condition = args.get("condition", "")
            sections = service.get_label_sections(drug)
            hit = cs.assess_condition(drug, sections, condition)
            return hit or {"drug": drug, "condition": condition, "flag": None,
                           "note": "No concern found in the label for this condition."}
        if name == "check_coadministration":
            patient = {
                "sex": args.get("sex"),
                "age": args.get("age"),
                "conditions": args.get("conditions", []),
                "diseases": args.get("diseases", []),
            }
            return check_coadministration(args.get("drugs", []), patient)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}
    return {"error": f"Unknown tool: {name}"}


# ----------------------------------------------------------------------------
# Provider adapters
# ----------------------------------------------------------------------------

def _openai_tools() -> List[Dict]:
    return [{"type": "function", "function": t} for t in TOOL_DEFS]


def _anthropic_tools() -> List[Dict]:
    return [{"name": t["name"], "description": t["description"],
             "input_schema": t["parameters"]} for t in TOOL_DEFS]


def _run_openai(model: str, message: str, history: List[Dict]) -> Dict:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in (history or [])[-6:]:
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": message})

    tools_used: List[str] = []
    for _ in range(MAX_TOOL_ITERATIONS):
        resp = client.chat.completions.create(
            model=model, messages=messages, tools=_openai_tools(),
            temperature=0.3, max_tokens=1200,
        )
        choice = resp.choices[0].message
        if not choice.tool_calls:
            return {"response": choice.content or "", "tools_used": tools_used}
        messages.append({
            "role": "assistant",
            "content": choice.content or "",
            "tool_calls": [tc.model_dump() for tc in choice.tool_calls],
        })
        for tc in choice.tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            result = _execute_tool(tc.function.name, args)
            tools_used.append(tc.function.name)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result)[:6000],
            })
    # Final call without tools to force a text answer.
    resp = client.chat.completions.create(
        model=model, messages=messages, temperature=0.3, max_tokens=1200)
    return {"response": resp.choices[0].message.content or "", "tools_used": tools_used}


def _run_anthropic(model: str, message: str, history: List[Dict]) -> Dict:
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
    messages = []
    for msg in (history or [])[-6:]:
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": message})

    tools_used: List[str] = []
    for _ in range(MAX_TOOL_ITERATIONS):
        resp = client.messages.create(
            model=model, system=SYSTEM_PROMPT, messages=messages,
            tools=_anthropic_tools(), max_tokens=1200, temperature=0.3,
        )
        if resp.stop_reason != "tool_use":
            text = "".join(b.text for b in resp.content if b.type == "text")
            return {"response": text, "tools_used": tools_used}
        messages.append({"role": "assistant", "content": [b.model_dump() for b in resp.content]})
        tool_results = []
        for block in resp.content:
            if block.type == "tool_use":
                result = _execute_tool(block.name, block.input or {})
                tools_used.append(block.name)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result)[:6000],
                })
        messages.append({"role": "user", "content": tool_results})
    resp = client.messages.create(
        model=model, system=SYSTEM_PROMPT, messages=messages, max_tokens=1200, temperature=0.3)
    text = "".join(b.text for b in resp.content if b.type == "text")
    return {"response": text, "tools_used": tools_used}


# ----------------------------------------------------------------------------
# Public entry point
# ----------------------------------------------------------------------------

def run_coadmin_agent(message: str, history: List[Dict] = None) -> Dict:
    """Answer a clinical co-administration question using tool-grounded reasoning."""
    provider = os.getenv("COADMIN_LLM_PROVIDER", "openai").lower()
    if provider == "anthropic":
        model = os.getenv("COADMIN_LLM_MODEL", DEFAULT_ANTHROPIC_MODEL)
        if not os.getenv("ANTHROPIC_API_KEY"):
            return _no_key_response("ANTHROPIC_API_KEY")
        runner = _run_anthropic
    else:
        model = os.getenv("COADMIN_LLM_MODEL", DEFAULT_OPENAI_MODEL)
        if not os.getenv("OPENAI_API_KEY"):
            return _no_key_response("OPENAI_API_KEY")
        runner = _run_openai

    try:
        out = runner(model, message, history or [])
    except Exception as exc:  # noqa: BLE001
        return {
            "response": f"Error processing query: {type(exc).__name__}: {exc}",
            "sources": [], "drugs_mentioned": [],
        }

    response_text = out.get("response", "") or ""
    if "disclaimer" not in response_text.lower() and DISCLAIMER[:30].lower() not in response_text.lower():
        response_text = f"{response_text}\n\n_{DISCLAIMER}_"
    return {
        "response": response_text,
        "sources": ["openFDA drug labels", "DrugBank"],
        "drugs_mentioned": [],
        "tools_used": out.get("tools_used", []),
        "model": model,
        "provider": provider,
    }


def _no_key_response(var: str) -> Dict:
    return {
        "response": f"AI assistant is not configured. Please set the {var} environment variable.",
        "sources": [], "drugs_mentioned": [],
    }
