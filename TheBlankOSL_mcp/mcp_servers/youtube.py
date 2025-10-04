from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from dataclasses import dataclass
from typing import List
from googleapiclient.discovery import build
import html
import os

# Replace this with your actual API key
load_dotenv()
API_KEY = os.getenv("YOUTUBE_API_KEY")

# Initialize MCP server
mcp = FastMCP("youtube")

@dataclass
class Result:
    ID: str
    Title: str
    Description: str
    ChannelID: str
    ChannelTitle: str
    PublishedAt: str
    Thumbnail: str

# Build YouTube API client
youtube = build("youtube", "v3", developerKey=API_KEY)

@mcp.tool()
async def search(query: str, max_results: int = 5) -> List[Result]:
    """Search YouTube videos using official API.

    Args:
        query: Search query string
        max_results: Maximum number of results (default 5)

    Returns:
        List of Result objects
    """
    request = youtube.search().list(
        q=query,
        part="snippet",
        type="video",
        maxResults=max_results
    )
    response = request.execute()

    results = []
    for item in response.get("items", []):
        snippet = item["snippet"]
        results.append(Result(
            ID=item["id"]["videoId"],
            Title=html.unescape(snippet["title"]),
            Description=html.unescape(snippet["description"]),
            ChannelID=snippet["channelId"],
            ChannelTitle=html.unescape(snippet["channelTitle"]),
            PublishedAt=snippet["publishedAt"],
            Thumbnail=snippet["thumbnails"]["high"]["url"] if "high" in snippet["thumbnails"] else ""
        ))
    return results

if __name__ == "__main__":
    mcp.run(transport="stdio")
