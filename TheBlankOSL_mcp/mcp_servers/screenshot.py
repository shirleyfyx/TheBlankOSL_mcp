from mcp.server.fastmcp import FastMCP
from io import BytesIO
import pyautogui
import base64

# Initialize MCP server
mcp = FastMCP("screenshot")

@mcp.tool()
def fullscreen() -> dict:
    """Take a screenshot of the entire screen and return it as an image.
    
    Returns:
        dict: Contains image bytes and MIME type for MCP clients.
    """
    try:
        # Capture screenshot
        img = pyautogui.screenshot()
        
        # Convert to bytes
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        
        # Encode as base64 for JSON transport
        image_data = buf.getvalue()
        encoded_data = base64.b64encode(image_data).decode('utf-8')
        
        # Return image data in proper format
        return {
            "data": encoded_data,
            "mime_type": "image/png",
            "encoding": "base64"
        }
    except Exception as e:
        return {
            "error": f"Failed to capture screenshot: {str(e)}",
            "data": None,
            "mime_type": None
        }

if __name__ == "__main__":
    mcp.run(transport="stdio")
