import zipfile
import tarfile
import anyio
import os
from typing import List, Union, Literal
from pathlib import Path
from mcp.server.fastmcp import FastMCP
import py7zr

# Initialize the MCP server
mcp = FastMCP("archive-manager")

PathLike = Union[str, Path]
TarCompression = Literal["gzip", "bz2", "xz", "none"]

def _resolve_path(path: PathLike) -> Path:
    """Expand ~ and resolve to an absolute path."""
    return Path(os.path.expanduser(str(path))).resolve()


# ---------------------------------------------------------------------
# ZIP Operations
# ---------------------------------------------------------------------

@mcp.tool()
async def compress_zip(sources: List[PathLike], output_path: PathLike) -> str:
    """
    Compress files or directories into a standard .zip archive.

    Args:
        sources: List of file or directory paths to include.
        output_path: Destination path for the archive.
    """
    out_path = _resolve_path(output_path)
    # Ensure correct extension if user forgot it
    if not out_path.name.lower().endswith(".zip"):
        out_path = out_path.with_suffix(".zip")
    
    source_paths = [_resolve_path(p) for p in sources]

    def _op():
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for src in source_paths:
                if not src.exists():
                    raise FileNotFoundError(f"Source not found: {src}")
                
                if src.is_file():
                    zf.write(src, arcname=src.name)
                elif src.is_dir():
                    for file in src.rglob("*"):
                        if file.is_file():
                            zf.write(file, arcname=file.relative_to(src.parent))
        return str(out_path)

    return await anyio.to_thread.run_sync(_op)


@mcp.tool()
async def decompress_zip(archive_path: PathLike, extract_to: PathLike) -> str:
    """
    Decompress a .zip archive.

    Args:
        archive_path: Path to the .zip file.
        extract_to: Destination directory.
    """
    arc_path = _resolve_path(archive_path)
    dest_path = _resolve_path(extract_to)

    def _op():
        if not arc_path.exists():
            raise FileNotFoundError(f"Archive not found: {arc_path}")
            
        dest_path.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(arc_path, 'r') as zf:
            zf.extractall(dest_path)
        return str(dest_path)

    return await anyio.to_thread.run_sync(_op)


# ---------------------------------------------------------------------
# 7-Zip Operations
# ---------------------------------------------------------------------

@mcp.tool()
async def compress_7z(sources: List[PathLike], output_path: PathLike) -> str:
    """
    Compress files into a .7z archive (Requires py7zr).

    Args:
        sources: List of file or directory paths.
        output_path: Destination path.
    """
    out_path = _resolve_path(output_path)
    if not out_path.name.lower().endswith(".7z"):
        out_path = out_path.with_suffix(".7z")

    source_paths = [_resolve_path(p) for p in sources]

    def _op():
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with py7zr.SevenZipFile(out_path, 'w') as zf:
            for src in source_paths:
                if not src.exists():
                    raise FileNotFoundError(f"Source not found: {src}")

                if src.is_file():
                    zf.write(src, arcname=src.name)
                elif src.is_dir():
                    zf.writeall(src, arcname=src.name)
        return str(out_path)

    return await anyio.to_thread.run_sync(_op)


@mcp.tool()
async def decompress_7z(archive_path: PathLike, extract_to: PathLike) -> str:
    """
    Decompress a .7z archive (Requires py7zr).

    Args:
        archive_path: Path to the .7z file.
        extract_to: Destination directory.
    """
    arc_path = _resolve_path(archive_path)
    dest_path = _resolve_path(extract_to)

    def _op():
        if not arc_path.exists():
            raise FileNotFoundError(f"Archive not found: {arc_path}")

        dest_path.mkdir(parents=True, exist_ok=True)
        with py7zr.SevenZipFile(arc_path, 'r') as zf:
            zf.extractall(dest_path)
        return str(dest_path)

    return await anyio.to_thread.run_sync(_op)


# ---------------------------------------------------------------------
# TAR Operations (Gzip, Bzip2, XZ)
# ---------------------------------------------------------------------

@mcp.tool()
async def compress_tar(
    sources: List[PathLike], 
    output_path: PathLike, 
    compression: TarCompression = "gzip"
) -> str:
    """
    Compress files into a tarball (.tar, .tar.gz, .tar.xz, .tar.bz2).

    Args:
        sources: List of file or directory paths.
        output_path: Destination path.
        compression: Algorithm to use ('gzip', 'bz2', 'xz', or 'none').
                     Default is 'gzip'.
    """
    out_path = _resolve_path(output_path)
    source_paths = [_resolve_path(p) for p in sources]

    # Map inputs to tarfile modes and extensions
    mode_map = {
        "gzip": ("w:gz", ".tar.gz"),
        "bz2":  ("w:bz2", ".tar.bz2"),
        "xz":   ("w:xz", ".tar.xz"),
        "none": ("w", ".tar")
    }
    
    write_mode, default_ext = mode_map.get(compression, ("w:gz", ".tar.gz"))

    # Append extension only if user didn't provide a valid one
    if not str(out_path).lower().endswith(tuple([ext for _, ext in mode_map.values()])):
        # Check if it ends in .tgz, .tbz, etc, otherwise append default
        if not str(out_path).lower().endswith(('.tgz', '.tbz', '.txz')):
             out_path = Path(str(out_path) + default_ext)

    def _op():
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(out_path, write_mode) as tf:
            for src in source_paths:
                if not src.exists():
                    raise FileNotFoundError(f"Source not found: {src}")

                if src.is_file():
                    tf.add(src, arcname=src.name)
                elif src.is_dir():
                    for file in src.rglob("*"):
                        if file.is_file():
                            tf.add(file, arcname=file.relative_to(src.parent))
        return str(out_path)

    return await anyio.to_thread.run_sync(_op)


@mcp.tool()
async def decompress_tar(archive_path: PathLike, extract_to: PathLike) -> str:
    """
    Decompress a tarball. Auto-detects compression (gzip/bz2/xz).

    Args:
        archive_path: Path to the tar archive.
        extract_to: Destination directory.
    """
    arc_path = _resolve_path(archive_path)
    dest_path = _resolve_path(extract_to)

    def _op():
        if not arc_path.exists():
            raise FileNotFoundError(f"Archive not found: {arc_path}")

        if not tarfile.is_tarfile(arc_path):
             raise ValueError(f"Not a valid tar file: {arc_path}")

        dest_path.mkdir(parents=True, exist_ok=True)
        
        # 'r:*' allows tarfile to transparently open gzip/bz2/xz
        with tarfile.open(arc_path, 'r:*') as tf:
            # Security check for 'Zip Slip' / 'Tar Slip' vulnerability
            def is_safe(members):
                for member in members:
                    member_path = (dest_path / member.name).resolve()
                    if dest_path not in member_path.parents:
                        # Log or raise error if path attempts to escape destination
                        raise PermissionError(f"Security blocked: Archive contains unsafe path {member.name}")
                    yield member

            tf.extractall(dest_path, members=is_safe(tf))
        return str(dest_path)

    return await anyio.to_thread.run_sync(_op)


if __name__ == "__main__":
    # Start the MCP server
    mcp.run(transport='stdio')
