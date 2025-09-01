import time
from playwright.sync_api import sync_playwright, Playwright, BrowserType
from bedrock_agentcore.tools.browser_client import browser_session
from langchain_core.tools import tool
from langchain_aws import ChatBedrock

def get_stock_data_with_browser(playwright: Playwright, symbol: str) -> str:
    """Get stock data using browser"""
    with browser_session('us-east-1') as client:
        ws_url, headers = client.generate_ws_headers()
        chromium: BrowserType = playwright.chromium
        browser = chromium.connect_over_cdp(ws_url, headers=headers)
        
        try:
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.pages[0] if context.pages else context.new_page()
            
            page.goto(f"https://finance.yahoo.com/quote/{symbol}")
            time.sleep(2)
            content = page.inner_text('body')
            
            # Use LLM to extract stock data
            llm = ChatBedrock(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0", region_name="us-east-1")
            prompt = f"Extract stock price and key information for {symbol} from this page content. Be concise:\n\n{content[:3000]}"
            result = llm.invoke(prompt).content
            return result
                
        finally:
            if not page.is_closed():
                page.close()
            browser.close()

def search_news_with_browser(playwright: Playwright, query: str, news_source: str = "bloomberg") -> str:
    """Generic news search using browser and LLM analysis"""
    with browser_session('us-east-1') as client:
        ws_url, headers = client.generate_ws_headers()
        chromium: BrowserType = playwright.chromium
        browser = chromium.connect_over_cdp(ws_url, headers=headers)
        
        try:
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.pages[0] if context.pages else context.new_page()
            
            # Map news sources to URLs
            news_urls = {
                "bloomberg": f"https://www.bloomberg.com/search?query={query}",
                "reuters": f"https://www.reuters.com/search/news?blob={query}",
                "cnbc": f"https://www.cnbc.com/search/?query={query}",
                "wall street journal": f"https://www.wsj.com/search?query={query}",
                "wsj": f"https://www.wsj.com/search?query={query}",
                "financial times": f"https://www.ft.com/search?q={query}",
                "ft": f"https://www.ft.com/search?q={query}",
                "dow jones": f"https://www.dowjones.com/search/?q={query}"
            }
            
            # Get URL for news source
            source_key = news_source.lower()
            url = news_urls.get(source_key, f"https://www.bloomberg.com/search?query={query}")
            
            page.goto(url)
            time.sleep(3)
            content = page.inner_text('body')
            
            # Use LLM to extract headlines and highlights
            llm = ChatBedrock(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0", region_name="us-east-1")
            prompt = f"Extract the main news headlines and key highlights about '{query}' from this {news_source} page. Focus on financial and market-relevant news:\n\n{content[:4000]}"
            result = llm.invoke(prompt).content
            return result
                
        finally:
            if not page.is_closed():
                page.close()
            browser.close()

@tool
def get_stock_data(symbol: str) -> str:
    """Get stock data for a given symbol"""
    try:
        with sync_playwright() as p:
            return get_stock_data_with_browser(p, symbol)
    except Exception as e:
        return f"Error getting stock data for {symbol}: {str(e)}"



@tool
def search_news(query: str, news_source: str = "bloomberg") -> str:
    """
    Search any news source for business news.
    
    Args:
        query (str): Search query
        news_source (str): News source (bloomberg, reuters, cnbc, wsj, financial times, dow jones)
    
    Returns:
        str: News headlines and highlights
    """
    try:
        with sync_playwright() as p:
            return search_news_with_browser(p, query, news_source)
    except Exception as e:
        return f"Error searching {news_source} for '{query}': {str(e)}"