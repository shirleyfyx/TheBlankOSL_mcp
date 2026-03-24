import tempfile
from mcp.server.fastmcp import FastMCP
from typing import List, Union
from pathlib import Path
import os
import shutil
import aiofiles
import anyio
import platform
import re
import mimetypes
from datetime import datetime
from fnmatch import fnmatch

# Initialize MCP server
mcp = FastMCP("filesystem")

PathLike = Union[str, Path]


def _resolve_path(path: PathLike) -> Path:
    """Expand ~ and resolve to absolute path so '~/Desktop/...' works regardless of cwd."""
    return Path(os.path.expanduser(path)).resolve()


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
    return _resolve_path(path).exists()


@mcp.tool()
async def is_file(path: PathLike) -> bool:
    """Check if a path is a file.

    Args:
        path: Path to check.

    Returns:
        True if the path is a file, False otherwise.
    """
    return _resolve_path(path).is_file()


@mcp.tool()
async def is_dir(path: PathLike) -> bool:
    """Check if a path is a directory.

    Args:
        path: Path to check.

    Returns:
        True if the path is a directory, False otherwise.
    """
    return _resolve_path(path).is_dir()


@mcp.tool()
async def read_file(path: PathLike, encoding: str = "utf-8") -> str:
    """Read the contents of a file asynchronously.

    Args:
        path: Path to the file.
        encoding: File encoding (default 'utf-8').

    Returns:
        Contents of the file as a string.
    """
    async with aiofiles.open(_resolve_path(path), mode="r", encoding=encoding) as f:
        return await f.read()


@mcp.tool()
async def write_file(path: PathLike, content: str, encoding: str = "utf-8") -> None:
    """Write content to a file asynchronously, overwriting if it exists.

    Args:
        path: Path to the file.
        content: Content to write.
        encoding: File encoding (default 'utf-8').
    """
    resolved = _resolve_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(resolved, mode="w", encoding=encoding) as f:
        await f.write(content)


@mcp.tool()
async def append_file(path: PathLike, content: str, encoding: str = "utf-8") -> None:
    """Append content to a file asynchronously.

    Args:
        path: Path to the file.
        content: Content to append.
        encoding: File encoding (default 'utf-8').
    """
    async with aiofiles.open(_resolve_path(path), mode="a", encoding=encoding) as f:
        await f.write(content)


@mcp.tool()
async def mkdir(path: PathLike, parents: bool = False, exist_ok: bool = False) -> None:
    """Create a directory asynchronously.

    Args:
        path: Path of the directory to create.
        parents: Create parent directories if needed.
        exist_ok: Do not raise an error if the directory exists.
    """
    _resolve_path(path).mkdir(parents=parents, exist_ok=exist_ok)


@mcp.tool()
async def listdir(path: PathLike) -> List[str]:
    """List contents of a directory asynchronously.

    Args:
        path: Path to the directory.

    Returns:
        List of file and directory names in the directory.
    """
    return [p.name for p in _resolve_path(path).iterdir()]


@mcp.tool()
async def remove(path: PathLike) -> None:
    """Remove a file, symlink, or directory recursively asynchronously.

    Args:
        path: Path to remove.
    """
    path = _resolve_path(path)
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
    await anyio.to_thread.run_sync(os.chmod, _resolve_path(path), mode)


@mcp.tool()
async def rename(src: PathLike, dst: PathLike) -> None:
    """Rename or move a file or directory asynchronously.

    Args:
        src: Source path.
        dst: Destination path.
    """
    await anyio.to_thread.run_sync(_resolve_path(src).rename, _resolve_path(dst))


@mcp.tool()
async def copy(src: PathLike, dst: PathLike) -> None:
    """Copy a file or directory asynchronously.

    Args:
        src: Source path.
        dst: Destination path.
    """
    src_path = _resolve_path(src)
    dst_path = _resolve_path(dst)
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
    await anyio.to_thread.run_sync(shutil.move, _resolve_path(src), _resolve_path(dst))


@mcp.tool()
async def touch(path: PathLike) -> None:
    """Create an empty file or update modification time asynchronously.

    Args:
        path: Path to the file.
    """
    await anyio.to_thread.run_sync(_resolve_path(path).touch)


