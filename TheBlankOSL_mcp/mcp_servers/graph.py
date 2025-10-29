from mcp.server.fastmcp import FastMCP
from typing import List, Union, Literal
import matplotlib.pyplot as plt
import io
import anyio

# Initialize MCP server
mcp = FastMCP("svg_plotter")

@mcp.tool()
async def plot_data(
    x: List[Union[int, float, str]],
    y: List[Union[int, float, str]],
    kind: Literal["line", "scatter"] = "line",
    title: str = "Data Plot",
    xlabel: str = "X-axis",
    ylabel: str = "Y-axis",
    width: float = 6,
    height: float = 4
) -> dict:
    """Plot x and y data and return it as an SVG in a dictionary.

    Args:
        x: List of x-values (int, float, or str).
        y: List of y-values (int, float, or str).
        kind: 'line' or 'scatter'.
        title: Plot title.
        xlabel: Label for X-axis.
        ylabel: Label for Y-axis.
        width: Figure width in inches.
        height: Figure height in inches.

    Returns:
        dict: {
            "type": "image/svg",
            "data": "<SVG content as string>"
        }
    """
    if len(x) != len(y):
        raise ValueError("x and y must be the same length")

    def _plot() -> dict:
        plt.figure(figsize=(width, height))
        if kind == "scatter":
            plt.scatter(x, y, color="blue")
        else:
            plt.plot(x, y, color="blue")
        plt.title(title)
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        plt.grid(True)

        buffer = io.StringIO()
        plt.savefig(buffer, format="svg")
        plt.close()
        buffer.seek(0)
        svg_data = buffer.getvalue()

        return {"type": "image/svg", "data": svg_data}

    return await anyio.to_thread.run_sync(_plot)


if __name__ == "__main__":
    mcp.run(transport="stdio")
