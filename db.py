import os
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

def get_connection():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)

def init_db():
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id    SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                done  BOOLEAN NOT NULL DEFAULT FALSE
            )
        """)
        cur.execute("SELECT COUNT(*) FROM tasks")
        count = cur.fetchone()["count"]
        if count == 0:
            cur.executemany(
                "INSERT INTO tasks (title, done) VALUES (%s, %s)",
                [("Buy milk", False), ("Walk the dog", True), ("Read a book", False)],
            )
    conn.commit()
    conn.close()

def row_to_task(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "done": row["done"],
    }