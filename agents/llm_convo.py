"""
llm_convo.py
────────────
Normal LLM Conversation Handler for TripOrchestrator.

Responsibilities
────────────────
1. Handles general conversation, greetings ("Hi", "Hello"), capability questions ("What can you do"),
   and casual Q&A dynamically using LLM (no static hardcoded replies).
2. Detects whether a user message requires multi-agent travel orchestration (weather, hotel, train, itinerary).
3. Provides streaming token generator for Streamlit's st.write_stream().
"""

import os
import asyncio
import queue
import threading
from typing import List, Dict, Generator

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from dotenv import load_dotenv

# Load environment
_env = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(_env if os.path.exists(_env) else None)

# Initialize LLM based on available API keys (same precedence as orchestra.py)
if os.getenv("GROQ_API_KEY"):
    from langchain_groq import ChatGroq
    LLM = ChatGroq(
        model="openai/gpt-oss-120b",
        temperature=0.7,
        groq_api_key=os.getenv("GROQ_API_KEY"),
    )
elif os.getenv("OPENAI_API_KEY"):
    from langchain_openai import ChatOpenAI
    LLM = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
elif os.getenv("GOOGLE_API_KEY"):
    from langchain_google_genai import ChatGoogleGenerativeAI
    LLM = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.7)
else:
    raise ValueError("llm_convo: No LLM API key found in environment variables.")

# System Prompt for normal conversation
SYSTEM_PROMPT = SystemMessage(content="""
You are Trippy — the friendly, intelligent conversational assistant for TripOrchestrator, an AI-powered travel planning suite.

Your Capabilities & Colleagues:
- 🌦️ Weather Agent   : Live weather forecasts and climate info
- 🗺️ Tour Guide (Trippy): Custom itineraries, sightseeing, and local attractions
- 🏨 Booking Agent    : Real-time hotel search and reservations on Booking.com
- 🚆 Transport Agent  : IRCTC train seat availability and route info

Instructions:
- Respond naturally, warmly, and concisely to greetings, questions about what you can do, general chit-chat, and travel inquiry introductions.
- Never give static or robotic repetitive responses. Keep every interaction fresh and engaging.
- When the user asks for specific travel plans, weather forecasts, hotel bookings, or train tickets, encourage them to specify their travel details (destination, dates, origin, guests) so our specialized agent team can execute them.
""")

# Keywords indicating travel sub-agent orchestration is needed
ORCHESTRATOR_KEYWORDS = [
    "weather", "forecast", "temperature", "climate", "rain",
    "hotel", "booking", "accommodation", "room", "stay", "resort", "motel",
    "train", "irctc", "ticket", "seat", "railway", "pnr", "berth", "sleeper",
    "itinerary", "places to visit", "sightseeing", "attractions", "tourist",
    "plan a trip", "plan my trip", "trip to", "travel to", "book hotel", "book train",
    "check-in", "check-out", "guests", "passengers",
]

def needs_orchestration(text: str) -> bool:
    """
    Evaluates whether the user input requires calling the multi-agent travel orchestrator.
    Returns True if travel planning, weather, hotel, train, or itinerary sub-agents are needed.
    Returns False for casual greetings, introduce requests, general questions, etc.
    """
    if not text or not text.strip():
        return False
    
    text_lower = text.lower().strip()
    
    # Fast check for simple greetings / capabilities prompts
    casual_exact = [
        "hi", "hi!", "hello", "hello!", "hey", "hey!", "hi there", "hello there",
        "what can you do", "what can you do?", "who are you", "who are you?",
        "help", "help me", "good morning", "good evening", "good afternoon",
        "thanks", "thank you", "bye", "goodbye"
    ]
    if text_lower in casual_exact:
        return False

    # Check for specific travel orchestration keywords
    return any(kw in text_lower for kw in ORCHESTRATOR_KEYWORDS)


def _build_messages(history: List[Dict], latest_prompt: str) -> List[BaseMessage]:
    """Convert Streamlit chat history dicts into LangChain message objects."""
    msgs: List[BaseMessage] = [SYSTEM_PROMPT]
    # Include up to last 6 chat history messages for context
    recent_history = history[-6:] if len(history) > 6 else history
    for m in recent_history:
        role = m.get("role")
        content = m.get("content", "")
        if role == "user":
            msgs.append(HumanMessage(content=content))
        elif role == "assistant":
            msgs.append(AIMessage(content=content))
    msgs.append(HumanMessage(content=latest_prompt))
    return msgs


def stream_normal_convo(history: List[Dict], user_message: str) -> Generator[str, None, None]:
    """
    Sync generator streaming token by token from LLM.
    Suitable for passing directly into Streamlit's st.write_stream().
    """
    token_q: queue.Queue = queue.Queue()
    messages = _build_messages(history, user_message)

    async def _async_stream():
        try:
            async for chunk in LLM.astream(messages):
                if chunk.content:
                    token_q.put(chunk.content)
        except Exception as exc:
            token_q.put(f"\n\n⚠️ {exc}")
        finally:
            token_q.put(None)  # Sentinel to mark end of stream

    def _worker():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_async_stream())
        finally:
            loop.close()

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()

    while True:
        token = token_q.get()
        if token is None:
            break
        yield token

    thread.join(timeout=5)
