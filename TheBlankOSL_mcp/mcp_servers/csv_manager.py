import csv
import os
from pathlib import Path
from typing import List, Dict, Union, Any, Optional
from anyio import to_thread  # Updated import to fix IDE type checking
from mcp.server.fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("csv_editor")

PathLike = Union[str, Path]

def _resolve_path(path: PathLike) -> Path:
    """Expand ~ and resolve to absolute path so '~/Desktop/...' works regardless of cwd."""
    return Path(os.path.expanduser(path)).resolve()

# ----------------------------------------------------------------------
# Internal synchronous helpers for CSV operations (run in worker threads)
# ----------------------------------------------------------------------

def _read_csv_sync(path: Path, limit: Optional[int] = None) -> List[Dict[str, str]]:
    with open(path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if limit:
            return [row for _, row in zip(range(limit), reader)]
        return list(reader)

def _get_headers_sync(path: Path) -> List[str]:
    with open(path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        try:
            return next(reader)
        except StopIteration:
            return []

def _create_csv_sync(path: Path, headers: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()

def _append_rows_sync(path: Path, rows: List[Dict[str, str]]) -> None:
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}. Create it first.")
    
    headers = _get_headers_sync(path)
    with open(path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
        writer.writerows(rows)

def _update_rows_sync(path: Path, filter_col: str, filter_val: str, update_data: Dict[str, str]) -> int:
    with open(path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        if not headers:
            raise ValueError("CSV is empty or missing headers.")
        if filter_col not in headers:
            raise ValueError(f"Column '{filter_col}' not found in CSV headers.")
            
        rows = list(reader)

    updated_count = 0
    for row in rows:
        if row.get(filter_col) == str(filter_val):
            row.update({k: str(v) for k, v in update_data.items() if k in headers})
            updated_count += 1

    if updated_count > 0:
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)

    return updated_count

def _delete_rows_sync(path: Path, filter_col: str, filter_val: str) -> int:
    with open(path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        if not headers:
            raise ValueError("CSV is empty or missing headers.")
            
        all_rows = list(reader)

    retained_rows = [row for row in all_rows if row.get(filter_col) != str(filter_val)]
    deleted_count = len(all_rows) - len(retained_rows)

    if deleted_count > 0:
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(retained_rows)

    return deleted_count

def _add_column_sync(path: Path, column_name: str, default_value: str = "") -> None:
    with open(path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        if not headers:
            raise ValueError("CSV is empty or missing headers.")
        if column_name in headers:
            raise ValueError(f"Column '{column_name}' already exists.")
            
        rows = list(reader)

    headers.append(column_name)
    for row in rows:
        row[column_name] = default_value

    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

def _delete_column_sync(path: Path, column_name: str) -> None:
    with open(path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        if not headers:
            raise ValueError("CSV is empty.")
        if column_name not in headers:
            raise ValueError(f"Column '{column_name}' does not exist.")
            
        rows = list(reader)

    headers.remove(column_name)
    for row in rows:
        row.pop(column_name, None)

    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

def _rename_column_sync(path: Path, old_name: str, new_name: str) -> None:
    with open(path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        if not headers:
            raise ValueError("CSV is empty.")
        if old_name not in headers:
            raise ValueError(f"Column '{old_name}' does not exist.")
        if new_name in headers:
            raise ValueError(f"Column '{new_name}' already exists. Choose a different name.")
            
        rows = list(reader)

    # Replace the old header with the new one, preserving order
    headers = [new_name if h == old_name else h for h in headers]
    
    for row in rows:
        # Transfer the value to the new key and remove the old key
        row[new_name] = row.pop(old_name, "")

    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


# ----------------------------
# Exposed MCP Tools
# ----------------------------

@mcp.tool()
async def read_csv(path: PathLike, limit: Optional[int] = None) -> List[Dict[str, str]]:
    """Read contents of a CSV file as a list of dictionaries asynchronously.
    
    Args:
        path: Path to the CSV file.
        limit: Optional maximum number of rows to return (useful for large files).
        
    Returns:
        List of dictionaries where keys are column headers.
    """
    return await to_thread.run_sync(_read_csv_sync, _resolve_path(path), limit)

@mcp.tool()
async def get_csv_headers(path: PathLike) -> List[str]:
    """Get the column headers of a CSV file.
    
    Args:
        path: Path to the CSV file.
        
    Returns:
        List of column header strings.
    """
    return await to_thread.run_sync(_get_headers_sync, _resolve_path(path))

@mcp.tool()
async def create_csv(path: PathLike, headers: List[str]) -> None:
    """Create a new, empty CSV file with the specified headers.
    
    Args:
        path: Path where the CSV should be created.
        headers: List of column names.
    """
    await to_thread.run_sync(_create_csv_sync, _resolve_path(path), headers)

@mcp.tool()
async def append_rows(path: PathLike, rows: List[Dict[str, Any]]) -> None:
    """Append one or more rows to an existing CSV file.
    
    Args:
        path: Path to the CSV file.
        rows: List of dictionaries representing the rows to append. Keys must match headers.
    """
    stringified_rows = [{k: str(v) for k, v in row.items()} for row in rows]
    await to_thread.run_sync(_append_rows_sync, _resolve_path(path), stringified_rows)

@mcp.tool()
async def update_rows(path: PathLike, filter_column: str, filter_value: Any, update_data: Dict[str, Any]) -> str:
    """Update existing rows in a CSV where a specific column matches a value.
    
    Args:
        path: Path to the CSV file.
        filter_column: The column name to search in.
        filter_value: The value to match in the filter_column.
        update_data: Dictionary of column/value pairs to update on matching rows.
        
    Returns:
        A string confirming how many rows were updated.
    """
    count = await to_thread.run_sync(
        _update_rows_sync, 
        _resolve_path(path), 
        filter_column, 
        str(filter_value), 
        update_data
    )
    return f"Successfully updated {count} row(s)."

@mcp.tool()
async def delete_rows(path: PathLike, filter_column: str, filter_value: Any) -> str:
    """Delete rows from a CSV where a specific column matches a value.
    
    Args:
        path: Path to the CSV file.
        filter_column: The column name to search in.
        filter_value: The value to match in the filter_column to trigger deletion.
        
    Returns:
        A string confirming how many rows were deleted.
    """
    count = await to_thread.run_sync(
        _delete_rows_sync, 
        _resolve_path(path), 
        filter_column, 
        str(filter_value)
    )
    return f"Successfully deleted {count} row(s)."

@mcp.tool()
async def add_column(path: PathLike, column_name: str, default_value: Any = "") -> str:
    """Add a new column to an existing CSV file.
    
    Args:
        path: Path to the CSV file.
        column_name: Name of the new column to add.
        default_value: The value to fill into the new column for all existing rows (defaults to empty string).
        
    Returns:
        Success message.
    """
    await to_thread.run_sync(
        _add_column_sync, 
        _resolve_path(path), 
        column_name, 
        str(default_value)
    )
    return f"Successfully added column '{column_name}'."

@mcp.tool()
async def delete_column(path: PathLike, column_name: str) -> str:
    """Delete a column from an existing CSV file.
    
    Args:
        path: Path to the CSV file.
        column_name: Name of the column to delete.
        
    Returns:
        Success message.
    """
    await to_thread.run_sync(
        _delete_column_sync, 
        _resolve_path(path), 
        column_name
    )
    return f"Successfully deleted column '{column_name}'."

@mcp.tool()
async def rename_column(path: PathLike, old_name: str, new_name: str) -> str:
    """Rename a column in an existing CSV file.
    
    Args:
        path: Path to the CSV file.
        old_name: The current name of the column.
        new_name: The new name for the column.
        
    Returns:
        Success message.
    """
    await to_thread.run_sync(
        _rename_column_sync, 
        _resolve_path(path), 
        old_name,
        new_name
    )
    return f"Successfully renamed column '{old_name}' to '{new_name}'."


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')
