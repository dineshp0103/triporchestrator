# 🧳 TripOrchestrator: Multi-Agent Autonomous Tour & Travel System

> **Hackathon Track:** AI Agents & Autonomous Workflows  
> **Built With:** LangChain, LangGraph, Python, Streamlit, OpenWeather API, Geopy, ChatGroq / OpenAI  

---

## 📌 Executive Summary

Planning multi-city travel involves juggling complex variables: checking live weather forecasts, calculating physical distances, selecting accommodation, booking transit, and handling payments securely. Single-prompt AI solutions frequently hallucinate details, misuse APIs, or perform actions without user consent.

**TripOrchestrator** addresses these limitations using a **Hierarchical Multi-Agent Architecture** powered by **LangGraph**. By decoupling responsibilities into specialized sub-agents and enforcing **Human-in-the-Loop (HITL)** checkpoints, the system automates end-to-end travel planning—from itinerary drafting to checkout preparation—while keeping users in total control before any payment execution.

---

## 📂 Repository Structure

```text
triporchestrator/
├── README.md                 ← judges read this first
├── requirements.txt
├── .env.example              ← names of keys needed (OPENWEATHERMAP_API_KEY, GROQ_API_KEY), never real keys
├── app.py                    ← Streamlit UI entry point (streamlit run app.py)
├── run.py                    ← single entry point: python run.py --query "Plan 2-day trip to Tirupati"
├── agents/
│   ├── tour_guide.py          ← geocodes landmarks & parses locations
│   ├── weather.py             ← queries OpenWeather API (v2.5/4.0)
│   ├── transport.py           ← checks transit & fare options
│   ├── booking.py             ← handles hotel reservations
│   └── orchestrator.py        ← main supervisor agent & human-in-the-loop (HITL) payment flow
├── eval/
│   ├── testset.csv            ← 20 hardcoded queries + expected agent outputs
│   ├── run_eval.py            ← evaluates confidence thresholds & run traces
│   └── results.md             ← confidence score logs & accuracy metrics
└── runs/                      ← execution decision traces & state checkpointer logs
```

## 🛠 Architecture & Agent Workflow

The engine models agent states using a unified `TypedDict` and coordinates workflow transitions via a **StateGraph**.

```text
                          +-------------------------------+
                          |    Supervisor Orchestrator    |
                          +---------------+---------------+
                                          |
        +---------------------------------+---------------------------------+
        |                                 |                                 |
+-------v-------+                 +-------v-------+                 +-------v-------+
|  Tour Guide   |                 | Weather Agent |                 |Transport Agent|
|     Agent     |                 +-------+-------+                 +-------+-------+
+-------+-------+                         |                                 |
        |                         +-------v-------+                         |
        +------------------------>| Check Weather |                         |
                                  |     Gate      |                         |
                                  +-------+-------+                         |
                                          | (Suitable)                      |
                                          v                                 v
                                  +---------------+                 +---------------+
                                  | Booking Agent |<----------------+   Execution   |
                                  +-------+-------+                 +---------------+
                                          |
                                          v
                                 🛑 [HITL INTERRUPT]
                                  (Human Approval)
                                          |
                                          v (Approved)
                                +-------------------+
                                |     Booking       |
                                |   Orchestrator    |
                                +-------------------+

```

### 🤖 Agent Roles & Responsibilities

| Agent | File | Primary Responsibility |
| :--- | :--- | :--- |
| **Supervisor Orchestrator** | `agents/orchestrator.py` | Receives global user state, handles task delegation, and synthesizes sub-agent outputs. |
| **Tour Guide Agent** | `agents/tour_guide.py` | Extracts tourist attraction metadata, geocodes locations via `geopy`/Nominatim, and determines if overnight stay is required (`is_far_destination`). |
| **Weather Agent** | `agents/weather.py` | Queries OpenWeather API endpoints (2.5/4.0 `/daily`) for 5-day forecasts and checks weather safety constraints. |
| **Transport Agent** | `agents/transport.py` | Evaluates travel distance and identifies transit choices (train, flight, cab options). |
| **Booking Agent** | `agents/booking.py` | Generates lodging and room reservations if `is_far_destination == True`. |


## ⚙️ Key Technical Features

* **Deterministic State Routing (LangGraph):** Replaces volatile single-prompt loops with structured graphs, state transitions, and conditional edges.
* **Human-in-the-Loop (HITL) Guardrails:** Pauses graph execution right before financial operations using LangGraph `interrupt()` state checkpointers.
* **Real-time Geocoding & Weather Integration:** Dynamically translates landmark and city names into coordinates using `geopy` before querying live OpenWeather APIs.
* **Evaluation Framework & Trace Logging:** Evaluates agent confidence thresholds and saves execution decision traces across test query sets inside `eval/` and `runs/`.
* **Interactive Streamlit Interface:** Provides a dynamic web UI that streams multi-agent decision steps live and displays an interactive approval card when HITL checkpoints trigger.

## ⚡ Quickstart & Setup Guide

### 1. Prerequisites
* **Python 3.10+**
* OpenWeatherMap API Key
* Groq API Key or OpenAI API Key

### 2. Environment Setup

```bash
# Clone repository
git clone [https://github.com/your-username/triporchestrator.git](https://github.com/your-username/triporchestrator.git)
cd triporchestrator

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

OPENWEATHERMAP_API_KEY="your_openweather_api_key"
GROQ_API_KEY="your_groq_api_key"
OPENAI_API_KEY="your_openai_api_key"

streamlit run app.py

python run.py --query "Plan a 2-day trip to Tirupati from Visakhapatnam"

python eval/run_eval.py
```