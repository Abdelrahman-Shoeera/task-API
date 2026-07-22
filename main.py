from fastapi import FastAPI,Request,Response
from fastapi.responses import JSONResponse
from db import init_db, get_connection, row_to_task


init_db()

app = FastAPI(
    title="Task API",
    description="A simple CRUD API for managing a to-do list.",
    version="1.0",
)

tasks = [
    {"id": 1, "title": "Learn HTTP", "done": True},
    {"id": 2, "title": "Build a CRUD API", "done": False},
    {"id": 3, "title": "Publish to GitHub", "done": False},
]

@app.get("/")
def read_root():
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks"]}


@app.get("/health")
def health_check():
    "gets status"
    return {"status": "ok"}

@app.get("/tasks", summary="List all tasks")
def get_tasks(done: bool | None = None, search: str | None = None):
    """Return all tasks, optionally filtered by done status and/or title search."""
    sql = "SELECT * FROM tasks"
    conditions = []
    params = []

    if done is not None:
        conditions.append("done = ?")
        params.append(1 if done else 0)

    if search is not None:
        conditions.append("title LIKE ?")
        params.append(f"%{search}%")

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    conn = get_connection()
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    return [row_to_task(r) for r in rows]


@app.get("/tasks/{id}")
def get_task(id: int):
    "returns a single task by id"
    conn = get_connection()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (id,)).fetchone()
    conn.close()

    if row is None:
        return JSONResponse(status_code=404, content={"error": f"Task {id} not found"})

    return row_to_task(row)


@app.post("/tasks")
async def create_task(request: Request):
    "creates a task"
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid JSON body"})
  
    title = body.get("title")
    if not isinstance(title, str) or not title.strip():
        return JSONResponse(
            status_code=400,
            content={"error": "title is required and must be a non-empty string"},
        )

    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO tasks (title, done) VALUES (?, ?)",
        (title, 0)
    )
    conn.commit()
    task = {"id": cur.lastrowid, "title": title, "done": False}
    conn.close()
    return JSONResponse(status_code=201, content=task)

@app.put("/tasks/{id}")
async def update_task(id: int, request: Request):
    "updates a task"
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid JSON body"})

    conn = get_connection()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (id,)).fetchone()
    if row is None:
        conn.close()
        return JSONResponse(status_code=404, content={"error": f"Task {id} not found"})

    updates = []
    params = []

    if "title" in body:
        title = body["title"]
        if not isinstance(title, str) or not title.strip():
            conn.close()
            return JSONResponse(status_code=400, content={"error": "title must be a non-empty string"})
        updates.append("title = ?")
        params.append(title)

    if "done" in body:
        if not isinstance(body["done"], bool):
            conn.close()
            return JSONResponse(status_code=400, content={"error": "done must be true or false"})
        updates.append("done = ?")
        params.append(1 if body["done"] else 0)

    if updates:
        params.append(id)
        conn.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()

    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (id,)).fetchone()
    conn.close()
    return row_to_task(row) 

@app.delete("/tasks/{id}")
def delete_task(id: int):
    "deletes a task by id"
    conn = get_connection()
    cur = conn.execute("DELETE FROM tasks WHERE id = ?", (id,))
    conn.commit()
    conn.close()

    if cur.rowcount == 0:
        return JSONResponse(status_code=404, content={"error": f"Task {id} not found"})

    return Response(status_code=204)

@app.get("/stats", summary="Task statistics")
def get_stats():
    """Return counts of total, done, and open tasks."""
    total = len(tasks)
    done = len([t for t in tasks if t["done"]])
    return {"total": total, "done": done, "open": total - done}
