"""
Week 4 — Stateful LangGraph Healthcare Research Agent
Domain: Healthcare / Medical Research

"""

import asyncio
import operator
import requests

from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from typing_extensions import TypedDict


# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────

MAX_ATTEMPTS = 3       
MODEL_NAME   = "llama3.2"  

SYSTEM_PROMPT = """You are a knowledgeable and compassionate healthcare research assistant.
You help users understand disease statistics, medication details, and ongoing clinical research.

Rules:
- Always use the available tools to fetch real data. Never guess numbers or drug facts.
- For disease stats questions, always call get_disease_stats.
- For drug/medication questions, always call get_drug_info.
- For research/trial questions, always call find_clinical_trials.
- Remind users that your information is for educational purposes only,
  and they should consult a qualified doctor for diagnosis or treatment decisions.
"""

QUALITY_SYSTEM_PROMPT = """You are a strict quality reviewer for healthcare research answers.
Evaluate whether the answer is complete, factual, and safe.

Respond with EXACTLY one of:
  PASS  — the answer is complete, references real data, and is safe to show the user.
  RETRY — the answer is missing data, vague, contains no tool results, or could mislead.

After PASS or RETRY, add one sentence explaining why.

Example good response:  "PASS — Answer includes real statistics from disease.sh and appropriate disclaimers."
Example retry response: "RETRY — Answer contains no actual drug data; the tool was never called."
"""


# ─────────────────────────────────────────────
# REAL API TOOLS 
# ─────────────────────────────────────────────

@tool
def get_disease_stats(country: str) -> str:
    """
    Fetch live COVID-19 statistics for a country (or globally) using disease.sh.
    Use 'global' for worldwide totals.

    Args:
        country: Country name or ISO code, e.g. 'India', 'USA', 'global'.
    """
    try:
        if country.lower() in ("global", "all", "world", "worldwide"):
            url   = "https://disease.sh/v3/covid-19/all"
            label = "Global"
        else:
            url   = f"https://disease.sh/v3/covid-19/countries/{country}"
            label = None

        resp = requests.get(url, timeout=6)
        if resp.status_code == 404:
            return (
                f"Country '{country}' not found. "
                "Try the full name or ISO code, e.g. 'USA', 'India', 'UK'."
            )
        resp.raise_for_status()
        data = resp.json()

        updated_ms: int = data.get("updated", 0)
        updated_str = (
            datetime.fromtimestamp(updated_ms / 1000, tz=timezone.utc)
            .strftime("%Y-%m-%d %H:%M UTC")
            if updated_ms else "N/A"
        )
        name = label or data.get("country", "Unknown")

        def fmt(n: int | None) -> str:
            return f"{n:,}" if isinstance(n, int) else "N/A"

        return (
            f"COVID-19 Statistics - {name}\n"
            f"  Total Cases    : {fmt(data.get('cases'))}\n"
            f"  Deaths         : {fmt(data.get('deaths'))}\n"
            f"  Recovered      : {fmt(data.get('recovered'))}\n"
            f"  Active Cases   : {fmt(data.get('active'))}\n"
            f"  Critical       : {fmt(data.get('critical'))}\n"
            f"  Total Tests    : {fmt(data.get('tests'))}\n"
            f"  Population     : {fmt(data.get('population'))}\n"
            f"  Last Updated   : {updated_str}"
        )
    except requests.RequestException as e:
        return f"Could not fetch disease statistics: {e}"


@tool
def get_drug_info(drug_name: str) -> str:
    """
    Look up FDA-approved drug label information (OpenFDA API).
    Returns brand/generic names, manufacturer, indications, warnings, dosage.

    Args:
        drug_name: Generic or brand name of the drug, e.g. 'ibuprofen', 'metformin'.
    """
    def _fetch(field: str) -> requests.Response:
        return requests.get(
            "https://api.fda.gov/drug/label.json",
            params={"search": f'openfda.{field}:"{drug_name}"', "limit": 1},
            timeout=8,
        )

    def _trunc(text: str, chars: int = 350) -> str:
        return text[:chars].rstrip() + "..." if len(text) > chars else text

    def _first(v: list | str | None, fb: str = "N/A") -> str:
        return (v[0] if v else fb) if isinstance(v, list) else (v or fb)

    try:
        resp = _fetch("generic_name")
        if resp.status_code == 404:
            resp = _fetch("brand_name")
        if resp.status_code == 404:
            return f"No FDA drug label found for '{drug_name}'."
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            return f"No drug label found for '{drug_name}'."

        label   = results[0]
        openfda = label.get("openfda", {})
        return (
            f"Drug Information - {', '.join(openfda.get('generic_name', ['N/A']))}\n"
            f"  Brand Name(s)  : {', '.join(openfda.get('brand_name', ['N/A']))}\n"
            f"  Manufacturer   : {_first(openfda.get('manufacturer_name'))}\n"
            f"  Indications    : {_trunc(_first(label.get('indications_and_usage')))}\n"
            f"  Warnings       : {_trunc(_first(label.get('warnings', label.get('boxed_warning'))))}\n"
            f"  Dosage Notes   : {_trunc(_first(label.get('dosage_and_administration')))}\n"
            f"WARNING: Always consult a licensed pharmacist or doctor before use."
        )
    except requests.RequestException as e:
        return f"Drug info lookup failed: {e}"


