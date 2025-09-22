from mcp.server.fastmcp import FastMCP
from typing import List, Union
from pathlib import Path
import os
import shutil
import aiofiles
import anyio
import platform

# Initialize MCP server
mcp = FastMCP("filesystem")

PathLike = Union[str, Path]

# ----------------------------
# File and directory operations
# ----------------------------

@mcp.tool()
async def exists(path: PathLike) -> bool:
    """Check if a path exists.

    Args:
        path: Path to a file or directory.

    Returns:
        True if the path exists, False otherwise.
    """
    return Path(path).exists()


@mcp.tool()
async def is_file(path: PathLike) -> bool:
    """Check if a path is a file.

    Args:
        path: Path to check.

    Returns:
        True if the path is a file, False otherwise.
    """
    return Path(path).is_file()


@mcp.tool()
async def is_dir(path: PathLike) -> bool:
    """Check if a path is a directory.

    Args:
        path: Path to check.

    Returns:
        True if the path is a directory, False otherwise.
    """
    return Path(path).is_dir()


@mcp.tool()
async def read_file(path: PathLike, encoding: str = "utf-8") -> str:
    """Read the contents of a file asynchronously.

    Args:
        path: Path to the file.
        encoding: File encoding (default 'utf-8').

    Returns:
        Contents of the file as a string.
    """
    async with aiofiles.open(path, mode="r", encoding=encoding) as f:
        return await f.read()


@mcp.tool()
async def write_file(path: PathLike, content: str, encoding: str = "utf-8") -> None:
    """Write content to a file asynchronously, overwriting if it exists.

    Args:
        path: Path to the file.
        content: Content to write.
        encoding: File encoding (default 'utf-8').
    """
    async with aiofiles.open(path, mode="w", encoding=encoding) as f:
        await f.write(content)


@mcp.tool()
async def append_file(path: PathLike, content: str, encoding: str = "utf-8") -> None:
    """Append content to a file asynchronously.

    Args:
        path: Path to the file.
        content: Content to append.
        encoding: File encoding (default 'utf-8').
    """
    async with aiofiles.open(path, mode="a", encoding=encoding) as f:
        await f.write(content)


@mcp.tool()
async def mkdir(path: PathLike, parents: bool = False, exist_ok: bool = False) -> None:
    """Create a directory asynchronously.

    Args:
        path: Path of the directory to create.
        parents: Create parent directories if needed.
        exist_ok: Do not raise an error if the directory exists.
    """
    Path(path).mkdir(parents=parents, exist_ok=exist_ok)


@mcp.tool()
async def listdir(path: PathLike) -> List[str]:
    """List contents of a directory asynchronously.

    Args:
        path: Path to the directory.

    Returns:
        List of file and directory names in the directory.
    """
    return [p.name for p in Path(path).iterdir()]


@mcp.tool()
async def remove(path: PathLike) -> None:
    """Remove a file, symlink, or directory recursively asynchronously.

    Args:
        path: Path to remove.
    """
    path = Path(path)
    if path.is_dir():
        # Use a blocking call in a thread so async loop isn't blocked
        await anyio.to_thread.run_sync(shutil.rmtree, path)
    elif path.is_file() or path.is_symlink():
        await anyio.to_thread.run_sync(path.unlink)
    else:
        raise FileNotFoundError(f"No such file or directory: {path}")


@mcp.tool()
async def chmod(path: PathLike, mode: int) -> None:
    """Change permissions of a file or directory asynchronously.

    Args:
        path: Path to modify.
        mode: POSIX-style permission (e.g., 0o644).
    """
    await anyio.to_thread.run_sync(os.chmod, path, mode)


@mcp.tool()
async def rename(src: PathLike, dst: PathLike) -> None:
    """Rename or move a file or directory asynchronously.

    Args:
        src: Source path.
        dst: Destination path.
    """
    await anyio.to_thread.run_sync(Path(src).rename, dst)


@mcp.tool()
async def copy(src: PathLike, dst: PathLike) -> None:
    """Copy a file or directory asynchronously.

    Args:
        src: Source path.
        dst: Destination path.
    """
    src_path = Path(src)
    dst_path = Path(dst)
    if src_path.is_dir():
        await anyio.to_thread.run_sync(shutil.copytree, src_path, dst_path)
    else:
        await anyio.to_thread.run_sync(shutil.copy2, src_path, dst_path)


@mcp.tool()
async def move(src: PathLike, dst: PathLike) -> None:
    """Move a file or directory asynchronously.

    Args:
        src: Source path.
        dst: Destination path.
    """
    await anyio.to_thread.run_sync(shutil.move, src, dst)


@mcp.tool()
async def touch(path: PathLike) -> None:
    """Create an empty file or update modification time asynchronously.

    Args:
        path: Path to the file.
    """
    await anyio.to_thread.run_sync(Path(path).touch)

'''
Supplementary tools to help guiding LLM identifying the OS information.
'''
@mcp.tool()
async def get_home_directory() -> str:
    """Return the path of the current user's home directory.

    Returns:
        str: Absolute path to the home directory.
    """
    return os.path.expanduser("~")

@mcp.tool()
async def get_os() -> str:
    """Return the name of the current operating system.

    Returns:
        str: OS name (e.g., 'Windows', 'Linux', 'Darwin' for macOS).
    """
    return platform.system()

if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')
