# 🧳 TripOrchestrator: Multi-Agent Autonomous Tour & Travel System

> **Built With:** LangChain, LangGraph, Python, Streamlit, OpenWeather API, Playwright, Selenium, ChatGroq / OpenAI / Google Gemini  

---

## 📌 Executive Summary

Planning multi-city travel involves juggling complex variables: checking live weather forecasts, discovering local attractions, selecting hotels, and searching train availability. Single-prompt AI solutions frequently hallucinate details, misuse APIs, or perform actions without user consent.

**TripOrchestrator** addresses these limitations using a **Hierarchical Multi-Agent Architecture** powered by **LangGraph** and **Streamlit**. By decoupling responsibilities into specialized sub-agents (Weather, Tour Guide, Hotel Booking, Train Transport) and employing dynamic LLM front-door conversation routing, the system automates end-to-end travel planning—from itinerary drafting to hotel and transit lookup—with real-time UI agent connection progress tracking.

---

## 📂 Repository Structure

```text
triporchestrator/
├── README.md                       ← Comprehensive project overview
├── main.py                         ← Streamlit launch forwarding entry point
├── pyproject.toml / requirements.txt ← Project dependencies
├── src/
│   └── triporchestrator/
│       └── app.py                  ← Streamlit Web UI application & resource caching
├── agents/
│   ├── llm_convo.py                 ← Front-door dynamic LLM chat & orchestration router
│   ├── orchestra.py                 ← LangGraph supervisor & workflow graph compiler
│   ├── guide.py                     ← Tour Guide (Trippy) itinerary & attraction agent
│   ├── weather_agent.py             ← OpenWeather API forecast agent
│   ├── booking.py                   ← Playwright automation agent for Booking.com
│   └── transport.py                 ← Selenium automation agent for IRCTC train availability
└── hotel_playwright_data/          ← Persistent browser context data
```

---

## 🛠 Architecture & Agent Workflow

The engine models agent states using a unified `TypedDict` and coordinates workflow transitions via a LangGraph **StateGraph**.

```text
                           +-------------------------------+
                           |    Supervisor Orchestrator    |
                           +---------------+---------------+
                                           |
         +---------------------------------+---------------------------------+
         |                                 |                                 |
+--------v-------+                +--------v-------+                +--------v-------+
|   Tour Guide   |                | Weather Agent  |                | Transport Agent|
| (Trippy Agent) |                +--------+-------+                +--------+-------+
+--------+-------+                         |                                 |
         |                         +-------v-------+                         |
         +------------------------>| Check Weather |                         |
                                   +-------+-------+                         |
                                           |                                 v
                                           v                        +----------------+
                                   +---------------+                | Booking Agent  |
                                   | Hotel Search  |<---------------+  (Booking.com) |
                                   +---------------+                +----------------+
```

### 🤖 Agent Roles & Responsibilities

| Agent | File | Primary Responsibility |
| :--- | :--- | :--- |
| **Front-Door LLM Chat** | `agents/llm_convo.py` | Handles general Q&A, greetings ("Hi"), and capability questions dynamically using LLM, and evaluates when multi-agent orchestration is needed. |
| **Supervisor Orchestrator** | `agents/orchestra.py` | LangGraph supervisor routing travel planning state across specialized sub-agents until requests are complete. |
| **Tour Guide (Trippy)** | `agents/guide.py` | Energetic itinerary planner providing daily schedules, attraction recommendations, and local travel advice. |
| **Weather Agent** | `agents/weather_agent.py` | Queries live weather forecasts for destination cities. |
| **Booking Agent** | `agents/booking.py` | Automated Playwright browser engine for real-time accommodation search on Booking.com. |
| **Transport Agent** | `agents/transport.py` | Automated Selenium browser engine for IRCTC train seat availability and route searches. |

---

## ⚙️ Key Technical Features

* **Dynamic Front-Door Conversation Routing (`llm_convo.py`):** Differentiates casual greetings ("Hi", "Hello, What can you do") from travel requests, responding dynamically without static or repetitive templates.
* **Sub-5ms UI Load Performance (`@st.cache_resource`):** Heavy agent modules, LLM models, and LangGraph workflows are cached in memory on app startup, eliminating rerun latency during interaction.
* **Real-time Web UI Connection Progress:** Streamlit `st.status` displays step-by-step progress cards (`Connected with weather agent for weather report`, `Weather report Generated`) with glowing CSS loading pulse animations.
* **Autonomous Web Browser Agents:** Playwright and Selenium headless/headful automation for real-time hotel and train ticket checks.

---

## ⚡ Quickstart & Setup Guide

### 1. Prerequisites
* **Python 3.10+**
* API Key for **Groq**, **OpenAI**, or **Google Gemini**
* OpenWeatherMap API Key (optional)

### 2. Environment Setup

```bash
# Clone repository
git clone https://github.com/dineshp0103/triporchestrator.git
cd triporchestrator

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Add API Keys
Create or update `agents/.env`:

```env
GROQ_API_KEY="your_groq_api_key"
OPENAI_API_KEY="your_openai_api_key"
GOOGLE_API_KEY="your_google_api_key"
```

### 4. Launch Application

```bash
streamlit run main.py
```

Or open directly via python:

```bash
python main.py
```

---

## 🌐 Deploy to Streamlit Community Cloud

1. Push code to your GitHub repository: `https://github.com/dineshp0103/triporchestrator`
2. Open **[share.streamlit.io](https://share.streamlit.io)** and click **New app**.
3. Select Repository `dineshp0103/triporchestrator`, Branch `main`, and Main file path `main.py`.
4. Under **Advanced settings... -> Secrets**, configure your API keys (`GROQ_API_KEY`, `OPENAI_API_KEY`, etc.).
5. Click **Deploy!**