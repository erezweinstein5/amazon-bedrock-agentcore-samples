# Market Trends Agent

A Strands-based agent that provides real-time stock data and business news analysis using browser automation.

## Features

- **Real-time Stock Data**: Get current prices and changes from Google Finance
- **Business News Search**: Search Bloomberg for relevant market news
- **Professional Analysis**: AI-powered market intelligence and insights

## Files

- `market_trends_agent.py` - Main Strands agent implementation
- `browser_tool.py` - Browser automation tools for data collection
- `test_agent.py` - Test suite for the agent
- `requirements.txt` - Python dependencies

## Setup

1. **Create virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   playwright install
   ```

3. **AWS Authentication** (for Bedrock):
   ```bash
   mwinit  # or configure AWS credentials
   ```

## Usage

### Test the Agent
```bash
python test_agent.py
```

### Use Programmatically
```python
from market_trends_agent import market_trends_agent_local

# Get stock data
response = market_trends_agent_local({
    "prompt": "What's the current price of Apple stock?"
})

# Search for news
response = market_trends_agent_local({
    "prompt": "Find recent news about AI stocks"
})
```

## Tools Available

- `get_stock_data(symbol)` - Retrieves real-time stock prices
- `search_bloomberg_news(query)` - Searches Bloomberg for business news

## Example Queries

- "Get me the current stock price for Apple (AAPL)"
- "Compare the stock prices of Apple, Google, and Tesla"
- "Search for recent news about artificial intelligence stocks"
- "What's happening with tech stocks today?"