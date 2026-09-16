import os
import asyncio
from typing import Annotated, Literal, TypedDict
from pydantic import BaseModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
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
    latest_user_input = state["messages"][-1].content
    response = weather_executor.invoke({"input": latest_user_input})
    return {"messages": [HumanMessage(content=f"[Weather Agent Response]: {response['output']}")]}


def tour_guide_node(state: OrchestratorState):
    response = tour_guide_agent.invoke(state)
    return {"messages": [response["messages"][-1]]}


async def booking_node(state: OrchestratorState):
    latest_user_input = state["messages"][-1].content
    response = await booking_module.executor.ainvoke({"input": latest_user_input})
    return {"messages": [HumanMessage(content=f"[Booking Agent Response]: {response['output']}")]}


def transport_node(state: OrchestratorState):
    latest_user_input = state["messages"][-1].content
    response = transport_module.executor.invoke({"input": latest_user_input})
    return {"messages": [HumanMessage(content=f"[Transport Agent Response]: {response['output']}")]}

# ---------------------------------------------------------------------------
# 5. Supervisor Router Node Logic
# ---------------------------------------------------------------------------
class RouteResponse(BaseModel):
    next: Literal["Weather", "TourGuide", "Booking", "Transport", "FINISH"]

SUPERVISOR_SYSTEM_PROMPT = """
You are the Master Travel Orchestrator managing a team of specialized sub-agents.
Your goal is to inspect the conversation and decide which sub-agent should act next to fulfill the user's travel request.

Sub-Agents & Responsibilities:
- Weather: Real-time weather forecasts and climate checks for destination cities.
- TourGuide: Itineraries, sightseeing recommendations, local attractions, and travel advice.
- Booking: Hotel, accommodation, and stay reservations.
- Transport: Train and inter-city transport searches and bookings.
- FINISH: Respond with FINISH when all parts of the user request have been addressed.
"""

def supervisor_node(state: OrchestratorState):
    messages = [SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT)] + state["messages"]
    structured_llm = ORCHESTRATOR_LLM.with_structured_output(RouteResponse)
    response = structured_llm.invoke(messages)
    return {"next": response.next}

# ---------------------------------------------------------------------------
# 6. Build and Compile the StateGraph
# ---------------------------------------------------------------------------
def build_orchestrator_graph():
    workflow = StateGraph(OrchestratorState)

    # Add Supervisor and Sub-Agent Nodes
    workflow.add_node("Supervisor", supervisor_node)
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
            "Weather": "Weather",
            "TourGuide": "TourGuide",
            "Booking": "Booking",
            "Transport": "Transport",
            "FINISH": END,
        },
    )

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