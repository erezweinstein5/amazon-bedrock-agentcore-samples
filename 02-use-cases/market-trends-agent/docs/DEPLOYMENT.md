# Market Trends Agent Deployment Guide

This guide walks you through deploying the Market Trends Agent to Amazon Bedrock AgentCore Runtime.

## Prerequisites

### 1. AWS Setup
- AWS CLI configured with appropriate credentials
- Docker installed and running
- Access to Amazon Bedrock AgentCore
- ECR repository created for the agent container

### 2. Required Permissions
Your IAM role needs the following permissions:
- `bedrock:InvokeModel` (for Claude Sonnet 3.7)
- `ecr:GetAuthorizationToken`
- `ecr:BatchCheckLayerAvailability`
- `ecr:GetDownloadUrlForLayer`
- `ecr:BatchGetImage`
- `logs:CreateLogGroup`
- `logs:CreateLogStream`
- `logs:PutLogEvents`

### 3. Python Dependencies
```bash
pip install bedrock-agentcore-starter-toolkit boto3
```

## Deployment Steps

### Step 1: Install Starter Toolkit

```bash
pip install bedrock-agentcore-starter-toolkit
```

### Step 2: Deploy with One Command

The starter toolkit handles everything automatically:

```bash
# Simple deployment (toolkit creates ECR repo and IAM role)
python deploy.py

# Or with custom settings
python deploy.py \
  --runtime-name "my-market-agent" \
  --region "us-west-2"
```

### Optional: Custom IAM Role

If you want to use a specific IAM role:

```bash
# Create role (optional - toolkit can create one)
aws iam create-role \
  --role-name MarketTrendsAgentRole \
  --assume-role-policy-document file://trust-policy.json

# Deploy with custom role
python deploy.py \
  --role-arn "arn:aws:iam::your-account:role/MarketTrendsAgentRole"
```

### Step 3: Test the Deployed Agent

```bash
# Test using the test script
python test_agent.py
```

## Configuration Files

### `Dockerfile`
Defines the container image with:
- Base AgentCore runtime image
- Python dependencies
- Playwright browser installation
- Application code

### `.dockerignore`
Excludes unnecessary files from the container build.

### `deploy.py`
Deployment script that handles:
- Container building and pushing to ECR
- AgentCore runtime creation
- Configuration management

## Monitoring and Troubleshooting

### CloudWatch Logs
Monitor your agent logs in CloudWatch:
- Log Group: `/aws/bedrock-agentcore/market-trends-agent`
- Check for startup errors and runtime issues

### Health Checks
The agent includes health check endpoints:
- `/ping` - Basic health check
- Monitor in AgentCore console

### Common Issues

1. **Container Build Fails:**
   - Check Dockerfile syntax
   - Ensure all dependencies are in requirements.txt
   - Verify base image availability

2. **Runtime Creation Fails:**
   - Check IAM role permissions
   - Verify ECR image exists and is accessible
   - Check region consistency

3. **Agent Invocation Fails:**
   - Check Bedrock model permissions
   - Verify Claude Sonnet 3.7 access
   - Check browser automation dependencies

## Example Usage

Once deployed, you can invoke the agent:

```python
import boto3
import json
from botocore.config import Config

# Load agent ARN from .agent_arn file
with open('.agent_arn', 'r') as f:
    runtime_arn = f.read().strip()

# Initialize Bedrock AgentCore client
config = Config(read_timeout=120)
client = boto3.client('bedrock-agentcore', region_name='us-east-1', config=config)

# Step 1: Send broker profile in structured format
broker_card_prompt = """Name: Maria Rodriguez
Company: JP Morgan Chase
Role: Senior Investment Advisor
Preferred News Feed: Reuters
Industry Interests: cryptocurrency, fintech, gaming
Investment Strategy: growth investing
Risk Tolerance: aggressive
Client Demographics: millennial retail investors
Geographic Focus: Latin America, Asia-Pacific
Recent Interests: blockchain technology, NFTs, metaverse"""

response = client.invoke_agent_runtime(
    agentRuntimeArn=runtime_arn,
    payload=json.dumps({"prompt": broker_card_prompt})
)

if 'response' in response:
    result = response['response'].read().decode('utf-8')
    print("Agent Response:", result)

# Step 2: Ask for personalized market analysis
analysis_prompt = "What's the latest news on cryptocurrency and fintech stocks?"

response2 = client.invoke_agent_runtime(
    agentRuntimeArn=runtime_arn,
    payload=json.dumps({"prompt": analysis_prompt})
)

if 'response' in response2:
    result2 = response2['response'].read().decode('utf-8')
    print("Personalized Analysis:", result2)
```

## Cleanup

To remove the deployed agent:

```bash
# Delete the runtime (replace with your runtime ID)
aws bedrock-agentcore-control delete-agent-runtime --agent-runtime-id <runtime-id>

# Delete ECR repository
aws ecr delete-repository --repository-name market-trends-agent --force

# Delete IAM role
aws iam detach-role-policy --role-name MarketTrendsAgentRole --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess
aws iam detach-role-policy --role-name MarketTrendsAgentRole --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly
aws iam detach-role-policy --role-name MarketTrendsAgentRole --policy-arn arn:aws:iam::aws:policy/CloudWatchLogsFullAccess
aws iam delete-role --role-name MarketTrendsAgentRole
```

## Support

For issues with:
- **AgentCore Runtime**: Check AWS documentation
- **LangGraph**: Check LangGraph documentation
- **Browser Automation**: Check Playwright documentation
- **Market Data**: Verify data source availability