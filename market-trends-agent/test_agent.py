#!/usr/bin/env python3
"""
Test script for the Market Trends Agent
Requires AWS credentials (run 'mwinit' first)
"""

from market_trends_agent import market_trends_agent_local

def test_stock_data():
    """Test getting stock data"""
    print("Testing stock data retrieval...")
    payload = {"prompt": "Get me the current stock price for Apple (AAPL)"}
    response = market_trends_agent_local(payload)
    print(f"Response: {response}")
    print("-" * 50)

def test_bloomberg_news():
    """Test Bloomberg news search"""
    print("Testing Bloomberg news search...")
    payload = {"prompt": "Search for recent news about artificial intelligence stocks"}
    response = market_trends_agent_local(payload)
    print(f"Response: {response}")
    print("-" * 50)

def test_multiple_stocks():
    """Test multiple stock analysis"""
    print("Testing multiple stock analysis...")
    payload = {"prompt": "Compare the stock prices of Apple, Google, and Tesla"}
    response = market_trends_agent_local(payload)
    print(f"Response: {response}")
    print("-" * 50)

if __name__ == "__main__":
    print("Market Trends Agent Test Suite")
    print("=" * 50)
    print("Note: Requires AWS credentials. Run 'mwinit' if you get credential errors.")
    print()
    
    try:
        test_stock_data()
        test_bloomberg_news()
        test_multiple_stocks()
        print("All tests completed!")
    except Exception as e:
        print(f"Test failed with error: {e}")
        if "CredentialRetrievalError" in str(e):
            print("\n💡 Tip: Run 'mwinit' to authenticate with AWS first.")