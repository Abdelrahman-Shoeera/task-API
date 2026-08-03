import os
from dotenv import load_dotenv
from fastapi import FastAPI,Request,Response
from supabase import create_client, Client
from fastapi.responses import JSONResponse
from db import init_db, get_connection, row_to_task
from supabase_auth.errors import AuthApiError

load_dotenv()
init_db()



supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(supabase_url, supabase_key)

print("Server running and connected to Supabase")

app = FastAPI(
    title="Task API",
    description="A simple CRUD API for managing a to-do list.",
    version="1.0",
)


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
        conditions.append("done = %s")
        params.append(done)

    if search is not None:
        conditions.append("title LIKE %s")
        params.append(f"%{search}%")

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    conn.close()
    return [row_to_task(r) for r in rows]

@app.get("/tasks/{id}")
def get_task(id: int):
    "returns a single task by id"
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM tasks WHERE id = %s", (id,))
        row = cur.fetchone()
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

    conn =get_connection()
    with conn.cursor() as cur:
       cur.execute(
           "INSERT INTO tasks (title, done) VALUES (%s, %s) RETURNING *",
           (title, False),
       )
       row = cur.fetchone()
    conn.commit()
    conn.close()
    return JSONResponse(status_code=201, content=row_to_task(row))

@app.put("/tasks/{id}")
async def update_task(id: int, request: Request):
    "updates a task"
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid JSON body"})

    conn = get_connection()
    with conn.cursor() as cur:
      cur.execute("SELECT * FROM tasks WHERE id =%s", (id,))
      row=cur.fetchone()
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
        updates.append("title = %s")
        params.append(title)

    if "done" in body:
        if not isinstance(body["done"], bool):
            conn.close()
            return JSONResponse(status_code=400, content={"error": "done must be true or false"})
        updates.append("done = %s")
        params.append(body["done"])

    if updates:
        params.append(id)
        with conn.cursor() as cur:
           cur.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = %s", params)
           conn.commit()
           cur.execute("SELECT * FROM tasks WHERE id = %s", (id,))
           row=cur.fetchone()
    conn.close()
    return row_to_task(row) 

@app.delete("/tasks/{id}")
def delete_task(id: int):
    "deletes a task by id"
    conn = get_connection()
    with conn.cursor() as cur:
       cur.execute("DELETE FROM tasks WHERE id = %s", (id,))
       deleted = cur.rowcount  
    conn.commit()
    conn.close()

    if deleted == 0:
        return JSONResponse(status_code=404, content={"error": f"Task {id} not found"})

    return Response(status_code=204)

@app.get("/stats", summary="Task statistics")
def get_stats():
    """Return counts of total, done, and open tasks."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM tasks")
        total = cur.fetchone()["count"]

        cur.execute("SELECT COUNT(*) FROM tasks WHERE done = TRUE")
        done = cur.fetchone()["count"]
    conn.close()

    open_count = total - done
    return {"total": total, "done": done, "open": open_count}

@app.post("/auth/signup")
async def signup(request: Request):
    
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON body"})

    email = body.get("email")  
    password=body.get("password")  

    if not isinstance(email, str) or not email.strip():
            return JSONResponse(
                status_code=400,
                content={"error": "email is required and must be a non-empty string"},
            )
    if not isinstance(password, str) or not password.strip():
            return JSONResponse(
                status_code=400,
                content={"error": "password is required and must be a non-empty string"},
            )
    try:
        response = supabase.auth.sign_up({"email": email, "password": password})
    except AuthApiError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    user = response.user
    return JSONResponse(
        status_code=201,
        content={
            "id": user.id,
            "email": user.email,
            "created_at": str(user.created_at),
        },
    )

@app.post("/auth/login")
async def login(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON body"})
    
    email = body.get("email")  
    password=body.get("password")  
    
    if not isinstance(email, str) or not email.strip():
        return JSONResponse(
                    status_code=400,
                    content={"error": "email is required and must be a non-empty string"},
                )
    if not isinstance(password, str) or not password.strip():
        return JSONResponse(
                    status_code=400,
                    content={"error": "password is required and must be a non-empty string"},
                )
    try:
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
    except AuthApiError as e:
        return JSONResponse(status_code=401, content={"error":  "Invalid login credentials"})

    return JSONResponse(
        status_code=200,
        content={
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
        },
    )

@app.get("/public/info")
async def public_info():
   return JSONResponse(status_code=200,content={"message": "Welcome stranger! This info is public."}, )

@app.get("/protected/profile")
async def protected_profile(request: Request):
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return JSONResponse(
                            status_code=401,
                            content={"error": "Access token required"}
                        )
    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        return JSONResponse(status_code=401,content={"error": "Access token required"})

    return JSONResponse( status_code=200,content={"message": "Token received", "token": token})

