from strands import Agent
from strands.models import BedrockModel
from browser_tool import get_stock_data, search_bloomberg_news
import argparse
import json

# Configure the Bedrock model
model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"
model = BedrockModel(
    model_id=model_id,
    region="us-east-1"
)

# Create the market trends agent with browser tools and system prompt
agent = Agent(
    model=model,
    tools=[get_stock_data, search_bloomberg_news],
    system_prompt="""You're a professional market intelligence assistant specializing in financial data and business news analysis.
    
    You have access to powerful browser tools that can:
    - Get real-time stock data from Yahoo Finance using get_stock_data()
    - Search Bloomberg for business news and headlines using search_bloomberg_news()
    
    When users ask about stocks or market data:
    - Use get_stock_data() with the stock symbol (e.g., 'AAPL', 'GOOGL', 'TSLA')
    - Provide clear analysis of the price movements and trends
    - Explain what the data means in business context
    
    When users ask about business news or market trends:
    - Use search_bloomberg_news() with relevant keywords
    - Summarize the key headlines and their potential market impact
    - Provide insights on how news might affect related stocks or sectors
    
    Always be professional, accurate, and provide actionable insights. If you encounter any errors with the tools, explain what happened and suggest alternatives."""
)

def market_trends_agent_local(payload):
    """
    Invoke the market trends agent with a payload for local testing
    
    Args:
        payload (dict): Dictionary containing the user prompt
        
    Returns:
        str: The agent's response containing market analysis and data
    """
    user_input = payload.get("prompt")
    response = agent(user_input)
    return response.message['content'][0]['text']

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("payload", type=str)
    args = parser.parse_args()
    
    response = market_trends_agent_local(json.loads(args.payload))
    # Note: The response is already displayed by the Strands framework
