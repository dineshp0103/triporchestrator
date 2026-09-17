import os
import time
import asyncio
from contextvars import ContextVar
from typing import Annotated, Literal, Optional, TypedDict
from pydantic import BaseModel
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_classic.agents import tool
from dotenv import load_dotenv

_UI_WRITER: ContextVar = ContextVar("ui_writer", default=None)


def _stream_event(event: dict) -> None:
    """Push a live thought/timer event to the UI when the graph is streaming."""
    payload = {**event, "ts": event.get("ts", time.time())}
    writer = _UI_WRITER.get()
    if writer is not None:
        try:
            writer(payload)
            return
        except Exception:
            pass
    try:
        from langgraph.config import get_stream_writer

        get_stream_writer()(payload)
    except Exception:
        pass


def _mark_flow_complete(state: dict, agent_name: str) -> list:
    agent_flow = list(state.get("agent_flow") or [])
    for entry in reversed(agent_flow):
        if entry.get("agent") == agent_name and entry.get("status") in ("pending", "active"):
            entry["status"] = "completed"
            entry["end_time"] = time.time()
            break
    return agent_flow


def _mark_flow_active(state: dict, agent_name: str) -> list:
    agent_flow = list(state.get("agent_flow") or [])
    now = time.time()
    for entry in reversed(agent_flow):
        if entry.get("agent") == agent_name and entry.get("status") in ("pending", "active"):
            entry["status"] = "active"
            entry["start_time"] = now
            break
    return agent_flow

print("All Modules are imported...")

env_file_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_file_path):
    load_dotenv(env_file_path)
else:
    load_dotenv()

# Set orchestrator LLM dynamically based on available API key
if os.getenv("GROQ_API_KEY"):
    from langchain_groq import ChatGroq
    ORCHESTRATOR_LLM = ChatGroq(model="openai/gpt-oss-120b", temperature=0, groq_api_key=os.getenv("GROQ_API_KEY"))
elif os.getenv("OPENAI_API_KEY"):
    from langchain_openai import ChatOpenAI
    ORCHESTRATOR_LLM = ChatOpenAI(model="gpt-4o-mini", temperature=0)
elif os.getenv("GOOGLE_API_KEY"):
    from langchain_google_genai import ChatGoogleGenerativeAI
    ORCHESTRATOR_LLM = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
else:
    raise ValueError("No valid API key found in environment variables.")

# ---------------------------------------------------------------------------
# 1. Import Sub-Agent Modules / Implementations
# ---------------------------------------------------------------------------

print("LLM was acessed...")

# ---------------------------------------------------------------------------
# 2. Shared Graph State Definition
# ---------------------------------------------------------------------------
class OrchestratorState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    next: str
    direct_reply: Optional[str]
    reasoning: Optional[str]
    current_step: int
    step_timestamps: dict
    agent_flow: list

# ---------------------------------------------------------------------------
# 3. Initialize Instantiated Sub-Agents
# ---------------------------------------------------------------------------
try:
    from weather_agent import weather_agent
    from guide import tour_guide_agent
    from booking import AccommodationAgentModule
    from transport import IRCTCTransportAgentModule
except ImportError:
    from agents.weather_agent import weather_agent
    from agents.guide import tour_guide_agent
    from agents.booking import AccommodationAgentModule
    from agents.transport import IRCTCTransportAgentModule

print("All Agents are imported...")

weather_executor = weather_agent()
booking_module = AccommodationAgentModule()
transport_module = IRCTCTransportAgentModule()

print("Agents was initiated...")

