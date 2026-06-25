# Stateful LangGraph Healthcare Research Agent

A local, fully offline healthcare research assistant built with LangGraph and Ollama.
Queries three free public APIs — no API key required.

---

## Graph Structure

```
START
  │
  ▼
┌─────────┐   tool calls?   ┌───────┐
│  agent  │────────────────▶│ tools │
│ (node 1)│                 │(node 2)│
└─────────┘◀────────────────└───────┘
     │         results loop back
     │ no tool calls
     ▼
┌──────────────┐   ⏸ interrupt_before (BONUS)
│ quality_check│
│   (node 3)   │
└──────────────┘
     │              │
   PASS or        RETRY
   max attempts   (attempts < MAX)
     │              │
     ▼              ▼
    END         ┌─────────┐
                │ reflect │
                │ (node 4)│
                └─────────┘
                     │
                     └──────▶ agent  (loops back)
```

### Nodes

| Node | Purpose |
|---|---|
| `agent` | Main LLM call (tools bound); produces tool calls or final answer |
| `tools` | Executes all tool calls, returns `ToolMessage` results |
| `quality_check` | Second LLM call reviews the answer — PASS or RETRY |
| `reflect` | Injects a retry instruction so the agent tries harder |

### Edges

| From | To | Condition |
|---|---|---|
| `START` | `agent` | always |
| `agent` | `tools` | last message has tool_calls |
| `agent` | `quality_check` | last message has no tool_calls |
| `tools` | `agent` | always (feed results back) |
| `quality_check` | `__end__` | verdict == PASS **or** attempts ≥ 3 |
| `quality_check` | `reflect` | verdict == RETRY and attempts < 3 |
| `reflect` | `agent` | always (retry cycle) |

---

## AgentState

```python
class AgentState(TypedDict):
    messages:        Annotated[list[BaseMessage], operator.add]  # reducer
    attempts:        int        # loop guard (max 3)
    quality_verdict: str        # "PASS" | "RETRY" | ""
    draft_answer:    str        # latest AI text (for human review)
```

`operator.add` means every node **appends** to `messages` — full history is preserved across the entire graph execution and across sessions (via the checkpointer).

---

## Requirements

```bash
pip install langgraph langchain-ollama langchain-core aiosqlite requests pydantic langgraph-checkpoint-sqlite
```

Pull a model that supports tool-calling:

```bash
ollama pull llama3.2        
```

Run:

```bash
python healthcare_langgraph_agent.py
```

No API key needed. Ollama must be running locally (`ollama serve`).

To use a different model, change `MODEL_NAME` at the top of the file:

```python
MODEL_NAME = "llama3.1"   # or "mistral-nemo", "qwen2.5", etc.
```

---

## Sample Run 1 — Single-Pass (Global COVID Stats)

**Query:** *"What are the current global COVID-19 statistics?"*  
**Thread:** `thread-001`

```
============================================================
QUERY  : What are the current global COVID-19 statistics?
THREAD : thread-001
============================================================

[agent_node] attempt=0
  tool_calls=True, content_len=0
  [stream] node=agent

  [tool_node] -> get_disease_stats({'country': 'global'})
  [tool_node] <- COVID-19 Statistics - Global
    Total Cases    : 704,753,890
    Deaths         : 7,010,681
    ...
  [stream] node=tools

[agent_node] attempt=0
  tool_calls=False, content_len=598
  [stream] node=agent

[quality_check_node] reviewing answer (598 chars)...
  verdict=PASS — Answer includes real statistics and an appropriate disclaimer.
  [stream] node=quality_check

────────────────────────────────────────────────────────────
FINAL ANSWER (Run 1):
As of the latest data from disease.sh, the global COVID-19 statistics are:

  Total Cases  : 704,753,890
  Deaths       : 7,010,681
  Recovered    : 675,619,811
  Active Cases : 22,123,398

This information is for educational purposes only.
Please consult a healthcare professional for medical advice.
```

**Flow:** `agent → tools → agent → quality_check → END`  
Single-pass, no retry. `attempts = 1`.

