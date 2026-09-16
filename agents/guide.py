import os
from typing import Literal
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

# =====================================================================
# 1. Configuration & API Setup
# =====================================================================
from dotenv import load_dotenv

env_file_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_file_path):
    load_dotenv(env_file_path)
else:
    load_dotenv()

# Initialize LLM based on available API keys
if os.getenv("GROQ_API_KEY"):
    from langchain_groq import ChatGroq
    llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0.7, groq_api_key=os.getenv("GROQ_API_KEY"))
elif os.getenv("OPENAI_API_KEY"):
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
elif os.getenv("GOOGLE_API_KEY"):
    from langchain_google_genai import ChatGoogleGenerativeAI
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.7)
else:
    raise ValueError("No valid API key found for Tour Guide Agent.")

# =====================================================================
# 2. Define Search Tool & System Prompt
# =====================================================================
# Real-time search tool to pull internet data
web_search_tool = DuckDuckGoSearchRun(
    description="Useful for searching up-to-date travel information, local events, ticket prices, opening hours, and weather."
)

tools = [web_search_tool]

# Tour guide behavior and personality prompt
SYSTEM_PROMPT = """
You are 'Trippy', an energetic, highly knowledgeable, and friendly Local Tour Guide.
Your job is to provide tailored travel itineraries, hidden local gems, historical context, and practical travel advice.

Guidelines:
1. Always check real-time details (e.g., ticket prices, opening hours, weather, or current safety guidelines) using the web search tool before providing final recommendations.
2. Structure your recommendations with clear, readable bullet points or daily schedules.
3. Keep your tone enthusiastic, welcoming, and polite.
"""

# =====================================================================
# 3. Create the Agent
# =====================================================================
# Uses modern LangChain/LangGraph agent interface
tour_guide_agent = create_react_agent(
    model=llm,
    tools=tools,
    prompt=SYSTEM_PROMPT,
)

# =====================================================================
# 4. Execution / Test Run
# =====================================================================
def ask_tour_guide(query: str):
    print(f"\n--- User Query: {query} ---\n")
    
    # Run the agent with user query
    response = tour_guide_agent.invoke(
        {"messages": [HumanMessage(content=query)]}
    )
    
    # Extract the final agent response message
    final_message = response["messages"][-1].content
    print(final_message)


if __name__ == "__main__":
    # Example 1: Real-time query requiring web search
    ask_tour_guide("I am visiting Kyoto for 2 days. What are top 3 places to visit and what's the weather like right now?")