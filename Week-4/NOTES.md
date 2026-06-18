# Week 4 — LangGraph: Stateful Agents

**Dates:** Jun 16 – Jun 22

---

## What We're Building This Week

In Week 2 your agent loop was a hand-written `while True:` — you kept calling the model, running tools, and feeding results back until it stopped asking for tools. That works, but it falls apart the moment you need real agent behaviour: branching ("if the answer is bad, retry"), persistence ("the server crashed mid-run, resume from where we were"), or a human approval step ("don't send this until I say so").

This week you'll rebuild that loop as a **graph**. LangGraph models an agent as nodes (functions), edges (routing), and a shared state object that travels through the whole run. Once it's a graph, loops, branching, crash recovery, and human-in-the-loop become one-line features instead of custom plumbing.

By the end of this week you'll understand the architecture that real production agents are actually built on.

---

## 1. What LangGraph Solves

LangChain is a **linear chain**: Input → Step 1 → Step 2 → Output. No loops, no branching.

Real agents need cycles — think, act, observe, retry, branch. That's a graph.

**LangGraph** = a framework for building agents as directed graphs.

- **Nodes** = Python functions (the work)
- **Edges** = transitions between nodes (the routing)
- **State** = shared memory that travels through the entire graph

### Agent vs Chatbot

```
Chatbot: user message → LLM → response. One shot.

Agent:   user message → LLM → tool call → observe result → LLM → tool call
         → ... repeat until goal reached or max iterations hit.
```

An agent is just **LLM + tools + ReAct loop + memory**.

### The ReAct loop

```
Thought  → "I need to find the revenue for client X"
Action   → calls fetch_revenue(client_id="client-001")
Observe  → "₹1,20,000 this week"
Thought  → "I have the data. I can answer now."
Answer   → "Client X's revenue this week is ₹1,20,000."
```

The loop continues until: goal reached **OR** max_iterations hit **OR** an explicit `END`.

### Agent failure modes

| Failure | Cause | Fix |
|---|---|---|
| Infinite loop | Same tool called repeatedly | `max_iterations` tracked in state |
| Context explosion | Every tool result appended to messages (20 calls × 2k = 40k tokens) | Summarize tool results before appending |
| Wrong tool called | Bad tool description | Rewrite the description, add "NOT for X" |

---

## 2. State

State is the **shared whiteboard**. Every node reads from it and writes to it. It travels through the entire graph and lives for the duration of one graph run.

```python
from typing import TypedDict

class AgentState(TypedDict):
    query: str
    context: list
    answer: str
    attempts: int
```

### TypedDict vs Pydantic

`TypedDict` does **zero runtime validation** — it's just editor hints, a plain dict under the hood. LangGraph uses `TypedDict` because it merges partial updates constantly. Pydantic would require reconstructing the full model on every single node update.

### The reducer pattern

```python
from typing import Annotated
import operator

class AgentState(TypedDict):
    messages: Annotated[list, operator.add]  # append, don't overwrite
```

Without a reducer, **last write wins**. Node A writes `["msg1"]`, Node B writes `["msg2"]` → state ends up with just `["msg2"]`. Node A's write is lost.

With the `operator.add` reducer, state has `["msg1", "msg2"]` — both preserved. Use this for chat history. Don't use it for single-value fields like `answer` or `attempts`.

### Initial state

```python
app.invoke({"query": "show revenue", "attempts": 0})
```

LangGraph takes this dict, treats it as `AgentState`, and passes it as `state` to your nodes. You never instantiate `AgentState()` yourself — LangGraph does it internally.

---

## 3. Nodes

A node is a Python function. It takes `state` and returns a dict of **only what changed**. LangGraph merges that returned dict back into the state.

```python
def retrieve_node(state: AgentState) -> dict:
    chunks = retrieve(state["query"])       # read from state
    return {"context": chunks}              # write only what changed

async def generate_node(state: AgentState) -> dict:
    context = state["context"]
    answer = await call_llm(state["query"], context)
    return {
        "answer": answer,
        "attempts": state["attempts"] + 1   # increment here, not in retrieve
    }
```

**Why increment `attempts` in generate, not retrieve?** One full attempt = retrieve + generate together. Incrementing in retrieve would count retrieval failures as attempts even if the LLM never ran. Increment after the full cycle completes.

---

## 4. Edges

**Normal edge** — always goes to the same next node:

```python
graph.add_edge("retrieve", "generate")
```

**Conditional edge** — reads state, returns a string, and that string maps to the next node:

```python
def should_continue(state: AgentState) -> str:
    if state["answer"] == "INSUFFICIENT_CONTEXT" and state["attempts"] < 3:
        return "retry"
    return "done"

graph.add_conditional_edges(
    "generate",               # from this node
    should_continue,          # run this after generate completes
    {"retry": "retrieve",     # if "retry" → go to retrieve
     "done": END}             # if "done" → stop
)
```

