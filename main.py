from fastapi import FastAPI,Request,Response
from fastapi.responses import JSONResponse
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

@app.get("/tasks",summary="List all tasks")
def get_tasks(done: bool | None = None, search: str | None = None):
    """Return all tasks, optionally filtered by done status and/or title search."""
    result = tasks

    if done is not None:
        result = [t for t in result if t["done"] == done]

    if search is not None:
        result = [t for t in result if search.lower() in t["title"].lower()]

    return result

@app.get("/tasks/{id}")
def get_task(id: int):
    "returns a single task by id"
    for task in tasks:
        if task["id"] == id:
            return task
    return JSONResponse(status_code=404, content={"error": f"Task {id} not found"})

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

    new_id = max([t["id"] for t in tasks], default=0) + 1
    task = {"id": new_id, "title": title, "done": False}
    tasks.append(task)
    return JSONResponse(status_code=201, content=task)

@app.put("/tasks/{id}")
async def update_task(id: int, request: Request):
    "updates a task"
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid JSON body"})

    for task in tasks:
        if task["id"] == id:
            if "title" in body:
                title = body["title"]
                if not isinstance(title, str) or not title.strip():
                    return JSONResponse(status_code=400, content={"error": "title must be a non-empty string"})
                task["title"] = title
            if "done" in body:
                if not isinstance(body["done"], bool):
                    return JSONResponse(status_code=400, content={"error": "done must be true or false"})
                task["done"] = body["done"]
            return task

    return JSONResponse(status_code=404, content={"error": f"Task {id} not found"})

@app.delete("/tasks/{id}")
def delete_task(id: int):
    "deletes a task by id"
    for i, task in enumerate(tasks):
        if task["id"] == id:
            tasks.pop(i)
            return Response(status_code=204)

    return JSONResponse(status_code=404, content={"error": f"Task {id} not found"})

@app.get("/stats", summary="Task statistics")
def get_stats():
    """Return counts of total, done, and open tasks."""
    total = len(tasks)
    done = len([t for t in tasks if t["done"]])
    return {"total": total, "done": done, "open": total - done}
