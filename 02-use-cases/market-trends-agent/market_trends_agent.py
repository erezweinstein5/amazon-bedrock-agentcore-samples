from langgraph.graph import StateGraph, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import HumanMessage, SystemMessage
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from tools import get_stock_data, search_news
from tools import parse_broker_profile_from_message, generate_market_summary_for_broker, get_broker_card_template, collect_broker_preferences_interactively
from tools import create_memory, extract_actor_id, create_memory_tools
import logging

app = BedrockAgentCoreApp()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Memory setup is now handled in tools/memory_tools.py

# Define the agent using LangGraph construction with AgentCore Memory
def create_market_trends_agent():
    """Create and configure the LangGraph market trends agent with memory"""
    from langchain_aws import ChatBedrock
    
    # Create memory
    memory_client, memory_id = create_memory()
    
    # Create session ID for this conversation, but actor_id will be determined from user input
    session_id = f"market-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # Default actor_id - will be updated when user identifies themselves
    default_actor_id = "unknown-user"
    
    # Initialize your LLM with Claude Sonnet 4 using inference profile
    llm = ChatBedrock(
        model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
        model_kwargs={"temperature": 0.1}
    )
    
    # Create memory tools using the memory_tools module
    memory_tools = create_memory_tools(memory_client, memory_id, session_id, default_actor_id)
    
    # Bind tools to the LLM (market data tools + memory tools + conversational broker tools)
    tools = [
        get_stock_data, 
        search_news,
        parse_broker_profile_from_message,
        generate_market_summary_for_broker,
        get_broker_card_template,
        collect_broker_preferences_interactively,
    ] + memory_tools
    llm_with_tools = llm.bind_tools(tools)
    
    # System message optimized for Claude Sonnet 4 with Long-Term AgentCore Memory
    system_message = """You're an expert market intelligence analyst with deep expertise in financial markets, business strategy, and economic trends. You have advanced long-term memory capabilities to store and recall financial interests for each broker you work with.

    PURPOSE:
    - Provide real-time market analysis and stock data
    - Maintain long-term financial profiles for each broker/client
    - Store and recall investment preferences, risk tolerance, and financial goals
    - Deliver personalized investment insights based on stored broker profiles
    - Build ongoing professional relationships through comprehensive memory

    AVAILABLE TOOLS:
    
    Real-Time Market Data:
    - get_stock_data(symbol): Retrieves current stock prices, changes, and market data
    - search_news(query, news_source): Searches multiple news sources (Bloomberg, Reuters, CNBC, WSJ, Financial Times, Dow Jones) for business news and market intelligence
    
    Broker Profile Collection (Conversational):
    - parse_broker_profile_from_message(user_message): Parse structured broker profile from user input
    - generate_market_summary_for_broker(broker_profile, market_data): Generate tailored market summary
    - get_broker_card_template(): Provide template for broker profile format
    - collect_broker_preferences_interactively(preference_type): Guide collection of specific preferences
    
    Memory & Financial Profile Management:
    - list_conversation_history(): Retrieve recent conversation history
    - get_broker_financial_profile(): Retrieve long-term financial interests and investment profile for this broker
    - update_broker_financial_interests(interests_update): Store new financial interests or profile updates
    - identify_broker(user_message): Use LLM to identify broker from their message and get their actor_id
    
    MULTI-STRATEGY LONG-TERM MEMORY CAPABILITIES:
    - You maintain persistent financial profiles for each broker using multiple memory strategies:
      * USER_PREFERENCE: Captures broker preferences, risk tolerance, and investment styles
      * SEMANTIC: Stores financial facts, market analysis, and investment insights
    - Use identify_broker() to intelligently extract broker identity using LLM analysis
    - Always check get_broker_financial_profile() for returning brokers to personalize service
    - Use update_broker_financial_interests() when brokers share new preferences or interests
    - Build comprehensive investment profiles over time across multiple memory dimensions
    - LLM-based identity extraction ensures consistent broker identification across varied introductions
    - Memory strategies work together to provide rich, contextual financial intelligence
    
    BROKER PROFILE MANAGEMENT:
    
    1. **Broker Identification**: 
       - Use identify_broker() when a user introduces themselves to get their consistent actor_id
       - The LLM will extract name, company, and role information intelligently
       - This ensures the same broker gets the same identity across all sessions
    
    2. **Profile Collection (Conversational Approach)**:
       - Use parse_broker_profile_from_message() when users provide structured broker card format
       - Use get_broker_card_template() to show users the expected format
       - Use collect_broker_preferences_interactively() to guide collection of specific preferences
       - NO FILE ACCESS - All profile data comes through conversation
    
    3. **New Brokers**: 
       - When a broker introduces themselves, use identify_broker() first
       - If they provide broker card format, use parse_broker_profile_from_message() to extract structured data
       - Use update_broker_financial_interests() to store their complete profile
       - If missing information, use collect_broker_preferences_interactively() to ask targeted questions
    
    4. **Returning Brokers**:
       - Use identify_broker() to confirm their identity, then get_broker_financial_profile() to recall their stored interests
       - Reference their previous preferences and tailor analysis accordingly
       - Update their profile with any new interests or changes using update_broker_financial_interests()
    
    3. **Market Analysis**:
       - Provide real-time stock data using get_stock_data()
       - Search for relevant market news using search_news() with appropriate news sources
       - Connect market events specifically to each broker's stored financial interests
       - Prioritize analysis of stocks/sectors in their profile
    
    4. **Professional Standards**:
       - Deliver institutional-quality analysis tailored to each broker's stored risk tolerance
       - Reference their specific investment goals and time horizons from their profile
       - Provide recommendations aligned with their stored investment style and preferences
       - Maintain professional relationships through consistent, personalized service
    
    CRITICAL: Always use the memory tools to maintain and reference broker financial profiles. This is essential for providing personalized, professional market intelligence services."""
    
    # Define the chatbot node with automatic conversation saving
    def chatbot(state: MessagesState):
        raw_messages = state["messages"]
        
        # Remove any existing system messages to avoid duplicates
        non_system_messages = [msg for msg in raw_messages if not isinstance(msg, SystemMessage)]
        
        # Always ensure SystemMessage is first
        messages = [SystemMessage(content=system_message)] + non_system_messages
        
        # Get the latest user message
        latest_user_message = next((msg.content for msg in reversed(messages) if isinstance(msg, HumanMessage)), None)
        
        # Extract actor_id from user message for consistent broker identification
        current_actor_id = default_actor_id
        if latest_user_message:
            current_actor_id = extract_actor_id(latest_user_message)
        
        # Get response from model with tools bound
        response = llm_with_tools.invoke(messages)
        
        # Save conversation to AgentCore Memory with correct actor_id
        if latest_user_message and response.content.strip():
            conversation = [
                (latest_user_message, "USER"),
                (response.content, "ASSISTANT")
            ]
            
            # Validate that all message texts are non-empty
            if all(msg[0].strip() for msg in conversation):
                try:
                    memory_client.create_event(
                        memory_id=memory_id,
                        actor_id=current_actor_id,
                        session_id=session_id,
                        messages=conversation
                    )
                    logger.info(f"Conversation saved to AgentCore Memory for actor: {current_actor_id}")
                except Exception as e:
                    logger.error(f"Error saving conversation to memory: {e}")
        
        # Return updated messages
        return {"messages": raw_messages + [response]}
    
    # Create the graph
    graph_builder = StateGraph(MessagesState)
    
    # Add nodes
    graph_builder.add_node("chatbot", chatbot)
    graph_builder.add_node("tools", ToolNode(tools))
    
    # Add edges
    graph_builder.add_conditional_edges(
        "chatbot",
        tools_condition,
    )
    graph_builder.add_edge("tools", "chatbot")
    
    # Set entry point
    graph_builder.set_entry_point("chatbot")
    
    # Compile the graph
    return graph_builder.compile()

# Initialize the agent
agent = create_market_trends_agent()

@app.entrypoint
def market_trends_agent_runtime(payload):
    """
    Invoke the market trends agent with a payload for AgentCore Runtime
    """
    user_input = payload.get("prompt")
    
    # Create the input in the format expected by LangGraph
    response = agent.invoke({"messages": [HumanMessage(content=user_input)]})
    
    # Extract the final message content
    return response["messages"][-1].content

def market_trends_agent_local(payload):
    """
    Invoke the market trends agent with a payload for local testing
    
    Args:
        payload (dict): Dictionary containing the user prompt
        
    Returns:
        str: The agent's response containing market analysis and data
    """
    user_input = payload.get("prompt")
    
    # Create the input in the format expected by LangGraph
    response = agent.invoke({"messages": [HumanMessage(content=user_input)]})
    
    # Extract the final message content
    return response["messages"][-1].content

if __name__ == "__main__":
    app.run()