@tool
def find_clinical_trials(condition: str, max_results: int = 3) -> str:
    """
    Search ClinicalTrials.gov for actively recruiting studies on a medical condition.

    Args:
        condition:   Medical condition, e.g. 'diabetes', 'lung cancer', 'alzheimer'.
        max_results: Number of trials to return (1-5).
    """
    max_results = max(1, min(max_results, 5))
    try:
        resp = requests.get(
            "https://clinicaltrials.gov/api/v2/studies",
            params={
                "query.cond": condition,
                "filter.overallStatus": "RECRUITING",
                "pageSize": max_results,
                "format": "json",
            },
            timeout=8,
        )
        resp.raise_for_status()
        data    = resp.json()
        studies = data.get("studies", [])
        total   = data.get("totalCount", 0)

        if not studies:
            return f"No recruiting trials found for '{condition}'. Try a broader term."

        lines = [
            f"Clinical Trials for '{condition}' - "
            f"showing {len(studies)} of {total:,} recruiting:\n"
        ]
        for i, study in enumerate(studies, 1):
            proto       = study.get("protocolSection", {})
            id_mod      = proto.get("identificationModule", {})
            status_mod  = proto.get("statusModule", {})
            design_mod  = proto.get("designModule", {})
            sponsor_mod = proto.get("sponsorCollaboratorsModule", {})
            nct_id      = id_mod.get("nctId", "N/A")
            title       = id_mod.get("briefTitle", "No title")[:90]
            phase       = ", ".join(design_mod.get("phases", [])) or "Not specified"
            sponsor     = sponsor_mod.get("leadSponsor", {}).get("name", "N/A")
            lines.append(
                f"  [{i}] {title}\n"
                f"      NCT ID  : {nct_id}\n"
                f"      Status  : {status_mod.get('overallStatus', 'N/A')}\n"
                f"      Phase   : {phase}\n"
                f"      Sponsor : {sponsor}\n"
                f"      Link    : https://clinicaltrials.gov/study/{nct_id}"
            )
        return "\n".join(lines)
    except requests.RequestException as e:
        return f"Clinical trials search failed: {e}"


TOOLS   = [get_disease_stats, get_drug_info, find_clinical_trials]
TOOL_MAP = {t.name: t for t in TOOLS}


# ─────────────────────────────────────────────
# LLM SETUP  (Ollama — no API key needed)
# ─────────────────────────────────────────────

llm       = ChatOllama(model=MODEL_NAME, temperature=0, num_ctx=8192)
llm_tools = llm.bind_tools(TOOLS)
llm_judge = ChatOllama(model=MODEL_NAME, temperature=0, num_ctx=4096)


# ─────────────────────────────────────────────
# AGENT STATE
# ─────────────────────────────────────────────

class AgentState(TypedDict):
    """
    State passed between graph nodes.

    messages:        operator.add reducer — every node appends, never overwrites.
    attempts:        retry counter (infinite-loop guard).
    quality_verdict: latest verdict from quality_check node ("PASS"/"RETRY"/"").
    draft_answer:    last AI text content (used by human review in BONUS mode).
    """
    messages:        Annotated[list[BaseMessage], operator.add]
    attempts:        int
    quality_verdict: str
    draft_answer:    str


# ─────────────────────────────────────────────
# NODE FUNCTIONS
# ─────────────────────────────────────────────

async def agent_node(state: AgentState) -> dict:
    """
    Node 1 — AGENT
    Main LLM call (with tools bound). Produces either tool calls or a final answer.
    """
    print(f"\n[agent_node] attempt={state['attempts']}")
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response: AIMessage = await llm_tools.ainvoke(messages)

    has_calls = bool(getattr(response, "tool_calls", None))
    print(f"  tool_calls={has_calls}, content_len={len(str(response.content))}")

    draft = response.content if isinstance(response.content, str) else ""
    return {
        "messages":     [response],
        "draft_answer": draft,
    }


