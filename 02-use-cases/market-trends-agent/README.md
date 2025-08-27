# Market Trends Agent

## Overview

This use case implements an intelligent financial analysis agent using Amazon Bedrock AgentCore that provides real-time market intelligence, stock analysis, and personalized investment recommendations. The agent combines LLM-powered analysis with live market data and maintains persistent memory of broker preferences across sessions.

| Information | Details |
|-------------|---------|
| Use case type | Conversational |
| Agent type | Single agent |
| Use case components | Memory, Tools, Browser Automation |
| Use case vertical | Financial Services |
| Example complexity | Advanced |
| SDK used | Amazon Bedrock AgentCore SDK, LangGraph, Playwright |

## Features

### 🧠 Advanced Memory Management
- **Multi-Strategy Memory**: Uses both USER_PREFERENCE and SEMANTIC memory strategies
- **Broker Profiles**: Maintains persistent financial profiles for each broker/client
- **LLM-Based Identity**: Intelligently extracts and matches broker identities across sessions
- **Investment Preferences**: Stores risk tolerance, investment styles, and sector preferences

### 📊 Real-Time Market Intelligence
- **Conversational Broker Profiles**: Users provide structured broker information through chat ✅ **TESTED & READY**
- **Automatic Profile Parsing**: Intelligently extracts and stores broker preferences from structured input
- **Personalized Market Briefings**: Tailored analysis based on stored broker profiles
- **Multi-Source News**: Bloomberg, Reuters, WSJ, Financial Times, CNBC support
- **Live Stock Data**: Current prices, changes, and market performance metrics
- **Professional Standards**: Delivers institutional-quality analysis aligned with broker's risk tolerance and investment style

### 🌐 Browser Automation
- **Web Scraping**: Automated data collection from financial websites
- **Dynamic Content**: Handles JavaScript-rendered pages and interactive elements
- **Rate Limiting**: Built-in delays and retry logic for reliable data collection

## Quick Start

### Prerequisites
- Python 3.10+
- AWS CLI configured with appropriate credentials
- Docker or Podman installed and running
- Access to Amazon Bedrock AgentCore

### Installation & Deployment

1. **Install Dependencies**
```bash
pip install bedrock-agentcore-starter-toolkit boto3
```

2. **Deploy the Agent** (One Command!)
```bash
python deploy.py
```

3. **Test the Agent**
```bash
python test_agent.py
```

## Files Structure

```
market-trends-agent/
├── deploy.py                 # Complete deployment script
├── test_agent.py             # Comprehensive test suite
├── test_broker_card.py       # Broker card functionality demonstration
├── market_trends_agent.py    # Main agent implementation
├── tools/
│   ├── browser_tool.py       # Web scraping utilities
│   ├── broker_card_tools.py  # Conversational broker profile tools
│   └── __init__.py          # Tool imports
├── requirements.txt          # Python dependencies
├── Dockerfile               # Container configuration
├── broker_card.txt          # Example broker profile format
└── docs/
    └── DEPLOYMENT.md        # Detailed deployment guide
```

## Usage Examples

### 📋 Broker Profile Setup (First Interaction)
Send your broker information in this structured format:

```
Name: Sarah Chen
Company: Morgan Stanley
Role: Investment Advisor
Preferred News Feed: Bloomberg
Industry Interests: technology, healthcare, financial services
Investment Strategy: growth investing
Risk Tolerance: moderate to high
Client Demographics: younger professionals, tech workers
Geographic Focus: North America, Asia-Pacific
Recent Interests: artificial intelligence, renewable energy, fintech
```

The agent will automatically:
- Parse and store your profile in memory
- Provide personalized acknowledgment
- Tailor all future responses to your specific preferences

### 📊 Personalized Market Analysis
After setting up your profile, ask for market insights:

```
"What's happening with biotech stocks today?"
"Give me an analysis of the AI sector for my tech-focused clients"
"What are the latest ESG investing trends in Europe?"
```

