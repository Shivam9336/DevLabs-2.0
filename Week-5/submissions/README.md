# Submissions — Week 5

## Checklist

- [ ] At least 2 worker agents, each compiled as its **own separate graph** with its own state schema
- [ ] An orchestrator (fixed plan) or supervisor (dynamic routing) coordinates the workers
- [ ] At least 2 independent workers run in parallel with `asyncio.gather` (fan-out), then combine (fan-in)
- [ ] State is isolated — orchestrator passes each worker only what it needs, lifts only the final output back
- [ ] Failure guard — `return_exceptions=True` or per-worker try/except so one worker failing doesn't kill the run
- [ ] README shows agent topology (who calls whom, what runs in parallel) + 2 sample runs (one happy path, one where a worker fails and recovers)

## Folder Structure

```
submissions/your-name/
├── agents.py
├── requirements.txt
└── README.md    ← agent topology + 2 sample runs (happy path + worker-failure recovery)
```
