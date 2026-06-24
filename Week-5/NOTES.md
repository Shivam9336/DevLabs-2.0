# Week 5 — Multi-Agent Systems

**Dates:** Jun 23 – Jun 29

---

## What We're Building This Week

Last week you built a single stateful agent as a LangGraph graph — one `AgentState`, one ReAct loop, one set of tools. That's enough until the job gets big. The moment you stuff a research step, a writing step, a fact-check step, and a formatting step into one agent, three things break: the system prompt becomes a 2,000-word monster, the context window fills with tool junk from steps that have nothing to do with each other, and one bad tool call takes down the entire run.

This week you'll split that one agent into **several focused agents** coordinated by an **orchestrator**. Each agent has a small prompt, its own context, and one job. The orchestrator decides who runs, in what order, and what runs in parallel. When a worker fails, you retry just that worker — not the whole pipeline.

By the end of this week you'll understand the architecture behind every "AI does a multi-step task end to end" product you've seen.

---

## 1. Why More Than One Agent

A single agent is the right default. Reach for multi-agent only when one of these actually hurts you:

| Problem with one agent | What multi-agent fixes |
|---|---|
| One giant system prompt covering 5 unrelated jobs | Each agent gets a small prompt about its one job |
| Context fills with tool results from every step | Each agent has its own fresh context |
| One bad tool call crashes the whole run | Failures are isolated — retry one worker |
| Can't run independent steps at once | Orchestrator fans out parallel workers |
| Impossible to debug "where did it go wrong" | Each agent's input/output is a clean boundary |

The flip side — **don't** go multi-agent when a single agent with 2–3 tools already does the job. More agents = more moving parts, more latency from coordination, more places to break. The one-liner: **split by responsibility, not by excitement.**

---

## 2. The Two Core Patterns

Almost everything you'll build is one of these two shapes.

### Orchestrator–Worker

A central orchestrator breaks a task into subtasks, calls workers, and collects their results. The orchestrator is the only thing that knows the whole plan; workers know nothing about each other.

```
              ┌──────────────┐
              │ Orchestrator │
              └──────┬───────┘
        ┌────────────┼────────────┐
        ▼            ▼            ▼
   ┌─────────┐  ┌─────────┐  ┌─────────┐
   │ Research│  │  Write  │  │  Fact   │
   │  Agent  │  │  Agent  │  │  Check  │
   └─────────┘  └─────────┘  └─────────┘
```

Use it when **you** know the steps up front (research → write → check → format).

### Supervisor (Router)

A supervisor agent decides *at runtime* which agent should act next, based on the current state. The set of next moves isn't fixed — the supervisor loops, picking an agent each turn until the task is done.

```
        ┌────────────┐
   ┌───▶│ Supervisor │◀──┐
   │    └─────┬──────┘   │
   │   "who handles this?"
   │          ▼          │
   │   picks an agent ───┘
   │          ▼
   └── agent does work, returns to supervisor
```