Notes:
- `should_continue` is a **sync** `def`, not async — it does no I/O, it just reads state.
- If it returns a string that isn't in the map → `KeyError` crash. **Always have a default case.**

---

## 5. Full Graph Skeleton

```python
from langgraph.graph import StateGraph, END

graph = StateGraph(AgentState)              # 1. create graph with state schema
graph.add_node("retrieve", retrieve_node)   # 2. add nodes (label, function)
graph.add_node("generate", generate_node)
graph.set_entry_point("retrieve")           # 3. which node runs first
graph.add_edge("retrieve", "generate")      # 4. normal edge
graph.add_conditional_edges(                # 5. conditional edge (the loop)
    "generate", should_continue, {"retry": "retrieve", "done": END}
)
app = graph.compile()                       # 6. validate + build runnable

result = app.invoke({"query": "...", "attempts": 0})
```

Those six steps — schema, nodes, entry point, edges, conditional edges, compile — are the whole pattern. Everything else this week builds on this skeleton.

---

## 6. Async Nodes + Parallel Calls

**Async node** — use `async def`, `await` your I/O calls, and run with `ainvoke`:

```python
async def retrieve_node(state: AgentState) -> dict:
    chunks = await retrieve(state["query"])
    return {"context": chunks}

result = await app.ainvoke({"query": "...", "attempts": 0})
```

**Parallel calls inside a node** — when two I/O calls are independent:

```python
async def retrieve_node(state: AgentState) -> dict:
    shopify, meta = await asyncio.gather(
        fetch_shopify(state["client_id"]),
        fetch_meta(state["client_id"])
    )
    return {"context": [shopify, meta]}
```

```
Sequential: 1.2s + 1.2s = 2.4s
Parallel:   max(1.2s, 1.2s) = 1.2s — half the latency
```

### Parallel worker pattern (multi-agent)

What to parallelize: tasks with **no dependency** on each other.

- Memory read + Retrieval read → parallel (both are reads, neither needs the other)
- Generation → sequential after both (it needs output from both)

```python
memory_result, retrieval_result = await asyncio.gather(
    memory_agent.ainvoke({"query": state["query"]}),
    retrieval_agent.ainvoke({"query": state["query"]})
)
```

---

## 7. Checkpointing

After every node completes, LangGraph serializes the full state to storage. Crash mid-run → resume from the last completed node, not from the start.

```python
from langgraph.checkpoint.aiosqlite import AsyncSqliteSaver

async with AsyncSqliteSaver.from_conn_string("checkpoints.db") as checkpointer:
    app = graph.compile(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "user-001"}}

    # first run — crashes after node 2
    await app.ainvoke({"query": "...", "attempts": 0}, config=config)

    # resume — pass None as input, same thread_id
    await app.ainvoke(None, config=config)
    # LangGraph loads the last checkpoint, runs from node 3. Nodes 1-2 don't re-run.
```

### What a checkpoint contains

```python
{
  "id": "1718000000000-0",      # timestamp-based unique ID
  "channel_values": {            # this IS your state
      "query": "show revenue",
      "attempts": 1,
      ...
  },
  "next": ["generate"],          # which node runs next
  "metadata": {"step": 1}
}
```

A checkpoint is saved **after** a node completes. A node that crashed mid-run has no checkpoint for it. On resume: find the last checkpoint → load state → run the `next` node from the start.

### Thread isolation (multi-tenancy)

```python
config_a = {"configurable": {"thread_id": "user-001"}}
config_b = {"configurable": {"thread_id": "user-002"}}
```

Completely isolated. 1000 users = 1000 thread IDs. **One** compiled graph serves all of them.

### Storage backends

| Backend | When |
|---|---|
| `AsyncSqliteSaver` | Local dev only. No horizontal scaling. |
| `AsyncRedisSaver` | Production. Fast, TTL support, expires old threads automatically. |
| `AsyncPostgresSaver` | Production + audit trail. Durable, queryable, slower writes. |

### Inspecting state (production debugging)

```python
state = await app.aget_state(config)
print(state.values)   # full state at current checkpoint
print(state.next)     # which node runs next

async for checkpoint in app.aget_state_history(config):
    print(checkpoint.values)   # time-travel: every state the graph ever had
```

---

## 8. Human in the Loop (HITL)

Pause the graph at a specific node, wait for human input, resume with that input.

```python
app = graph.compile(
    checkpointer=checkpointer,
    interrupt_before=["send_message"]   # pause BEFORE this node
)
```

### What happens internally

1. `generate_node` completes → checkpoint saved with `next=["send_message"]`
2. LangGraph sees `interrupt_before` → raises `GraphInterrupt` internally
3. `ainvoke` catches it → returns cleanly (no crash, no error)
4. The graph is suspended. State is saved. Waiting.

