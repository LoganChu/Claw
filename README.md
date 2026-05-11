# Claw

> 24/7 autonomous productivity tracking agent system built on **NeMo Claw** (NVIDIA NeMo Agent Toolkit) and **LangGraph**.

Claw runs a team of persistent monitor agents that watch your work signals around the clock, then feeds the collected data into a LangGraph analysis pipeline to produce an end-of-day productivity report — learning your patterns over time.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              Persistent Monitor Agents (24/7)                   │
│                                                                 │
│  GitMonitorAgent     FocusTrackerAgent   GoalCheckAgent         │
│  (commits, branches) (active window)     (goal progress)        │
└──────────────────────────┬──────────────────────────────────────┘
                           │ event log (SQLite)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              LangGraph Analysis Pipeline                        │
│  (wrapped by NeMo Agent Toolkit for observability + eval)       │
│                                                                 │
│  Ingest → Classify → [retry? ↩] → GoalTracker                  │
│         → PatternAnalyzer → InsightGenerator → ReportWriter     │
└──────────────────────────┬──────────────────────────────────────┘
                           │ MCP tools (GitHub, Calendar, Slack)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Memory + Output                                                │
│  SQLite (event log + daily summaries) · ChromaDB (vectors)      │
│  Markdown reports · NeMo eval (predicted vs. self-rated score)  │
└─────────────────────────────────────────────────────────────────┘
```

## Agentic Patterns Demonstrated

| Pattern | Where |
|---------|-------|
| Orchestrator + workers | Main loop coordinates 3 monitor agents |
| Parallel execution | All monitor agents run concurrently via `asyncio` |
| Iterative refinement | LangGraph cycles back to ingest if confidence < 0.5 |
| Long-term memory | SQLite history + ChromaDB vector store |
| Tool use (MCP) | NeMo Agent Toolkit MCP tools for GitHub/Calendar/Slack |
| Safety guardrails | Privacy filter scrubs secrets before DB storage |
| Observability | NeMo Agent Toolkit profiles every pipeline run |
| Evaluation system | Predicted score vs. self-rating correlation tracking |
| Continuous learning | NeMo prompt optimizer tunes classification prompts |

---

## Quick Start

### 1. Set up environment

```bash
conda create -n claw python=3.12 -y
conda activate claw
pip install -e ".[dev]"
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — at minimum set OPENAI_API_KEY (or NVIDIA_API_KEY for NIM)
```

### 3. Run

```bash
# Start all monitor agents + scheduled analysis
conda activate claw && python main.py

# Run analysis right now and print the report
python main.py --report

# Report for a specific date
python main.py --report --date 2026-05-09

# Rate a session (1-5) to feed the evaluation system
python -c "
import asyncio
from claw.eval import record_self_rating
asyncio.run(record_self_rating('2026-05-09', 4))
"

# Check evaluation accuracy over the last 30 days
python -c "
import asyncio, json
from claw.eval import compute_accuracy_report
print(json.dumps(asyncio.run(compute_accuracy_report()), indent=2))
"
```

### 4. NeMo Agent Toolkit workflow

```bash
# Run via nat CLI (adds observability + evaluation UI)
nat run --config_file=src/claw/configs/config.yml \
  --input "Analyze my productivity for today"

# Start API server
nat serve --config_file=src/claw/configs/config.yml

# Evaluate with NeMo eval system
nat eval --config_file=src/claw/configs/config.yml
```

---

## Tests

```bash
pytest tests/ -v --cov=src/claw --cov-report=term-missing
```

---

## Project Structure

```
Claw/
├── src/claw/
│   ├── agents/          # Persistent monitor agents (git, focus, goal)
│   ├── pipeline/        # LangGraph analysis graph + state + nodes
│   ├── database/        # SQLite schema and async ORM helpers
│   ├── memory/          # ChromaDB vector store for long-term memory
│   ├── safety/          # Privacy filter guardrail
│   ├── tools/           # NeMo Agent Toolkit registered tools
│   ├── eval/            # Predicted vs. self-rated accuracy tracking
│   └── configs/         # NeMo Agent Toolkit workflow YAML
├── tests/
├── main.py              # Entry point
├── pyproject.toml
└── .env.example
```

---

## Roadmap

- [ ] Phase 1 (next): CalendarAgent (Google Calendar MCP) + CommunicationAgent (Slack)
- [ ] Phase 2: A2A protocol — monitor agents publish events via NeMo A2A server
- [ ] Phase 3: Weekly trend charts (matplotlib / plotly)
- [ ] Phase 4: NeMo prompt optimizer integration for classification tuning
- [ ] Phase 5: Live dashboard (Textual TUI or Streamlit)