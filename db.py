import sqlite3

DB_FILE = "tasks.db"

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row   # rows come back like dicts
    return conn

def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id    INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            done  INTEGER NOT NULL DEFAULT 0
        )
    """)
    # seed only if the table is empty
    count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    if count == 0:
        conn.executemany(
            "INSERT INTO tasks (title, done) VALUES (?, ?)",
            [("Buy milk", 0), ("Walk the dog", 1), ("Read a book", 0)],
        )
    conn.commit()
    conn.close()

def row_to_task(row):
     return {
        "id": row["id"],
        "title": row["title"],
        "done": bool(row["done"]),
     }