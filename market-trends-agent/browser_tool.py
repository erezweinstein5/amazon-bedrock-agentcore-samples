import time
from playwright.sync_api import sync_playwright, Playwright, BrowserType
from bedrock_agentcore.tools.browser_client import browser_session
from strands import tool

def get_stock_data_with_browser(playwright: Playwright, symbol: str) -> str:
    """Internal function to get stock data using Bedrock AgentCore browser session"""
    with browser_session('us-west-2') as client:
        print(f"📡 Browser session started for {symbol}...")
        ws_url, headers = client.generate_ws_headers()
        
        chromium: BrowserType = playwright.chromium
        browser = chromium.connect_over_cdp(ws_url, headers=headers)
        
        try:
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.pages[0] if context.pages else context.new_page()
            
            # Try different URLs for better results
            urls_to_try = [
                f"https://www.google.com/finance/quote/{symbol}:NASDAQ",
                f"https://www.google.com/finance/quote/{symbol}",
                f"https://finance.yahoo.com/quote/{symbol}",
                f"https://www.marketwatch.com/investing/stock/{symbol}"
            ]
            
            for url in urls_to_try:
                try:
                    print(f"🌐 Navigating to {url}...")
                    page.goto(url, wait_until="domcontentloaded")
                    time.sleep(2)
                    
                    title = page.title()
                    
                    # Try to find price elements with common selectors
                    price_selectors = [
                        '[data-symbol] [data-field="regularMarketPrice"]',
                        '.Fw\\(b\\).Fz\\(36px\\)',
                        '[data-testid="qsp-price"]',
                        '.YMlKec.fxKbKc'  # Google Finance price
                    ]
                    
                    price = None
                    for selector in price_selectors:
                        try:
                            price_element = page.query_selector(selector)
                            if price_element:
                                price = price_element.inner_text()
                                break
                        except:
                            continue
                    
                    if price:
                        # Try to get additional info
                        change = None
                        change_selectors = [
                            '[data-field="regularMarketChange"]',
                            '[data-testid="qsp-price-change"]',
                            '.JwB6zf'  # Google Finance change
                        ]
                        
                        for selector in change_selectors:
                            try:
                                change_element = page.query_selector(selector)
                                if change_element:
                                    change = change_element.inner_text()
                                    break
                            except:
                                continue
                        
                        result = f"Stock data for {symbol}:\nPrice: {price}"
                        if change:
                            result += f"\nChange: {change}"
                        result += f"\nSource: {url}"
                        return result
                        
                except Exception as e:
                    print(f"❌ Error with {url}: {e}")
                    continue
            
            # Fallback: get page content and try to extract any useful info
            try:
                page.goto(f"https://finance.yahoo.com/quote/{symbol}")
                content = page.inner_text('body')
                lines = [line.strip() for line in content.split('\n') if line.strip()]
                
                # Look for lines that might contain price info
                relevant_lines = []
                for line in lines:
                    if (symbol.upper() in line or 
                        any(word in line.lower() for word in ['price', 'usd', '$', 'market', 'stock'])):
                        relevant_lines.append(line)
                        if len(relevant_lines) >= 5:
                            break
                
                if relevant_lines:
                    return f"Stock data for {symbol}:\n" + "\n".join(relevant_lines)
                else:
                    return f"Retrieved page for {symbol} but couldn't extract price information. Title: {title}"
                    
            except Exception as e:
                return f"Error extracting data for {symbol}: {str(e)}"
                
        finally:
            print("🔒 Closing browser session...")
            if not page.is_closed():
                page.close()
            browser.close()

def search_bloomberg_with_browser(playwright: Playwright, query: str) -> str:
    """Internal function to search Bloomberg using Bedrock AgentCore browser session"""
    with browser_session('us-west-2') as client:
        print(f"📡 Browser session started for Bloomberg search: {query}...")
        ws_url, headers = client.generate_ws_headers()
        
        chromium: BrowserType = playwright.chromium
        browser = chromium.connect_over_cdp(ws_url, headers=headers)
        
        try:
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.pages[0] if context.pages else context.new_page()
            
            url = f"https://www.bloomberg.com/search?query={query}"
            print(f"🌐 Navigating to Bloomberg search...")
            page.goto(url, wait_until="domcontentloaded")
            time.sleep(3)  # Wait for search results
            
            # Get page content
            content = page.inner_text('body')
            
            # Extract headlines (simplified approach)
            lines = content.split('\n')
            headlines = []
            
            for line in lines:
                line = line.strip()
                # Look for lines that might be headlines (reasonable length, contains relevant words)
                if (20 < len(line) < 200 and 
                    any(word in line.lower() for word in ['stock', 'market', 'company', 'business', 'economy', 'financial'])):
                    headlines.append(line)
                    if len(headlines) >= 5:  # Limit to 5 headlines
                        break
            
            if headlines:
                return f"Bloomberg News for '{query}':\n" + "\n".join([f"- {h}" for h in headlines])
            else:
                return f"Searched Bloomberg for '{query}' but couldn't extract specific headlines. URL: {url}"
                
        except Exception as e:
            return f"Error searching Bloomberg for '{query}': {str(e)}"
            
        finally:
            print("🔒 Closing browser session...")
            if not page.is_closed():
                page.close()
            browser.close()

@tool
def get_stock_data(symbol: str) -> str:
    """
    Get stock data from financial sources for a given symbol using Bedrock AgentCore browser.
    
    Args:
        symbol (str): Stock symbol to look up (e.g., 'AAPL', 'GOOGL', 'TSLA')
    
    Returns:
        str: Stock information including price and other details
    """
    try:
        with sync_playwright() as p:
            return get_stock_data_with_browser(p, symbol)
    except Exception as e:
        return f"Error accessing financial data for {symbol}: {str(e)}"

@tool
def search_bloomberg_news(query: str) -> str:
    """
    Search Bloomberg for business news and headlines using Bedrock AgentCore browser.
    
    Args:
        query (str): Search query for business news (e.g., 'artificial intelligence', 'tech stocks')
    
    Returns:
        str: News headlines and information from Bloomberg
    """
    try:
        with sync_playwright() as p:
            return search_bloomberg_with_browser(p, query)
    except Exception as e:
        return f"Error searching Bloomberg for '{query}': {str(e)}"