Your code now shows the draft to the human. They review, edit, approve.

```python
# Human edits and approves:
await app.aupdate_state(config, {"report": "corrected report here"})
# aupdate_state: loads latest checkpoint, applies new values, saves a new checkpoint

await app.ainvoke(None, config=config)
# resumes from send_message with the corrected report in state
```

### Full timeline

```
fetch_data runs       → checkpoint saved
generate_report runs  → checkpoint saved → PAUSE (interrupt_before)
human reviews draft   → edits report     → aupdate_state
human approves        → ainvoke(None)    → send_message runs
```

### A real use case

Before an agent sends a weekly client report over WhatsApp: the agent pauses, you review the report in a dashboard, you approve, the agent sends. That's the entire change — one line: `interrupt_before=["send_message"]`.

### Crash recovery with HITL

- **User A** is paused waiting for human approval. Server restarts → the checkpoint exists at the pause point. Still waiting. The restart is irrelevant.
- **User B** is mid-run at `generate_node` when the server crashes → the checkpoint exists after `retrieve` (the last completed node). On retry: resumes at the start of `generate_node`. `retrieve` doesn't re-run.

---

## 9. Multi-Agent Architectures

One agent doing everything → huge prompt, context exhaustion, one failure kills the whole run. Multi-agent → each agent does one thing well, an orchestrator coordinates.

### Orchestrator-worker pattern

- **Orchestrator**: breaks a task into subtasks, delegates to workers, collects results.
- **Workers**: each compiled as a separate graph, called by orchestrator nodes.

```python
async def analyze_node(state: OrchestratorState) -> dict:
    result = await worker.ainvoke({"task": f"Analyze: {state['query']}"})
    return {"analysis": result["result"]}
```

Each worker has its own fresh context. One worker failing means you retry just that worker.

### Benefits vs one agent

| | One agent | Multi-agent |
|---|---|---|
| Prompt | One huge prompt | Small focused prompts |
| Context | Fills fast | Independent contexts |
| Failure | One failure = total failure | Isolated failures |

### When to parallelize

Two tasks with no dependency → run in parallel. Two tasks where B needs A's output → sequential.

### Production bugs to guard against

| Bug | Fix |
|---|---|
| No max_iterations guard | Track `attempts` in state, check in the edge function |
| Context explosion from tool results | Summarize results before appending |
| Conditional edge returns unknown string | Always have a default return case |
| Sync blocking call in async node | Use `async def` + `await` everywhere |
| Thread ID collision between users | Use `uuid4()` per conversation |
| Checkpoint storage grows unbounded | Redis TTL or a scheduled cleanup job |

### The one-liner to remember

> LangGraph models agents as directed graphs — nodes are Python functions, edges define routing, state is a TypedDict that travels through the graph. Conditional edges enable the ReAct loop: generate → check if done → retry retrieve if not. Checkpointing saves state after every node, enabling crash recovery and human-in-the-loop. In production always set max_iterations in state and guard against context explosion by summarizing large tool results.

---

## Resources

### Course
- [DeepLearning.AI — AI Agents in LangGraph](https://www.deeplearning.ai/short-courses/ai-agents-in-langgraph/) ← built around exactly this material

### Docs
- [LangGraph Docs](https://langchain-ai.github.io/langgraph/) ← start with the "Quickstart" and "Persistence" sections
- [LangGraph — Persistence / Checkpointing](https://langchain-ai.github.io/langgraph/concepts/persistence/)
- [LangGraph — Human-in-the-loop](https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/)

### Repo
- [langchain-ai/langgraph (GitHub)](https://github.com/langchain-ai/langgraph) ← check the `examples/` folder for runnable graphs

---

## Week 4 Deliverable

**Step up from Week 2.** Last week you wrote the agent loop by hand. This week you'll build it as a real graph.

Build a **stateful LangGraph agent** that:

1. Defines an `AgentState` **TypedDict** with at least one **reducer** field (e.g. `messages: Annotated[list, operator.add]`)
2. Has at least **2 nodes** wired with `add_node`
3. Uses a **conditional edge** to create a loop — a ReAct-style "retry if the answer isn't good enough" cycle
4. **Guards against infinite loops** — track `attempts` in state and stop at a max (no runaway loops)
5. Compiles with a **checkpointer** (`AsyncSqliteSaver` is fine) and runs with a `thread_id`

**Bonus challenge:** add `interrupt_before=[...]` to pause before one node, show a draft to the "human" (you, via terminal input), edit the state with `aupdate_state`, then resume with `ainvoke(None, config)`.

Submit in `submissions/your-name/` with a README that shows your graph's structure (nodes + edges) and 2 sample runs — one that finishes in a single pass, and one that triggers the retry loop.