async def tool_node(state: AgentState) -> dict:
    """
    Node 2 — TOOLS
    Executes all tool calls from the most recent AIMessage and returns ToolMessages.
    """
    last_ai: AIMessage = state["messages"][-1]
    tool_messages: list[ToolMessage] = []

    for tc in last_ai.tool_calls:
        print(f"  [tool_node] -> {tc['name']}({tc['args']})")
        fn     = TOOL_MAP.get(tc["name"])
        result = fn.invoke(tc["args"]) if fn else f"Unknown tool: {tc['name']}"
        preview = result[:120] + "..." if len(result) > 120 else result
        print(f"  [tool_node] <- {preview}")
        tool_messages.append(
            ToolMessage(content=result, tool_call_id=tc["id"])
        )

    return {"messages": tool_messages}


async def quality_check_node(state: AgentState) -> dict:
    """
    Node 3 — QUALITY CHECK
    A second LLM call reviews the last answer text. Returns PASS or RETRY.
    This is the node paused by interrupt_before in BONUS mode.
    """
    last_answer = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage) and msg.content:
            last_answer = msg.content if isinstance(msg.content, str) else str(msg.content)
            break

    print(f"\n[quality_check_node] reviewing answer ({len(last_answer)} chars)...")

    judge_messages = [
        SystemMessage(content=QUALITY_SYSTEM_PROMPT),
        HumanMessage(content=f"Answer to review:\n\n{last_answer}"),
    ]
    verdict_msg: AIMessage = await llm_judge.ainvoke(judge_messages)
    verdict_text = verdict_msg.content if isinstance(verdict_msg.content, str) else ""
    verdict = "PASS" if verdict_text.strip().upper().startswith("PASS") else "RETRY"

    print(f"  [quality_check_node] verdict={verdict} — {verdict_text[:80]}")
    return {
        "quality_verdict": verdict,
        "attempts":        state["attempts"] + 1,
    }


async def reflect_node(state: AgentState) -> dict:
    """
    Node 4 — REFLECT  (retry path only)
    Injects a correction message so the agent retries with tool usage.
    """
    print(f"\n[reflect_node] injecting retry instruction (attempt {state['attempts']})")
    retry_msg = HumanMessage(
        content=(
            "Your previous answer was not complete or did not include real data "
            "from the tools. Please try again: call the relevant tool(s) and "
            "produce a thorough, factual answer using the data you retrieve."
        )
    )
    return {"messages": [retry_msg]}


# ─────────────────────────────────────────────
# CONDITIONAL EDGE FUNCTIONS
# ─────────────────────────────────────────────

def route_after_agent(state: AgentState) -> Literal["tools", "quality_check"]:
    """Route to tools if the agent made tool calls, else to quality_check."""
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return "quality_check"


def route_after_quality(state: AgentState) -> Literal["reflect", "__end__"]:
    """Route to reflect (retry) or end based on quality verdict / attempt count."""
    if state["quality_verdict"] == "PASS" or state["attempts"] >= MAX_ATTEMPTS:
        if state["attempts"] >= MAX_ATTEMPTS and state["quality_verdict"] != "PASS":
            print(f"  [router] MAX_ATTEMPTS={MAX_ATTEMPTS} reached — forcing END")
        return "__end__"
    return "reflect"


# ─────────────────────────────────────────────
# GRAPH CONSTRUCTION
# ─────────────────────────────────────────────

def build_graph(checkpointer):
    """Build and compile the LangGraph StateGraph with checkpointer."""
    builder = StateGraph(AgentState)

    # --- Add nodes ---
    builder.add_node("agent",         agent_node)
    builder.add_node("tools",         tool_node)
    builder.add_node("quality_check", quality_check_node)
    builder.add_node("reflect",       reflect_node)

    # --- Add edges ---
    builder.add_edge(START, "agent")

    builder.add_conditional_edges(
        "agent",
        route_after_agent,
        {"tools": "tools", "quality_check": "quality_check"},
    )
    builder.add_edge("tools", "agent")          # tool results feed back to agent

    builder.add_conditional_edges(
        "quality_check",
        route_after_quality,
        {"reflect": "reflect", "__end__": END},
    )
    builder.add_edge("reflect", "agent")        # reflect triggers agent retry

    return builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["quality_check"],     # pause before review
    )


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def extract_final_answer(state: AgentState) -> str:
    """Return the last AI text response from the message history."""
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage) and msg.content:
            return msg.content if isinstance(msg.content, str) else str(msg.content)
    return "[No answer generated]"