---

## Sample Run 2 — Retry Cycle (Multi-Tool Query)

**Query:** *"Tell me about metformin and find 2 active clinical trials for diabetes."*  
**Thread:** `thread-002`

```
============================================================
QUERY  : Tell me about metformin... Also find 2 active clinical trials for diabetes.
THREAD : thread-002
============================================================

[agent_node] attempt=0
  tool_calls=True, content_len=0

  [tool_node] -> get_drug_info({'drug_name': 'metformin'})
  [tool_node] <- Drug Information - METFORMIN HYDROCHLORIDE
    Brand Name(s) : Glucophage, Fortamet
    Indications   : Indicated for type 2 diabetes management...
    Warnings      : Risk of lactic acidosis...

  [tool_node] -> find_clinical_trials({'condition': 'diabetes', 'max_results': 2})
  [tool_node] <- Clinical Trials for 'diabetes' - showing 2 of 7,842 recruiting:
    [1] Continuous Glucose Monitoring Study — NCT05812234
    [2] Tirzepatide vs Semaglutide — NCT05901831

[agent_node] attempt=0
  tool_calls=False, content_len=1187

[quality_check_node] reviewing answer (1187 chars)...
  verdict=PASS — Contains verified drug data from OpenFDA and 2 trial entries.

────────────────────────────────────────────────────────────
FINAL ANSWER (Run 2):
Metformin (brand: Glucophage) is used for type 2 diabetes management.
Key warning: risk of lactic acidosis — avoid in kidney impairment.

Active Diabetes Trials:
  [1] Continuous Glucose Monitoring in Type 2 Diabetes
      NCT05812234 · Phase 3 · Dexcom
      https://clinicaltrials.gov/study/NCT05812234
  [2] Tirzepatide vs Semaglutide Head-to-Head Study
      NCT05901831 · Phase 4 · Eli Lilly
      https://clinicaltrials.gov/study/NCT05901831
```

**Flow:** Two tools called in one agent turn → single-pass. `attempts = 1`.

**What a retry looks like** — if the model answers without calling tools, quality_check returns RETRY and the graph loops:

```
[quality_check_node] verdict=RETRY — Answer contains no tool data; tools were not called.

[reflect_node] injecting retry instruction (attempt 1)
[agent_node] attempt=1
  tool_calls=True   ← agent now calls the tools
  ...
[quality_check_node] verdict=PASS → END
```

---

##  Bonus: Human-in-the-Loop

Compiled with `interrupt_before=["quality_check"]`. Before the reviewer runs, you see the draft:

```
PAUSED — Draft answer ready for human review:
──────────────────────────────────────────────────
There are 3 recruiting Alzheimer's trials...
[NCT05312281] — Phase 3 — Lecanemab extension study
──────────────────────────────────────────────────

[Human] Press ENTER to approve, or type an edit instruction:
> Add a note about eligibility criteria

  [human] State updated with reviewer note.
  [stream] node=quality_check → PASS → END
```

The human's note is injected via `aupdate_state(as_node="agent")` and included when quality_check evaluates the answer.

---

## Files

```
healthcare_langgraph_agent.py   ← main agent + graph
healthcare_checkpoints.db       ← auto-created SQLite (LangGraph state)
README.md                       ← this file
```

---

## Key Concepts

- **`Annotated[list, operator.add]`** — reducer that appends messages instead of replacing
- **`add_node` × 4** — agent, tools, quality_check, reflect
- **Conditional edges** — `route_after_agent` and `route_after_quality` create the ReAct + retry loop
- **`attempts` counter** — guards against infinite loops (cap = 3)
- **`AsyncSqliteSaver`** — checkpointer persists state to SQLite; resume any session by thread_id
- **`interrupt_before=["quality_check"]`** — pauses graph for human review 
- **`aupdate_state`** — injects human edits into live graph state 
- **`astream(None, config)`** — resumes from interrupt point 
- **`ChatOllama`** — local LLM via Ollama, zero API cost, works offline