# ---------------------------------------------------------------------------
# 4. Node Definitions Wrapping Sub-Agents
# ---------------------------------------------------------------------------
def weather_node(state: OrchestratorState, writer=None):
    _tok = _UI_WRITER.set(writer) if writer is not None else None
    try:
        agent_flow = _mark_flow_active(state, "Weather")
        _stream_event({
            "type": "agent_start",
            "agent": "Weather",
            "text": "Connected with the weather agent. Fetching a live forecast…",
        })
        latest_user_input = state["messages"][-1].content
        _stream_event({
            "type": "thought",
            "agent": "Weather",
            "text": "Calling weather tools for the requested destination.",
        })
        try:
            response = weather_executor.invoke({"input": latest_user_input})
            output = response["output"]
            _stream_event({"type": "thought", "agent": "Weather", "text": "Weather report generated."})
            return {
                "messages": [HumanMessage(content=f"[Weather Agent Response]: {output}")],
                "agent_flow": _mark_flow_complete({"agent_flow": agent_flow}, "Weather"),
            }
        finally:
            _stream_event({"type": "agent_end", "agent": "Weather"})
    finally:
        if _tok is not None:
            _UI_WRITER.reset(_tok)


def tour_guide_node(state: OrchestratorState, writer=None):
    _tok = _UI_WRITER.set(writer) if writer is not None else None
    try:
        agent_flow = _mark_flow_active(state, "TourGuide")
        _stream_event({
            "type": "agent_start",
            "agent": "TourGuide",
            "text": "Connected with the tour guide agent for itinerary recommendations…",
        })
        _stream_event({
            "type": "thought",
            "agent": "TourGuide",
            "text": "Trippy is drafting sights, pacing, and local tips.",
        })
        try:
            response = tour_guide_agent.invoke(state)
            _stream_event({"type": "thought", "agent": "TourGuide", "text": "Tour guide itinerary generated."})
            return {
                "messages": [response["messages"][-1]],
                "agent_flow": _mark_flow_complete({"agent_flow": agent_flow}, "TourGuide"),
            }
        finally:
            _stream_event({"type": "agent_end", "agent": "TourGuide"})
    finally:
        if _tok is not None:
            _UI_WRITER.reset(_tok)


async def booking_node(state: OrchestratorState, writer=None):
    _tok = _UI_WRITER.set(writer) if writer is not None else None
    try:
        agent_flow = _mark_flow_active(state, "Booking")
        _stream_event({
            "type": "agent_start",
            "agent": "Booking",
            "text": "Connected with the booking agent. Searching accommodations…",
        })
        latest_user_input = state["messages"][-1].content
        _stream_event({
            "type": "thought",
            "agent": "Booking",
            "text": "Opening Booking.com tools and gathering stay options.",
        })
        try:
            response = await booking_module.executor.ainvoke({"input": latest_user_input})
            _stream_event({"type": "thought", "agent": "Booking", "text": "Hotel booking options generated."})
            return {
                "messages": [HumanMessage(content=f"[Booking Agent Response]: {response['output']}")],
                "agent_flow": _mark_flow_complete({"agent_flow": agent_flow}, "Booking"),
            }
        finally:
            _stream_event({"type": "agent_end", "agent": "Booking"})
    finally:
        if _tok is not None:
            _UI_WRITER.reset(_tok)


def transport_node(state: OrchestratorState, writer=None):
    _tok = _UI_WRITER.set(writer) if writer is not None else None
    try:
        agent_flow = _mark_flow_active(state, "Transport")
        _stream_event({
            "type": "agent_start",
            "agent": "Transport",
            "text": "Connected with the transport agent to check IRCTC availability…",
        })
        latest_user_input = state["messages"][-1].content
        _stream_event({
            "type": "thought",
            "agent": "Transport",
            "text": "Querying train search tools for seats and schedules.",
        })
        try:
            response = transport_module.executor.invoke({"input": latest_user_input})
            _stream_event({"type": "thought", "agent": "Transport", "text": "Transport availability report generated."})
            return {
                "messages": [HumanMessage(content=f"[Transport Agent Response]: {response['output']}")],
                "agent_flow": _mark_flow_complete({"agent_flow": agent_flow}, "Transport"),
            }
        finally:
            _stream_event({"type": "agent_end", "agent": "Transport"})
    finally:
        if _tok is not None:
            _UI_WRITER.reset(_tok)