The agent will provide analysis specifically tailored to:
- Your industry interests
- Your risk tolerance
- Your client demographics
- Your preferred news sources

### 🧪 Test the Broker Card Functionality
```bash
python test_broker_card.py
```

This demonstrates the complete workflow:
1. Sending structured broker profile
2. Agent parsing and storing preferences
3. Receiving personalized market analysis

## Deployment Options

### Simple Deployment
```bash
# Deploy with defaults
python deploy.py
```

### Custom Configuration
```bash
# Deploy with custom settings
python deploy.py \
  --agent-name "my-market-agent" \
  --region "us-west-2" \
  --role-name "MyCustomRole"
```

### Available Options
- `--agent-name`: Name for the agent (default: market_trends_agent)
- `--role-name`: IAM role name (default: MarketTrendsAgentRole)
- `--region`: AWS region (default: us-east-1)
- `--skip-checks`: Skip prerequisite validation

## Testing

### Test Options
```bash
# Simple connectivity test
python test_agent.py
# Choose option 1

# Comprehensive functionality tests
python test_agent.py
# Choose option 2
```

The comprehensive tests include:
- Broker profile creation and memory storage
- Memory recall across sessions
- Real-time market data retrieval
- Bloomberg news searches

## Architecture

### Use case Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Market Trends Agent                          │
├─────────────────────────────────────────────────────────────────┤
│  LangGraph Agent Framework                                      │
│  ├── Claude Sonnet 4 (LLM)                                     │
│  ├── Browser Automation Tools                                   │
│  └── Memory Management Tools                                    │
├─────────────────────────────────────────────────────────────────┤
│  AgentCore Multi-Strategy Memory                                │
│  ├── USER_PREFERENCE: Broker profiles & preferences            │
│  └── SEMANTIC: Financial facts & market insights               │
├─────────────────────────────────────────────────────────────────┤
│  External Data Sources                                          │
│  ├── Real-time Stock Data (Google Finance, Yahoo Finance)      │
│  ├── Financial News (Bloomberg)                                 │
│  └── Market Analysis APIs                                       │
└─────────────────────────────────────────────────────────────────┘
```

### Memory Strategies
- **USER_PREFERENCE**: Captures broker preferences, risk tolerance, investment styles
- **SEMANTIC**: Stores financial facts, market analysis, investment insights

### Available Tools
- `get_stock_data(symbol)`: Real-time stock prices and market data
- `search_bloomberg_news(query)`: Bloomberg news and market intelligence
- `identify_broker(message)`: LLM-based broker identity extraction
- `get_broker_financial_profile()`: Retrieve stored financial profiles
- `update_broker_financial_interests()`: Store new preferences and interests

## Monitoring

### CloudWatch Logs
After deployment, monitor your agent:
```bash
# View logs (replace with your agent ID)
aws logs tail /aws/bedrock-agentcore/runtimes/{agent-id}-DEFAULT --follow
```

### Health Checks
- Built-in health check endpoints
- Monitor agent availability and response times

## Troubleshooting

### Common Issues

1. **Throttling Errors**
   - Wait a few minutes between requests
   - Your account may have lower rate limits
   - Check CloudWatch logs for details

2. **Container Build Fails**
   - Ensure Docker/Podman is running
   - Check network connectivity
   - Verify all required files are present

3. **Permission Errors**
   - The deployment script creates all required IAM permissions
   - Check AWS credentials are configured correctly

### Debug Information
The deployment script includes comprehensive error reporting and will guide you through any issues.

## Security

### IAM Permissions
The deployment script automatically creates a role with:
- `bedrock:InvokeModel` (for Claude Sonnet)
- `bedrock-agentcore:*` (for memory and runtime operations)
- `ecr:*` (for container registry access)
- `xray:*` (for tracing)
- `logs:*` (for CloudWatch logging)

### Data Privacy
- Financial profiles are stored securely in Bedrock AgentCore Memory
- No sensitive data is logged or exposed
- All communications are encrypted in transit

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.