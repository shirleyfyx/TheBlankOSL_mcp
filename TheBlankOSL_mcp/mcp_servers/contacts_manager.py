from typing import List, Optional
import aiosqlite
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("contacts")
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "contacts.sqlite3"


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
            birthday TEXT,
            age INTEGER,
            address TEXT,
            notes TEXT
        );
        """)

        # --- migrations for older DBs ---
        cur = await db.execute("PRAGMA table_info(contacts);")
        cols = {row[1] for row in await cur.fetchall()}

        if "age" not in cols:
            await db.execute("ALTER TABLE contacts ADD COLUMN age INTEGER;")
        if "address" not in cols:
            await db.execute("ALTER TABLE contacts ADD COLUMN address TEXT;")
        if "notes" not in cols:
            await db.execute("ALTER TABLE contacts ADD COLUMN notes TEXT;")

        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email);"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_contacts_age ON contacts(age);"
        )
        await db.commit()


@mcp.tool()
async def list_contacts() -> List[dict]:
    """List all contacts."""
    await init_db()

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT id, name, email, phone, birthday, age, address, notes
            FROM contacts
            ORDER BY name ASC
            """
        )
        rows = await cur.fetchall()

    return [
        {
            "id": r[0],
            "name": r[1],
            "email": r[2],
            "phone": r[3],
            "birthday": r[4],
            "age": r[5],
            "address": r[6],
            "notes": r[7],
        }
        for r in rows
    ]


@mcp.tool()
async def add_contact(
    name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    birthday: Optional[str] = None,
    age: Optional[int] = None,
    address: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict:
    """Add a contact to the database."""
    await init_db()

    name = name.strip()
    if not name:
        return {"ok": False, "error": "Name cannot be empty."}

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO contacts (name, email, phone, birthday, age, address, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (name, email, phone, birthday, age, address, notes),
        )
        await db.commit()

    return {"ok": True, "id": cur.lastrowid, "name": name}


@mcp.tool()
async def update_contact(
    contact_id: int,
    name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    birthday: Optional[str] = None,
    age: Optional[int] = None,
    address: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict:
    """Update a contact."""
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

    if age is not None:
        updates.append("age=?")
        params.append(age)

    if address is not None:
        updates.append("address=?")
        params.append(address)

    if notes is not None:
        updates.append("notes=?")
        params.append(notes)

    if not updates:
        return {"ok": False, "error": "Nothing to update."}

    params.append(contact_id)

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            f"UPDATE contacts SET {', '.join(updates)} WHERE id=?",
            tuple(params),
        )
        await db.commit()

        if cur.rowcount == 0:
            return {"ok": False, "error": f"No contact found with id={contact_id}"}

    async with aiosqlite.connect(DB_PATH) as db:
        cur2 = await db.execute(
            """
            SELECT id, name, email, phone, birthday, age, address, notes
            FROM contacts
            WHERE id=?
            """,
            (contact_id,),
        )
        row = await cur2.fetchone()

    return {
        "ok": True,
        "contact": {
            "id": row[0],
            "name": row[1],
            "email": row[2],
            "phone": row[3],
            "birthday": row[4],
            "age": row[5],
            "address": row[6],
            "notes": row[7],
        },
    }


@mcp.tool()
async def delete_contact(contact_id: int) -> dict:
    """Delete an entire contact by id."""
    await init_db()

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM contacts WHERE id=?", (contact_id,))
        await db.commit()

        if cur.rowcount == 0:
            return {"ok": False, "error": f"No contact found with id={contact_id}"}

    return {"ok": True}


@mcp.tool()
async def clear_contact_fields(
    contact_id: int,
    email: bool = False,
    phone: bool = False,
    birthday: bool = False,
    age: bool = False,
    address: bool = False,
    notes: bool = False,
) -> dict:
    """Clear specific fields (set to NULL) for a contact."""
    await init_db()

    updates = []

    if email:
        updates.append("email=NULL")
    if phone:
        updates.append("phone=NULL")
    if birthday:
        updates.append("birthday=NULL")
    if age:
        updates.append("age=NULL")
    if address:
        updates.append("address=NULL")
    if notes:
        updates.append("notes=NULL")

    if not updates:
        return {"ok": False, "error": "Nothing to clear."}

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            f"UPDATE contacts SET {', '.join(updates)} WHERE id=?",
            (contact_id,),
        )
        await db.commit()

        if cur.rowcount == 0:
            return {"ok": False, "error": f"No contact found with id={contact_id}"}

    return {"ok": True}


@mcp.tool()
async def search_contacts(query: str, limit: int = 20) -> List[dict]:
    """Search contacts across all fields."""
    await init_db()

    q = (query or "").strip()
    if not q:
        return []

    like = f"%{q}%"

    age_value = int(q) if q.isdigit() else None

    async with aiosqlite.connect(DB_PATH) as db:
        if age_value is not None:
            cur = await db.execute(
                """
                SELECT id, name, email, phone, birthday, age, address, notes
                FROM contacts
                WHERE name LIKE ?
                   OR email LIKE ?
                   OR phone LIKE ?
                   OR birthday LIKE ?
                   OR address LIKE ?
                   OR notes LIKE ?
                   OR age = ?
                ORDER BY name ASC
                LIMIT ?
                """,
                (like, like, like, like, like, like, age_value, limit),
            )
        else:
            cur = await db.execute(
                """
                SELECT id, name, email, phone, birthday, age, address, notes
                FROM contacts
                WHERE name LIKE ?
                   OR email LIKE ?
                   OR phone LIKE ?
                   OR birthday LIKE ?
                   OR address LIKE ?
                   OR notes LIKE ?
                ORDER BY name ASC
                LIMIT ?
                """,
                (like, like, like, like, like, like, limit),
            )

        rows = await cur.fetchall()

    return [
        {
            "id": r[0],
            "name": r[1],
            "email": r[2],
            "phone": r[3],
            "birthday": r[4],
            "age": r[5],
            "address": r[6],
            "notes": r[7],
        }
        for r in rows
    ]


if __name__ == "__main__":
    mcp.run(transport="stdio")