"""
Supplementary tools to help guiding LLM identifying the OS information.
"""


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


@mcp.tool()
async def get_temporary_directory_auto() -> str:
    """
    Creates a temporary directory that is automatically cleaned up
    when the Python process ends or the object is garbage collected.

    Returns:
        Path to the temporary directory as a string.
    """
    temp_dir_obj = tempfile.TemporaryDirectory()
    return temp_dir_obj.name


@mcp.tool()
async def search_files(
    directory: PathLike,
    content_pattern: str = None,
    name_pattern: str = "*",
    extension: str = None,
    min_size: int = None,
    max_size: int = None,
    modified_after: str = None,
    modified_before: str = None,
    case_insensitive: bool = False,
) -> List[str]:
    """
    Perform a deep search for files based on combined criteria (grep + find).

    Args:
        directory: The base directory to search in.
        content_pattern: Regex pattern or string to search for INSIDE file content.
        name_pattern: Glob pattern for file names (e.g., 'test_*', '*.py'). Default '*'.
        extension: Specific file extension to filter by (e.g., '.json', '.cpp').
        min_size: Minimum file size in bytes.
        max_size: Maximum file size in bytes.
        modified_after: ISO 8601 datetime string (e.g., '2024-01-01T00:00:00').
        modified_before: ISO 8601 datetime string.
        case_insensitive: If True, content and name matching will be case-insensitive.

    Returns:
        List of absolute file paths that match ALL criteria.
    """
    root_path = _resolve_path(directory)
    if not root_path.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    # Pre-compile regex if provided
    regex = None
    if content_pattern:
        flags = re.IGNORECASE if case_insensitive else 0
        try:
            regex = re.compile(content_pattern, flags)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")

    # Parse dates if provided
    ts_after = (
        datetime.fromisoformat(modified_after).timestamp() if modified_after else None
    )
    ts_before = (
        datetime.fromisoformat(modified_before).timestamp() if modified_before else None
    )

    def _matches_criteria(path: Path) -> bool:
        # 1. Filter by Name Pattern
        name_to_check = path.name
        pattern_to_check = name_pattern
        if case_insensitive:
            name_to_check = name_to_check.lower()
            pattern_to_check = pattern_to_check.lower()

        if not fnmatch(name_to_check, pattern_to_check):
            return False

        # 2. Filter by Extension
        if extension:
            # Normalize extension format (ensure dot prefix)
            target_ext = extension if extension.startswith(".") else f".{extension}"
            if case_insensitive:
                if path.suffix.lower() != target_ext.lower():
                    return False
            else:
                if path.suffix != target_ext:
                    return False

        # Get stats once to reuse
        try:
            stat = path.stat()
        except OSError:
            return False  # Skip files we can't access

        # 3. Filter by Size
        if min_size is not None and stat.st_size < min_size:
            return False
        if max_size is not None and stat.st_size > max_size:
            return False

        # 4. Filter by Modification Time
        if ts_after is not None and stat.st_mtime < ts_after:
            return False
        if ts_before is not None and stat.st_mtime > ts_before:
            return False

        return True

    def _matches_content(path: Path) -> bool:
        """Checks if file content matches the regex pattern."""
        if not regex:
            return True  # No content search requested

        # Skip binary files based on mime guessing to save time/errors
        mime_type, _ = mimetypes.guess_type(path)
        if mime_type and not mime_type.startswith("text"):
            # If strictly binary (like images), skip grep
            return False

        try:
            # Open with error handling for encoding issues
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                # Read line by line to avoid loading massive files into RAM
                for line in f:
                    if regex.search(line):
                        return True
        except (OSError, UnicodeDecodeError):
            return False

        return False

    def _search_op():
        matched_files = []
        for path in root_path.rglob("*"):
            if path.is_file():
                # Check Metadata first (fast)
                if _matches_criteria(path):
                    # Check Content last (slow)
                    if _matches_content(path):
                        matched_files.append(str(path.resolve()))
        return matched_files

    # Run blocking I/O in a thread
    return await anyio.to_thread.run_sync(_search_op)


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport="stdio")
