import os
import asyncio
from typing import Annotated, Literal, Optional, TypedDict
from pydantic import BaseModel
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_classic.agents import tool
from dotenv import load_dotenv

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
def weather_node(state: OrchestratorState):
    import time
    latest_user_input = state["messages"][-1].content
    response = weather_executor.invoke({"input": latest_user_input})
    
    # Update agent flow to mark as completed
    agent_flow = state.get("agent_flow", [])
    for entry in reversed(agent_flow):
        if entry["agent"] == "Weather" and entry["status"] in ["pending", "active"]:
            entry["status"] = "completed"
            entry["end_time"] = time.time()
            break
    
    return {
        "messages": [HumanMessage(content=f"[Weather Agent Response]: {response['output']}")],
        "agent_flow": agent_flow,
    }


def tour_guide_node(state: OrchestratorState):
    import time
    response = tour_guide_agent.invoke(state)
    
    # Update agent flow to mark as completed
    agent_flow = state.get("agent_flow", [])
    for entry in reversed(agent_flow):
        if entry["agent"] == "TourGuide" and entry["status"] in ["pending", "active"]:
            entry["status"] = "completed"
            entry["end_time"] = time.time()
            break
    
    return {
        "messages": [response["messages"][-1]],
        "agent_flow": agent_flow,
    }


async def booking_node(state: OrchestratorState):
    import time
    latest_user_input = state["messages"][-1].content
    response = await booking_module.executor.ainvoke({"input": latest_user_input})
    
    # Update agent flow to mark as completed
    agent_flow = state.get("agent_flow", [])
    for entry in reversed(agent_flow):
        if entry["agent"] == "Booking" and entry["status"] in ["pending", "active"]:
            entry["status"] = "completed"
            entry["end_time"] = time.time()
            break
    
    return {
        "messages": [HumanMessage(content=f"[Booking Agent Response]: {response['output']}")],
        "agent_flow": agent_flow,
    }


def transport_node(state: OrchestratorState):
    import time
    latest_user_input = state["messages"][-1].content
    response = transport_module.executor.invoke({"input": latest_user_input})
    
    # Update agent flow to mark as completed
    agent_flow = state.get("agent_flow", [])
    for entry in reversed(agent_flow):
        if entry["agent"] == "Transport" and entry["status"] in ["pending", "active"]:
            entry["status"] = "completed"
            entry["end_time"] = time.time()
            break
    
    return {
        "messages": [HumanMessage(content=f"[Transport Agent Response]: {response['output']}")],
        "agent_flow": agent_flow,
    }

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


def supervisor_node(state: OrchestratorState):
    import time
    
    last_user_msg = next(
        (m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
        ""
    )
    
    # Initialize or increment step counter
    current_step = state.get("current_step", 0) + 1
    step_timestamps = state.get("step_timestamps", {})
    step_timestamps[current_step] = time.time()
    
    agent_flow = state.get("agent_flow", [])

    # Fast-path for non-travel queries: generate dynamic LLM response without hardcoded strings
    if not _is_travel_query(last_user_msg):
        messages = [
            SystemMessage(content="You are the Master Travel Orchestrator. Respond warmly and helpfully to general questions or greetings, explaining how your team (Weather, Tour Guide, Booking, Transport) can help plan trips when ready.")
        ] + state["messages"]
        reply_msg = ORCHESTRATOR_LLM.invoke(messages)
        reasoning = "Non-travel query detected. Providing direct conversational response."
        return {
            "next": "FINISH",
            "direct_reply": reply_msg.content,
            "reasoning": reasoning,
            "current_step": current_step,
            "step_timestamps": step_timestamps,
        }

    # Travel query → ask LLM to route to the right sub-agent
    messages = [SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT)] + state["messages"]
    structured_llm = ORCHESTRATOR_LLM.with_structured_output(RouteResponse)
    response = structured_llm.invoke(messages)
    
    # Generate fallback reasoning if LLM didn't provide one
    reasoning = response.reasoning if response.reasoning else f"Routing to {response.next} agent to handle the request."
    
    # Add to agent flow if routing to a sub-agent
    if response.next != "FINISH":
        agent_flow.append({
            "step": current_step,
            "agent": response.next,
            "status": "pending",
            "reasoning": reasoning,
            "start_time": time.time(),
        })
    
    return {
        "next": response.next,
        "direct_reply": response.direct_reply or None,
        "reasoning": reasoning,
        "current_step": current_step,
        "step_timestamps": step_timestamps,
        "agent_flow": agent_flow,
    }

# ---------------------------------------------------------------------------
# 6. Build and Compile the StateGraph
# ---------------------------------------------------------------------------
def finish_node(state: OrchestratorState):
    """Surfaces a direct_reply (e.g. greeting response) as an AI message."""
    reply = state.get("direct_reply")
    if reply:
        return {"messages": [AIMessage(content=reply)]}
    return {}


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