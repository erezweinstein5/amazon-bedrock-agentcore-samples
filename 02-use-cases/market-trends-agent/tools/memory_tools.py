"""
Memory Tools for Market Trends Agent

This module contains all memory-related tools for managing broker profiles,
conversation history, and financial interests using AgentCore Memory.
"""

from langchain_core.tools import tool
from bedrock_agentcore.memory import MemoryClient
from botocore.exceptions import ClientError
import hashlib
import logging
import os
import re

# Configure logging
logger = logging.getLogger(__name__)

def create_memory():
    """Create or retrieve existing AgentCore Memory for the market trends agent with multiple memory strategies"""
    from bedrock_agentcore.memory.constants import StrategyType
    
    region = os.getenv('AWS_REGION', 'us-east-1')
    client = MemoryClient(region_name=region)
    memory_name = "MarketTrendsAgentMultiStrategy"
    
    # First, check if memory already exists
    logger.info(f"Checking if memory '{memory_name}' already exists...")
    try:
        memories = client.list_memories()
        memory_id = None
        for memory in memories:
            # Memory IDs start with the memory name followed by a dash and random string
            if memory.get('id', '').startswith(memory_name + '-'):
                memory_id = memory['id']
                break
        
        if memory_id:
            logger.info(f"Found existing memory '{memory_name}' with ID: {memory_id}")
            return client, memory_id
    except Exception as e:
        logger.warning(f"Error checking existing memories: {e}")
    
    # Memory doesn't exist, create it
    logger.info("Memory not found, creating new AgentCore Memory with multiple memory strategies...")
    try:
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
            # Race condition: memory was created between our check and create attempt
            logger.info(f"Memory '{memory_name}' was created by another process, retrieving it...")
            memories = client.list_memories()
            memory_id = None
            for memory in memories:
                if memory.get('id', '').startswith(memory_name + '-'):
                    memory_id = memory['id']
                    break
            
            if memory_id:
                logger.info(f"Found existing memory '{memory_name}' with ID: {memory_id}")
                return client, memory_id
            else:
                logger.error(f"Memory '{memory_name}' exists but could not retrieve ID")
                raise Exception(f"Could not find existing memory '{memory_name}'")
        else:
            logger.error(f"Error creating memory: {e}")
            raise
    except Exception as e:
        logger.error(f"Unexpected error creating memory: {e}")
        raise

def extract_actor_id(user_message: str) -> str:
    """Extract actor_id from broker card format or user message"""
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
    message_hash = hashlib.sha256(user_message.lower().encode()).hexdigest()[:8]
    return f"user_{message_hash}"

def get_namespaces(mem_client: MemoryClient, memory_id: str) -> dict:
    """Get namespace mapping for memory strategies."""
    try:
        strategies = mem_client.get_memory_strategies(memory_id)
        return {i["type"]: i["namespaces"][0] for i in strategies}
    except Exception as e:
        logger.error(f"Error getting namespaces: {e}")
        return {}

def create_memory_tools(memory_client: MemoryClient, memory_id: str, session_id: str, default_actor_id: str):
    """Create memory tools with the provided memory client and configuration"""
    
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
                return "Broker Financial Profile:\n" + "\n\n".join(all_profile_info)
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
                        return "Broker Profile (from conversation history):\n" + "\n\n".join(profile_elements[-2:])
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
    
    return [
        list_conversation_history,
        get_broker_financial_profile,
        update_broker_financial_interests,
        identify_broker
    ]