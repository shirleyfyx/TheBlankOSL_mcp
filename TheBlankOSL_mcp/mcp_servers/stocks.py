"""Stock MCP Server using Alpha Vantage API."""

import datetime
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

# Initialize MCP
mcp = FastMCP("stocks")

# Alpha Vantage config
ALPHA_URL = "https://www.alphavantage.co/query"
API_KEY = "AGIYJRZ4EDWB9MMN" # Public API key for testing

if not API_KEY:
    raise RuntimeError("⚠️ Missing ALPHAVANTAGE_API_KEY environment variable.")

# Simple cache decorator (5 min TTL)
def cache_ttl(ttl_seconds: int):
    """Cache function results for a given TTL in seconds."""
    def decorator(func):
        cache = {}
        def wrapper(*args):
            key = args
            now = datetime.datetime.now().timestamp()
            if key in cache:
                result, ts = cache[key]
                if now - ts < ttl_seconds:
                    return result
            result = func(*args)
            cache[key] = (result, now)
            return result
        return wrapper
    return decorator

# -------------------- Helper Functions --------------------

async def fetch_alpha(params: dict) -> dict[str, Any] | None:
    """Make a request to Alpha Vantage."""
    params["apikey"] = API_KEY
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(ALPHA_URL, params=params, timeout=20.0)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:  #pylint: disable=broad-except
            print(f"Error fetching {params.get('symbol')}: {e}")
            return None

# -------------------- MCP Tools --------------------

@mcp.tool()
async def get_stock_price(symbol: str) -> str:
    """Get latest stock price and change info."""
    data = await fetch_alpha({"function": "GLOBAL_QUOTE", "symbol": symbol})
    quote = data.get("Global Quote") if data else None
    if not quote:
        return f"Could not retrieve data for '{symbol}'."

    return f"""
{symbol}
Price: {quote.get('05. price', 'N/A')}
Open: {quote.get('02. open', 'N/A')}
High: {quote.get('03. high', 'N/A')}
Low: {quote.get('04. low', 'N/A')}
Change: {quote.get('09. change', 'N/A')} ({quote.get('10. change percent', 'N/A')})
Volume: {quote.get('06. volume', 'N/A')}
Latest trading day: {quote.get('07. latest trading day', 'N/A')}
"""

@mcp.tool()
async def get_historical(symbol: str, days: int = 5) -> str:
    """Get last N days of closing prices."""
    data = await fetch_alpha({"function": "TIME_SERIES_DAILY", "symbol": symbol})
    ts = data.get("Time Series (Daily)") if data else None
    if not ts:
        return f"Could not retrieve historical data for '{symbol}'."

    sorted_days = sorted(ts.keys(), reverse=True)[:days]
    lines = [f"{day}: {ts[day]['4. close']}" for day in sorted_days]
    return f"{symbol} (last {days} days)\n" + "\n".join(lines)

@mcp.tool()
async def get_company_overview(symbol: str) -> str:
    """Get company description and financial info."""
    data = await fetch_alpha({"function": "OVERVIEW", "symbol": symbol})
    if not data or "Symbol" not in data:
        return f"Could not retrieve overview for '{symbol}'."

    return f"""
{data.get('Name', symbol)} ({data.get('Symbol')})
Sector: {data.get('Sector', 'N/A')}
Industry: {data.get('Industry', 'N/A')}
Market Cap: {data.get('MarketCapitalization', 'N/A')}
P/E Ratio: {data.get('PERatio', 'N/A')}
Description: {data.get('Description', 'N/A')}
"""

@mcp.tool()
async def compare_stocks(symbol1: str, symbol2: str) -> str:
    """Compare two stocks by price and change percent."""
    quote1 = (await fetch_alpha({"function": "GLOBAL_QUOTE", "symbol": symbol1})).get("Global Quote")
    quote2 = (await fetch_alpha({"function": "GLOBAL_QUOTE", "symbol": symbol2})).get("Global Quote")
    if not quote1 or not quote2:
        return "Could not retrieve data for comparison."

    price1 = float(quote1.get("05. price", 0))
    price2 = float(quote2.get("05. price", 0))
    percent1 = quote1.get("10. change percent", "N/A")
    percent2 = quote2.get("10. change percent", "N/A")

    winner = symbol1 if price1 > price2 else symbol2
    return f"""
Comparison:
{symbol1} Price: {price1} ({percent1})
{symbol2} Price: {price2} ({percent2})
Higher Price: {winner}
"""

@mcp.tool()
async def get_top_movers(symbols: list[str] = ["AAPL", "MSFT", "TSLA", "NVDA", "GOOG"]) -> str:
    """Return top 3 gainers and losers by % change."""
    movers = []
    for sym in symbols:
        quote = (await fetch_alpha({"function": "GLOBAL_QUOTE", "symbol": sym})).get("Global Quote")
        if quote:
            try:
                change_pct = float(quote.get("10. change percent", "0%").replace("%",""))
                movers.append((sym, change_pct))
            except:
                continue
    if not movers:
        return "No data for top movers."

    movers.sort(key=lambda x: x[1], reverse=True)
    top = movers[:3]
    bottom = movers[-3:]
    result = "Top 3 Gainers:\n" + "\n".join([f"{s}: {p}%" for s,p in top])
    result += "\n\nTop 3 Losers:\n" + "\n".join([f"{s}: {p}%" for s,p in bottom])
    return result

# -------------------- Run MCP --------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