Use it when **the LLM** should decide the routing (a customer query that might need billing, tech support, or sales — you don't know which until you read it).

The difference in one line: **orchestrator = fixed plan you wrote; supervisor = dynamic plan the model decides.**

---

## 3. Each Worker Is Its Own Compiled Graph

The key mental shift from Week 4: a worker isn't a node, it's a **whole graph** — compiled separately, with its own state schema and its own tools. The orchestrator calls it the same way you call any agent: `await worker.ainvoke({...})`.

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict

# ── Worker: a self-contained research agent ──────────────────
class ResearchState(TypedDict):
    task: str
    result: str

async def do_research(state: ResearchState) -> dict:
    findings = await search_web(state["task"])     # its own tools
    return {"result": findings}

research_graph = StateGraph(ResearchState)
research_graph.add_node("research", do_research)
research_graph.set_entry_point("research")
research_graph.add_edge("research", END)
research_agent = research_graph.compile()          # a standalone runnable
```

Now the orchestrator node just calls it:

```python
class OrchestratorState(TypedDict):
    query: str
    research: str
    draft: str

async def research_node(state: OrchestratorState) -> dict:
    out = await research_agent.ainvoke({"task": state["query"]})
    return {"research": out["result"]}             # lift worker output into orchestrator state
```

**Why a separate graph and not just a function?** Because the worker gets its own context, its own checkpointer, its own retry loop. Its 15 tool calls never pollute the orchestrator's state — only the final `result` crosses the boundary.

---

## 4. State: Shared vs Isolated

This is the part people get wrong. There are two state objects in play and they are **not** the same dict.

- **Orchestrator state** — the high-level plan: `query`, `research`, `draft`, `final`. Small. Travels through the orchestrator graph.
- **Worker state** — internal scratch space for one worker: `task`, `messages`, `attempts`, `result`. Lives and dies inside one `ainvoke`.

The boundary between them is deliberate. You pass **only what the worker needs in** (`{"task": ...}`) and lift **only the finished output out** (`{"research": out["result"]}`).

```
Orchestrator state:  { query, research, draft, final }
                            │ pass task in
                            ▼
Worker state:        { task, messages, attempts, result }   ← isolated, discarded after
                            │ lift result out
                            ▼
Orchestrator state:  { query, research: "...", draft, final }
```

**Never** hand a worker your whole orchestrator state. If you do, you've recreated the single-agent context-explosion problem, just with extra steps.

---

## 5. Parallel Workers — Fan-Out / Fan-In

Independent workers should run at the same time. Use `asyncio.gather` inside one orchestrator node.

```python
import asyncio

async def gather_node(state: OrchestratorState) -> dict:
    # Both reads are independent — neither needs the other's output
    research, competitor = await asyncio.gather(
        research_agent.ainvoke({"task": state["query"]}),
        competitor_agent.ainvoke({"task": state["query"]}),
    )
    return {
        "research": research["result"],
        "competitor": competitor["result"],
    }
```

```
Sequential:  research (2s) → competitor (2s)        = 4s
Parallel:    research (2s) ‖ competitor (2s)         = 2s
```

**The rule for what to parallelize:** two tasks with no dependency → parallel. Task B needs Task A's output → sequential. Research and competitor analysis both only need the query, so they fan out. Writing needs both of them, so it runs after the `gather` completes (fan-in).

**Gotcha — partial failure:** if one of the gathered calls raises, `asyncio.gather` cancels the rest by default. Wrap each worker so one failure doesn't kill the others:

```python
results = await asyncio.gather(
    research_agent.ainvoke({"task": q}),
    competitor_agent.ainvoke({"task": q}),
    return_exceptions=True,          # failures come back as values, not crashes
)
for r in results:
    if isinstance(r, Exception):
        ...  # handle / retry just that one
```

---

## 6. How Agents Talk to Each Other

Agents don't share variables — they communicate through **structured messages**. Two clean patterns:

**Hand-off (sequential):** Agent A's output *is* Agent B's input. The orchestrator wires the edge.

```python
research = await research_agent.ainvoke({"task": query})
draft    = await writer_agent.ainvoke({"task": query, "context": research["result"]})
```

**Blackboard (shared scratchpad):** all agents read and write a shared `findings` list on the orchestrator state, using a reducer so writes append instead of overwrite (exactly the Week 4 reducer pattern).

```python
from typing import Annotated
import operator

class OrchestratorState(TypedDict):
    query: str
    findings: Annotated[list, operator.add]   # every agent appends its finding
```

Keep what crosses the boundary **small and typed**. "Pass the whole conversation" is how you leak 40k tokens into a worker that needed two sentences.

---

## 7. The Supervisor Loop in Code

The supervisor is just a node that returns *the name of the next agent*, wired with a conditional edge — the same `add_conditional_edges` you used for the retry loop in Week 4.

```python
async def supervisor_node(state: SupervisorState) -> dict:
    decision = await call_llm(
        system="Route to one of: billing, tech, sales, DONE. Return only the label.",
        messages=state["messages"],
    )
    return {"next": decision.strip()}

def route(state: SupervisorState) -> str:
    return state["next"]                       # "billing" | "tech" | "sales" | "DONE"

graph.add_node("supervisor", supervisor_node)
graph.add_node("billing", billing_agent_node)
graph.add_node("tech", tech_agent_node)
graph.add_node("sales", sales_agent_node)

graph.set_entry_point("supervisor")
graph.add_conditional_edges("supervisor", route, {
    "billing": "billing",
    "tech": "tech",
    "sales": "sales",
    "DONE": END,
})
# each worker routes BACK to the supervisor so it can decide the next move
graph.add_edge("billing", "supervisor")
graph.add_edge("tech", "supervisor")
graph.add_edge("sales", "supervisor")
```

Two non-negotiables, both carried over from Week 4:
- **Max-iterations guard** — track `turns` in state, force `DONE` past a cap, or the supervisor loops forever.
- **Default route case** — if the LLM returns a label not in the map, you get a `KeyError`. Map unknown labels to `END` or a clarify node.

---

## 8. Production Bugs to Guard Against

| Bug | Cause | Fix |
|---|---|---|
| Supervisor never stops | No iteration cap | Track `turns`, force `DONE` at a max |
| Unknown route crashes | LLM returns a label not in the map | Default case → `END` or a clarify node |
| One parallel worker kills the batch | `gather` cancels siblings on first exception | `return_exceptions=True`, handle per-worker |
| Worker context explosion | Orchestrator passed its whole state in | Pass only the fields the worker needs |
| Lost worker output | Forgot to lift `result` back into orchestrator state | Return the mapped dict from the orchestrator node |
| Latency creep | Ran independent workers sequentially | `asyncio.gather` the independent ones |
| Thread ID collision across users | Reused `thread_id` | `uuid4()` per conversation (same as Week 4) |

---

## The One-Liner to Remember

> A multi-agent system splits one big agent into focused agents — each its own compiled graph with a small prompt and isolated context — coordinated either by an **orchestrator** (fixed plan you wrote) or a **supervisor** (dynamic routing the LLM decides). Workers communicate through small typed messages, not shared variables; independent workers fan out with `asyncio.gather` and fan in afterward. The Week 4 disciplines still apply: max-iterations guards, default route cases, and a `uuid4()` thread_id per run.

---

## Resources

### Course
- [DeepLearning.AI — Multi AI Agent Systems with crewAI](https://www.deeplearning.ai/short-courses/multi-ai-agent-systems-with-crewai/) ← the multi-agent mental model, framework-agnostic
- [DeepLearning.AI — AI Agents in LangGraph](https://www.deeplearning.ai/short-courses/ai-agents-in-langgraph/) ← the later lessons cover multi-agent graphs

### Docs
- [LangGraph — Multi-agent concepts](https://langchain-ai.github.io/langgraph/concepts/multi_agent/) ← orchestrator-worker vs supervisor, start here
- [LangGraph — Agent supervisor tutorial](https://langchain-ai.github.io/langgraph/tutorials/multi_agent/agent_supervisor/) ← a runnable supervisor end to end
- [LangGraph — Subgraphs](https://langchain-ai.github.io/langgraph/how-tos/subgraph/) ← how to call one compiled graph from inside another

### Reading
- [Anthropic — Building effective agents](https://www.anthropic.com/research/building-effective-agents) ← the orchestrator-workers and routing sections are exactly this week
- [langchain-ai/langgraph (GitHub)](https://github.com/langchain-ai/langgraph) ← see `examples/multi_agent/` for runnable graphs

---

## Week 5 Deliverable

**Step up from Week 4.** Last week you built one stateful agent. This week you'll coordinate several.

Build a **multi-agent system** that:

1. Has at least **2 worker agents**, each compiled as its **own separate graph** with its own state schema (not just two nodes in one graph)
2. Has an **orchestrator or supervisor** that coordinates the workers
3. Runs at least **two independent workers in parallel** with `asyncio.gather` (fan-out), then combines their results (fan-in)
4. Keeps state **isolated** — the orchestrator passes each worker only what it needs and lifts only the final output back
5. **Guards against failure** — use `return_exceptions=True` (or per-worker try/except) so one worker failing doesn't kill the whole run

**Bonus challenge:** make it a **supervisor** instead of a fixed orchestrator — an LLM node that reads the state and routes to the next agent each turn, looping back to the supervisor until it returns `DONE`. Include a max-iterations guard and a default route case.

Submit in `submissions/your-name/` with a README that shows your agent topology (which agents exist, who calls whom, what runs in parallel) and 2 sample runs — one happy path, and one where a worker fails and the system recovers instead of crashing.
