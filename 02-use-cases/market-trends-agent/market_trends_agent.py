from langgraph.graph import StateGraph, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.memory import MemoryClient
from tools import get_stock_data, search_bloomberg_news, search_news
from tools import parse_broker_profile_from_message, generate_market_summary_for_broker, get_broker_card_template, collect_broker_preferences_interactively
from botocore.exceptions import ClientError
from datetime import datetime
import argparse
import json
import logging
import os

app = BedrockAgentCoreApp()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Memory setup
def create_memory():
    """Create AgentCore Memory for the market trends agent with multiple memory strategies"""
    from bedrock_agentcore.memory.constants import StrategyType
    
    region = os.getenv('AWS_REGION', 'us-east-1')
    client = MemoryClient(region_name=region)
    memory_name = "MarketTrendsAgentMultiStrategy"
    
    try:
        logger.info("Creating AgentCore Memory with multiple memory strategies...")
        
        # Define memory strategies for market trends agent
        strategies = [
            {
                StrategyType.USER_PREFERENCE.value: {
                    "name": "BrokerPreferences",
                    "description": "Captures broker preferences, risk tolerance, and investment styles",
                    "namespaces": ["market-trends/broker/{actorId}/preferences"]
                }
            },
            {
                StrategyType.SEMANTIC.value: {
                    "name": "MarketTrendsSemantic",
                    "description": "Stores financial facts, market analysis, and investment insights",
                    "namespaces": ["market-trends/broker/{actorId}/semantic"]
                }
            }
        ]
        
        memory = client.create_memory_and_wait(
            name=memory_name,
            description="Market Trends Agent with multi-strategy memory for broker financial interests",
            strategies=strategies,  # Multiple memory strategies for comprehensive storage
            event_expiry_days=90,  # Keep conversations for 90 days (longer for financial data)
            max_wait=300,
            poll_interval=10
        )
        memory_id = memory['id']
        logger.info(f"Multi-strategy memory created successfully with ID: {memory_id}")
        return client, memory_id
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ValidationException' and "already exists" in str(e):
            # Memory already exists, retrieve its ID
            memories = client.list_memories()
            memory_id = next((m['id'] for m in memories if m['id'].startswith(memory_name)), None)
            logger.info(f"Multi-strategy memory already exists. Using existing memory ID: {memory_id}")
            return client, memory_id
        else:
            logger.error(f"Error creating memory: {e}")
            raise
    except Exception as e:
        logger.error(f"Unexpected error creating memory: {e}")
        raise

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
    
    def extract_actor_id(user_message: str) -> str:
        """Extract actor_id from broker card format or user message"""
        import hashlib
        import re
        
        # Look for broker card format: "Name: [Name]"
        name_match = re.search(r'Name:\s*([^\n]+)', user_message, re.IGNORECASE)
        if name_match:
            name = name_match.group(1).strip()
            if name and name.lower() != "unknown":
                # Clean name for actor_id
                clean_name = re.sub(r'[^a-zA-Z0-9]', '_', name.lower())
                return f"broker_{clean_name}"
        
        # Look for "I'm [Name]" or "My name is [Name]" patterns
        intro_patterns = [
            r"I'?m\s+([A-Z][a-zA-Z\s]+?)(?:\s+from|\s+at|\s*[,.]|$)",
            r"My name is\s+([A-Z][a-zA-Z\s]+?)(?:\s+from|\s+at|\s*[,.]|$)",
            r"This is\s+([A-Z][a-zA-Z\s]+?)(?:\s+from|\s+at|\s*[,.]|$)"
        ]
        
        for pattern in intro_patterns:
            match = re.search(pattern, user_message, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                if len(name.split()) <= 3:  # Reasonable name length
                    clean_name = re.sub(r'[^a-zA-Z0-9]', '_', name.lower())
                    return f"broker_{clean_name}"
        
        # Fallback: use message hash for anonymous users
        message_hash = hashlib.md5(user_message.lower().encode()).hexdigest()[:8]
        return f"user_{message_hash}"
    
    @tool
    def list_conversation_history(actor_id_override: str = None):
        """Retrieve recent conversation history and user preferences from memory"""
        try:
            # Use provided actor_id or default
            current_actor_id = actor_id_override or default_actor_id
            
            events = memory_client.list_events(
                memory_id=memory_id,
                actor_id=current_actor_id,
                session_id=session_id,
                max_results=10
            )
            return events
        except Exception as e:
            logger.error(f"Error retrieving conversation history: {e}")
            return "No conversation history available"
    
    def get_namespaces(mem_client: MemoryClient, memory_id: str) -> dict:
        """Get namespace mapping for memory strategies."""
        try:
            strategies = mem_client.get_memory_strategies(memory_id)
            return {i["type"]: i["namespaces"][0] for i in strategies}
        except Exception as e:
            logger.error(f"Error getting namespaces: {e}")
            return {}

    @tool
    def get_broker_financial_profile(actor_id_override: str = None):
        """Retrieve the long-term financial interests and investment profile from multiple memory strategies"""
        try:
            # Use provided actor_id or default
            current_actor_id = actor_id_override or default_actor_id
            
            # Get namespaces for all memory strategies
            namespaces_dict = get_namespaces(memory_client, memory_id)
            
            all_profile_info = []
            
            # Retrieve from all memory strategies
            for strategy_type, namespace_template in namespaces_dict.items():
                try:
                    namespace = namespace_template.format(actorId=current_actor_id)
                    
                    memories = memory_client.retrieve_memories(
                        memory_id=memory_id,
                        namespace=namespace,
                        query="broker financial profile investment preferences risk tolerance",
                        top_k=3
                    )
                    
                    for memory in memories:
                        if isinstance(memory, dict):
                            content = memory.get('content', {})
                            if isinstance(content, dict):
                                text = content.get('text', '').strip()
                                if text and len(text) > 20:  # Meaningful content
                                    all_profile_info.append(f"[{strategy_type.upper()}] {text}")
                                    
                except Exception as strategy_error:
                    logger.info(f"No memories found in {strategy_type} strategy: {strategy_error}")
            
            if all_profile_info:
                return f"Broker Financial Profile:\n" + "\n\n".join(all_profile_info)
            else:
                # Fallback: Get recent events to build profile from conversation history
                events = memory_client.list_events(
                    memory_id=memory_id,
                    actor_id=current_actor_id,
                    session_id=session_id,
                    max_results=10
                )
                
                if events:
                    profile_elements = []
                    for event in events:
                        if 'messages' in event:
                            for message in event['messages']:
                                content = message.get('content', '')
                                # Look for profile-related information
                                if any(keyword in content.lower() for keyword in ['broker', 'investment', 'risk tolerance', 'portfolio', 'preference', 'client']):
                                    if len(content) > 50:  # Meaningful content
                                        profile_elements.append(content[:200] + "..." if len(content) > 200 else content)
                    
                    if profile_elements:
                        return f"Broker Profile (from conversation history):\n" + "\n\n".join(profile_elements[-2:])
                    else:
                        return "Building financial profile from our conversations. Profile will be enhanced as we continue our discussions."
                else:
                    return "No financial profile found for this broker yet. This will be created as we learn about their investment preferences."
                
        except Exception as e:
            logger.error(f"Error retrieving broker financial profile: {e}")
            return "Unable to retrieve financial profile at this time"
    
    @tool 
    def update_broker_financial_interests(interests_update: str, actor_id_override: str = None):
        """Update or add to the broker's financial interests and investment preferences
        
        Args:
            interests_update: New financial interests, preferences, or profile updates to store
            actor_id_override: Optional specific actor_id to use
        """
        try:
            # Use provided actor_id or default
            current_actor_id = actor_id_override or default_actor_id
            
            # Create an event with proper roles for memory storage
            conversation = [
                (f"Please update my financial profile with this information: {interests_update}", "USER"),
                ("I've updated your financial profile with the new information. This will be included in your long-term investment profile for future reference.", "ASSISTANT")
            ]
            
            memory_client.create_event(
                memory_id=memory_id,
                actor_id=current_actor_id,
                session_id=session_id,
                messages=conversation
            )
            
            return "Financial interests successfully updated in long-term memory profile"
            
        except Exception as e:
            logger.error(f"Error updating financial interests: {e}")
            return "Unable to update financial interests at this time"
    
    @tool
    def identify_broker(user_message: str):
        """Identify the broker from their message and return their consistent actor_id
        
        Args:
            user_message: The user's message containing identity information (broker card format or introduction)
            
        Returns:
            Information about the identified broker and their actor_id
        """
        try:
            # Extract actor_id using simple parsing
            identified_actor_id = extract_actor_id(user_message)
            
            # Try to get existing profile for this broker
            try:
                events = memory_client.list_events(
                    memory_id=memory_id,
                    actor_id=identified_actor_id,
                    session_id=session_id,
                    max_results=5
                )
                
                if events:
                    return f"Broker identified: {identified_actor_id}\nFound existing profile with {len(events)} previous interactions.\nUse get_broker_financial_profile() to retrieve their stored preferences."
                else:
                    return f"New broker identified: {identified_actor_id}\nNo previous profile found. This appears to be a new broker.\nUse update_broker_financial_interests() to store their preferences."
                    
            except Exception as e:
                return f"Broker identified: {identified_actor_id}\nUnable to check existing profile: {e}"
                
        except Exception as e:
            logger.error(f"Error identifying broker: {e}")
            return "Unable to identify broker at this time"
    
    # Bind tools to the LLM (market data tools + memory tools + conversational broker tools)
    tools = [
        get_stock_data, 
        search_bloomberg_news,
        search_news,
        parse_broker_profile_from_message,
        generate_market_summary_for_broker,
        get_broker_card_template,
        collect_broker_preferences_interactively,
        list_conversation_history,
        get_broker_financial_profile,
        update_broker_financial_interests,
        identify_broker
    ]
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
    - search_bloomberg_news(query): Searches Bloomberg for business news and market intelligence
    - search_news(query): General news search for market-related information
    
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
       - Search for relevant market news using search_bloomberg_news()
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