# ---------------------------------------------------------------------------
# 5. Supervisor Router Node Logic
# ---------------------------------------------------------------------------
class RouteResponse(BaseModel):
    next: Literal["Weather", "TourGuide", "Booking", "Transport", "FINISH"]
    direct_reply: Optional[str] = None
    reasoning: str = ""  # Explanation of routing decision

SUPERVISOR_SYSTEM_PROMPT = """
You are the Master Travel Orchestrator — an AI assistant managing a team of specialized travel sub-agents.

Sub-Agents & Responsibilities:
- Weather   : Real-time weather forecasts and climate checks for destination cities.
- TourGuide : Itineraries, sightseeing recommendations, local attractions, travel advice.
- Booking   : Hotel, accommodation, and stay reservations via Booking.com.
- Transport : Train and inter-city transport searches via IRCTC.
- FINISH    : Use when all user requests have been fulfilled OR when the query is casual /
              conversational (greetings, introductions, thanks, general questions not related
              to travel planning).  In that case populate `direct_reply` with a friendly
              response and set next = FINISH.

Rules:
1. For greetings or non-travel questions, set next=FINISH and write a helpful reply in direct_reply.
2. For travel queries, route to the appropriate agent and leave direct_reply empty.
3. Once all parts of a travel request are fulfilled, set next=FINISH.

IMPORTANT: When making routing decisions, you MUST provide clear reasoning explaining:
- What aspects of the user's request triggered this routing choice
- Which specific keywords or intents were identified
- Why this agent is the appropriate choice

Your reasoning should be concise (1-2 sentences) and specific to this request.
"""

# Keywords that signal a travel-planning intent
_TRAVEL_KEYWORDS = [
    "weather", "forecast", "temperature", "climate",
    "hotel", "booking", "accommodation", "room", "stay",
    "train", "transport", "irctc", "ticket", "seat",
    "itinerary", "places", "visit", "trip", "tour", "travel",
    "plan", "flight", "guide", "tourist", "sightseeing",
]

def _is_travel_query(text: str) -> bool:
    """Quick heuristic — returns True if the message looks like a travel request."""
    lower = text.lower()
    return any(kw in lower for kw in _TRAVEL_KEYWORDS)


def supervisor_node(state: OrchestratorState, writer=None):
    _tok = _UI_WRITER.set(writer) if writer is not None else None
    try:
        last_user_msg = next(
            (m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
            ""
        )

        current_step = state.get("current_step", 0) + 1
        step_timestamps = dict(state.get("step_timestamps") or {})
        step_timestamps[current_step] = time.time()
        agent_flow = list(state.get("agent_flow") or [])

        _stream_event({
            "type": "agent_start",
            "agent": "Supervisor",
            "text": "Orchestrator is analyzing the request and choosing the next specialist…",
            "step": current_step,
        })

        try:
            if not _is_travel_query(last_user_msg):
                _stream_event({
                    "type": "thought",
                    "agent": "Supervisor",
                    "text": "This does not look like a travel-planning task. Drafting a direct reply.",
                    "step": current_step,
                })
                messages = [
                    SystemMessage(content="You are the Master Travel Orchestrator. Respond warmly and helpfully to general questions or greetings, explaining how your team (Weather, Tour Guide, Booking, Transport) can help plan trips when ready.")
                ] + state["messages"]
                reply_msg = ORCHESTRATOR_LLM.invoke(messages)
                reasoning = "Non-travel query detected. Providing direct conversational response."
                _stream_event({
                    "type": "thought",
                    "agent": "Supervisor",
                    "text": reasoning,
                    "next": "FINISH",
                    "step": current_step,
                })
                return {
                    "next": "FINISH",
                    "direct_reply": reply_msg.content,
                    "reasoning": reasoning,
                    "current_step": current_step,
                    "step_timestamps": step_timestamps,
                }

            _stream_event({
                "type": "thought",
                "agent": "Supervisor",
                "text": "Travel intent detected. Routing to the best specialist agent.",
                "step": current_step,
            })
            messages = [SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT)] + state["messages"]
            structured_llm = ORCHESTRATOR_LLM.with_structured_output(RouteResponse)
            response = structured_llm.invoke(messages)

            reasoning = response.reasoning if response.reasoning else f"Routing to {response.next} agent to handle the request."

            if response.next != "FINISH":
                agent_flow.append({
                    "step": current_step,
                    "agent": response.next,
                    "status": "pending",
                    "reasoning": reasoning,
                    "start_time": None,
                })
                _stream_event({
                    "type": "thought",
                    "agent": "Supervisor",
                    "text": reasoning,
                    "next": response.next,
                    "step": current_step,
                })
            else:
                _stream_event({
                    "type": "thought",
                    "agent": "Supervisor",
                    "text": reasoning or "All requested work looks complete. Wrapping up.",
                    "next": "FINISH",
                    "step": current_step,
                })

            return {
                "next": response.next,
                "direct_reply": response.direct_reply or None,
                "reasoning": reasoning,
                "current_step": current_step,
                "step_timestamps": step_timestamps,
                "agent_flow": agent_flow,
            }
        finally:
            _stream_event({"type": "agent_end", "agent": "Supervisor", "step": current_step})
    finally:
        if _tok is not None:
            _UI_WRITER.reset(_tok)

