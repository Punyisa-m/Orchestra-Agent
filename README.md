# 🎼 Orchestra-Agent

> **Autonomous AI Task Management System** — multi-node LangGraph pipeline
> that breaks natural-language requests into atomic sub-tasks and assigns
> them bias-free to the best-fit employees via a live Skill Matrix.

---

## Architecture

```
User Input (NL)
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│              LangGraph StateGraph                        │
│                                                          │
│  ┌──────────┐   ┌─────────────┐   ┌───────────┐         │
│  │ PLANNER  │──►│ MATCHMAKER  │──►│ SCHEDULER │──► ...  │
│  │ (LLM)   │   │ (Pure algo) │   │ (Deadline)│         │
│  └──────────┘   └─────────────┘   └───────────┘         │
│                                          │               │
│                                          ▼               │
│                                    ┌──────────┐          │
│                                    │ REPORTER │          │
│                                    │ (DB+MD)  │          │
│                                    └──────────┘          │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
                  SQLite (orchestra.db)
                         │
                         ▼
              Streamlit Dashboard (app.py)
```

---

## File Structure

```
orchestra_agent/
├── database.py      # Schema, Pydantic models, all DB operations
├── graph.py         # LangGraph nodes + graph compilation
├── app.py           # Streamlit management dashboard
├── requirements.txt # Python dependencies
└── README.md
```

---

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2a. Use OpenAI (recommended for best results)
```bash
export OPENAI_API_KEY="sk-..."
```

### 2b. Use Ollama (local, free)
```bash
# Install Ollama: https://ollama.com
ollama pull llama3.1
ollama serve           # keep this running in background
```

### 3. Launch the dashboard
```bash
streamlit run app.py
```

Open **http://localhost:8501** in your browser.

---

## How the Bias-Free Matchmaker Works

```
match_score = (skill_score/10 × 0.5  +  coverage × 0.3)
              × (1 − load_fraction × 0.4)
```

| Component      | Weight | Description                                  |
|----------------|--------|----------------------------------------------|
| Skill score    | 50%    | Mean proficiency on required skills (0-10)   |
| Coverage       | 30%    | Fraction of required skills the person has   |
| Load penalty   | 40%    | Penalises busy employees, not blocks them    |

**No LLM involvement** in assignment logic → zero hallucination, zero bias.

---

## Features

- 🤖 **4-node LangGraph pipeline**: Planner → Matchmaker → Scheduler → Reporter
- 📊 **Live analytics**: Workload balance score, Est vs Actual hours chart
- 🗺️ **Task Assignment Map**: filterable full log with status tracking
- 🧠 **Skill Matrix heatmap**: proficiency across all employees × skills
- 🔄 **Demo reset & simulation**: instantly simulate actual hours for analytics
- 🔌 **Dual LLM support**: OpenAI GPT-4o-mini or Ollama Llama 3.1