async def _resume_until_done(graph, config: dict) -> None:
    """Keep resuming the graph after each interrupt until it reaches END."""
    while True:
        snapshot = await graph.aget_state(config)
        if not snapshot.next:          
            break
        async for event in graph.astream(None, config=config):
            for node_name in event:
                print(f"  [stream] node={node_name}")


# ─────────────────────────────────────────────
# STANDARD RUNNER  (auto-approves interrupts)
# ─────────────────────────────────────────────

async def run_query(graph, query: str, thread_id: str) -> str:
    """Run a query through the graph, auto-approving the quality_check interrupt."""
    config = {"configurable": {"thread_id": thread_id}}
    init_state: AgentState = {
        "messages":        [HumanMessage(content=query)],
        "attempts":        0,
        "quality_verdict": "",
        "draft_answer":    "",
    }

    print(f"\n{'='*60}")
    print(f"QUERY  : {query}")
    print(f"THREAD : {thread_id}")
    print("="*60)

   
    async for event in graph.astream(init_state, config=config):
        for node_name in event:
            print(f"  [stream] node={node_name}")

   
    await _resume_until_done(graph, config)

    final_snapshot = await graph.aget_state(config)
    return extract_final_answer(final_snapshot.values)


# ─────────────────────────────────────────────
# Human-in-the-loop
# ─────────────────────────────────────────────

async def run_query_with_human_review(graph, query: str, thread_id: str) -> str:
    """
    BONUS MODE — pauses before quality_check so a human can inspect
    the draft answer, optionally edit state, then resume.
    """
    config = {"configurable": {"thread_id": thread_id}}
    init_state: AgentState = {
        "messages":        [HumanMessage(content=query)],
        "attempts":        0,
        "quality_verdict": "",
        "draft_answer":    "",
    }

    print(f"\n{'='*60}")
    print(f"[BONUS] QUERY  : {query}")
    print(f"[BONUS] THREAD : {thread_id}")
    print("="*60)

   
    async for event in graph.astream(init_state, config=config):
        for node_name in event:
            print(f"  [stream] node={node_name}")

    # ── HUMAN REVIEW ──────────────────────────────────────────────
    snapshot = await graph.aget_state(config)
    draft    = snapshot.values.get("draft_answer", "")

    print("\n" + "─"*60)
    print("PAUSED — Draft answer ready for human review:")
    print("─"*60)
    print(draft[:500] + ("..." if len(draft) > 500 else ""))
    print("─"*60)

    edit = input(
        "\n[Human] Press ENTER to approve, or type an edit instruction: "
    ).strip()

    if edit:
        await graph.aupdate_state(
            config,
            {"messages": [HumanMessage(content=f"[Human reviewer note]: {edit}")]},
            as_node="agent",
        )
        print("  [human] State updated with reviewer note.")
    else:
        print("  [human] Approved — resuming.")

   
    await _resume_until_done(graph, config)

    final_snapshot = await graph.aget_state(config)
    return extract_final_answer(final_snapshot.values)


# ─────────────────────────────────────────────
# DEMO
# ─────────────────────────────────────────────

async def main():
    async with AsyncSqliteSaver.from_conn_string("healthcare_checkpoints.db") as checkpointer:
        graph = build_graph(checkpointer)

        print("\n" + "★"*60)
        print(f"  WEEK 4 — LangGraph Healthcare Agent  (model: {MODEL_NAME})")
        print("★"*60)

        # ── Run 1: single-pass — COVID global stats ──
        answer1 = await run_query(
            graph,
            query="What are the current global COVID-19 statistics?",
            thread_id="thread-001",
        )
        print(f"\n{'─'*60}")
        print("FINAL ANSWER (Run 1):")
        print(answer1)

        # ── Run 2: ( Retry cycle ) multi-tool — drug info + clinical trials ──
        answer2 = await run_query(
            graph,
            query=(
                "Tell me about metformin — what is it for and what are the warnings? "
                "Also find 2 active clinical trials for diabetes."
            ),
            thread_id="thread-002",
        )
        print(f"\n{'─'*60}")
        print("FINAL ANSWER (Run 2):")
        print(answer2)

        # ── BONUS: human-in-the-loop ──
        print("\n" + "★"*60)
        print("  BONUS: Human-in-the-Loop Demo")
        print("★"*60)
        answer3 = await run_query_with_human_review(
            graph,
            query="Are there any active clinical trials for Alzheimer's disease? Show me 3.",
            thread_id="thread-003",
        )
        print(f"\n{'─'*60}")
        print("FINAL ANSWER (Bonus Run):")
        print(answer3)


if __name__ == "__main__":
    asyncio.run(main())