# ---------------------------------------------------------------------------
# 6. Build and Compile the StateGraph
# ---------------------------------------------------------------------------
def finish_node(state: OrchestratorState, writer=None):
    """Surfaces a direct_reply (e.g. greeting response) as an AI message."""
    _tok = _UI_WRITER.set(writer) if writer is not None else None
    try:
        reply = state.get("direct_reply")
        _stream_event({
            "type": "thought",
            "agent": "Supervisor",
            "text": "Orchestration finished. Compiling the final response.",
            "next": "FINISH",
        })
        if reply:
            return {"messages": [AIMessage(content=reply)]}
        return {}
    finally:
        if _tok is not None:
            _UI_WRITER.reset(_tok)


def build_orchestrator_graph():
    workflow = StateGraph(OrchestratorState)

    # Add Supervisor, FINISH, and Sub-Agent Nodes
    workflow.add_node("Supervisor", supervisor_node)
    workflow.add_node("Finish", finish_node)
    workflow.add_node("Weather", weather_node)
    workflow.add_node("TourGuide", tour_guide_node)
    workflow.add_node("Booking", booking_node)
    workflow.add_node("Transport", transport_node)

    # Define Graph Edges
    workflow.add_edge(START, "Supervisor")

    workflow.add_conditional_edges(
        "Supervisor",
        lambda state: state["next"],
        {
            "Weather":   "Weather",
            "TourGuide": "TourGuide",
            "Booking":   "Booking",
            "Transport": "Transport",
            "FINISH":    "Finish",   # goes through Finish node → then END
        },
    )

    workflow.add_edge("Finish", END)

    # Route sub-agents back to Supervisor for step-by-step re-evaluations
    for node_name in ["Weather", "TourGuide", "Booking", "Transport"]:
        workflow.add_edge(node_name, "Supervisor")

    return workflow.compile()

# ---------------------------------------------------------------------------
# 7. Main Execution Entry Point
# ---------------------------------------------------------------------------
async def main():
    graph = build_orchestrator_graph()

    user_query = "Check the current weather in Tirupati, recommend 2 places to visit, and check sleeper class train availability from Visakhapatnam to Tirupati."
    
    print(f"User Query: {user_query}\n" + "=" * 60)

    try:
        # Run graph execution stream asynchronously
        async for chunk in graph.astream({"messages": [HumanMessage(content=user_query)]}):
            for node_name, state_update in chunk.items():
                print(f"\n[ Active Node Execution: {node_name} ]")
                if "messages" in state_update:
                    print(state_update["messages"][-1].content)
    finally:
        # Graceful cleanup of underlying Playwright & Selenium browser engines
        await booking_module.shutdown()
        transport_module.shutdown()

if __name__ == "__main__":
    print("running main function")
    asyncio.run(main())