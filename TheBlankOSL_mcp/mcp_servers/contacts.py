from typing import List, Optional
import aiosqlite
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("contacts")
DB_PATH = Path("contacts.sqlite3")

async def init_db() -> None:
    """
    Initialize the SQLite database and create tables if they don't exist.
    This is safe to call multiple times.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            birthday TEXT
        );
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email);")
        await db.commit()

@mcp.tool()
async def list_contacts() -> List[dict]:
    """List all contacts.

    Returns:
        A list of contacts (each contact is a dict).
    """
    await init_db()

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, name, email, phone, birthday FROM contacts ORDER BY name ASC"
        )
        rows = await cur.fetchall()

    return [
        {"id": r[0], "name": r[1], "email": r[2], "phone": r[3], "birthday": r[4]}
        for r in rows
    ]

@mcp.tool()
async def add_contact(
    name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    birthday: Optional[str] = None,
) -> str:
    """Add a contact to the database.

    Args:
        name: Contact name (required).
        email: Contact email (optional).
        phone: Contact phone (optional).
        birthday: Contact birthday in YYYY-MM-DD format (optional).

    Returns:
        A confirmation string including the new contact id.
    """
    await init_db()

    name = name.strip()
    if not name:
        return {"ok": False, "error": "Name cannot be empty."}

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO contacts (name, email, phone, birthday) VALUES (?, ?, ?, ?)",
            (name, email, phone, birthday),
        )
        await db.commit()
        new_id = cur.lastrowid

    return {"ok": True, "id": new_id, "name": name}

@mcp.tool()
async def update_contact(
    contact_id: int,
    name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    birthday: Optional[str] = None,
) -> str:
    """Update a contact. Provide only fields you want to change.

    Args:
        contact_id: The contact id to update.
        name: New name (optional).
        email: New email (optional).
        phone: New phone (optional).
        birthday: New birthday in YYYY-MM-DD format (optional).

    Returns:
        A confirmation string.
    """
    await init_db()

    updates = []
    params = []

    if name is not None:
        name = name.strip()
        if not name:
            return {"ok": False, "error": "Name cannot be empty."}
        updates.append("name=?")
        params.append(name)

    if email is not None:
        updates.append("email=?")
        params.append(email)

    if phone is not None:
        updates.append("phone=?")
        params.append(phone)

    if birthday is not None:
        updates.append("birthday=?")
        params.append(birthday)

    if not updates:
        return {"ok": False, "error": "Nothing to update. Provide at least one field."}

    params.append(contact_id)

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            f"UPDATE contacts SET {', '.join(updates)} WHERE id=?",
            tuple(params),
        )
        await db.commit()

        if cur.rowcount == 0:
            return {"ok": False, "error": " No contact found with id"}

    return {"ok": True}

@mcp.tool()
async def delete_contact(contact_id: int) -> str:
    """Delete a contact by id.

    Returns:
        A confirmation string.
    """
    await init_db()

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM contacts WHERE id=?", (contact_id,))
        await db.commit()

        if cur.rowcount == 0:
            return {"ok": False, "error": "No contacts found"}

    return {"ok": True}

@mcp.tool()
async def search_contacts(query: str, limit: int = 20) -> List[dict]:
    """Search contacts across name, email, phone, and birthday.

    Returns:
        List of matching contacts as dicts.
    """
    await init_db()

    q = (query or "").strip()
    if not q:
        return []

    like = f"%{q}%"

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT id, name, email, phone, birthday
            FROM contacts
            WHERE name LIKE ?
               OR email LIKE ?
               OR phone LIKE ?
               OR birthday LIKE ?
            ORDER BY name ASC
            LIMIT ?
            """,
            (like, like, like, like, limit),
        )
        rows = await cur.fetchall()

    return [
        {"id": r[0], "name": r[1], "email": r[2], "phone": r[3], "birthday": r[4]}
        for r in rows
    ]


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport="stdio")