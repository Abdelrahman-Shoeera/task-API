# Task API

A small CRUD API for managing a to-do list, built with FastAPI as part of the FlyRank Backend Track (Weeks 2–3). It supports creating, reading, updating, and deleting tasks. Data is stored in a SQLite database (tasks.db), so tasks survive a server restart.
## Requirements

- Python 3.10 or newer

## Install & run

```bash
# 1. create and activate a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows (PowerShell)
# source .venv/bin/activate       # Mac / Linux

# 2. install dependencies
pip install "fastapi[standard]"

# 3. start the server
fastapi dev main.py
```

The server runs at **http://localhost:8000**.
Interactive API docs (Swagger UI) are at **http://localhost:8000/docs**.

## Endpoints

| Method | Path          | Description     | Status codes        |
|--------|---------------|-----------------|---------------------|
| GET    | `/`           | API info        | 200                 |
| GET    | `/health`     | Health check    | 200                 |
| GET    | `/tasks`      | List all tasks  | 200                 |
| GET    | `/tasks/{id}` | Get one task    | 200, 404            |
| POST   | `/tasks`      | Create a task   | 201, 400            |
| PUT    | `/tasks/{id}` | Update a task   | 200, 400, 404       |
| DELETE | `/tasks/{id}` | Delete a task   | 204, 404            |

A task looks like this:

```json
{ "id": 1, "title": "Learn HTTP", "done": true }
```

Errors return a JSON body of the form `{ "error": "..." }`.

## Example request

Deleting a task that doesn't exist returns a `404` with a JSON error body:

```
$ curl -i -X DELETE http://localhost:8000/tasks/99
HTTP/1.1 404 Not Found
date: Sun, 19 Jul 2026 16:22:40 GMT
server: uvicorn
content-length: 29
content-type: application/json

{"error":"Task 99 not found"}
```

## Swagger UI

![Swagger UI showing the Task API endpoints](swagger.png)

## Design notes

- **Errors use `{ "error": ... }`.** I used `JSONResponse` to build error
  responses by hand rather than FastAPI's `HTTPException`, because
  `HTTPException` always wraps messages in `{ "detail": ... }` and the
  assignment requires the `error` key.

- **POST and PUT read the raw request body** (via `Request`) instead of a
  Pydantic model. This was a deliberate trade: a Pydantic model rejects a
  malformed body with `422`, but the assignment requires `400`, so I parse
  and validate the body myself to control the status code. One side effect
  is that Swagger's "Try it out" shows input boxes for the GET endpoints but
  not for POST/PUT. Those two endpoints are fully tested with `curl` — see
  the example above — and work correctly for the whole create/update cycle.

- **Storage is in-memory.** Created tasks live in a Python list and disappear
  when the server stops. Restarting the server brings back only the three
  seed tasks. This is exactly why a database is needed.
