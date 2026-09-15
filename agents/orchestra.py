# main.py
from weather_agent import weather_agent

def main():
    print("Initializing Weather Agent...")
    
    # 1. Instantiate the agent executor
    agent = weather_agent()

    # 2. Define your query
    user_query = "Hi! Introduce yourself and tell me what the weather is like in Tirupathi."

    print(f"User Query: {user_query}\n")

    # 3. Invoke the agent
    response = agent.invoke({"input": user_query})

    # 4. Print the final response output
    print("--- Agent Response ---")
    print(response["output"])

if __name__ == "__main__":
    main()