# Task API

A small CRUD API for managing a to-do list, built with FastAPI and backed by a
PostgreSQL database running in Docker. It supports creating, reading, updating,
and deleting tasks. The entire stack — the API and its database — starts with a
single command.

## Requirements

Docker Desktop (or any Docker Engine with Compose). Nothing else — no local
Python, database, or dependencies to install; everything runs in containers.

## Running it

```bash
# 1. copy the example environment file
cp .env.example .env

# 2. start the whole stack (API + database)
docker compose up
```

The API runs at http://localhost:8000. Interactive API docs (Swagger UI) are at
http://localhost:8000/docs.

On first start the database initializes, the `tasks` table is created
automatically, and three example tasks are seeded. The API waits for the
database to be ready before starting, so `docker compose up` works on a clean
clone with no manual setup.

## Configuration

Configuration lives in a `.env` file, which is git-ignored and never committed.
A template with placeholder values is provided as `.env.example` — copy it to
`.env` before running.

| Variable       | Description                  |
|----------------|------------------------------|
| `DATABASE_URL` | PostgreSQL connection string |

The database password is kept out of the code and out of version control.

## Endpoints

| Method | Path         | Description    | Status codes  |
|--------|--------------|----------------|---------------|
| GET    | /            | API info       | 200           |
| GET    | /health      | Health check   | 200           |
| GET    | /tasks       | List all tasks | 200           |
| GET    | /tasks/{id}  | Get one task   | 200, 404      |
| POST   | /tasks       | Create a task  | 201, 400      |
| PUT    | /tasks/{id}  | Update a task  | 200, 400, 404 |
| DELETE | /tasks/{id}  | Delete a task  | 204, 404      |
| GET    | /stats       | Task counts    | 200           |

A task looks like this:

```json
{ "id": 1, "title": "Learn HTTP", "done": true }
```

Errors return a JSON body of the form `{ "error": "..." }`.

## Example request

Deleting a task that doesn't exist returns a 404 with a JSON error body:

```
$ curl -i -X DELETE http://localhost:8000/tasks/99
HTTP/1.1 404 Not Found
date: Sun, 27 Jul 2026 05:31:23 GMT
server: uvicorn
content-length: 30
content-type: application/json
{"error":"Task 99 not found"}
```

## Swagger UI

![Swagger UI showing the Task API endpoints](swagger.png)

## Design notes

Errors use `{ "error": ... }`. I used `JSONResponse` to build error responses by
hand rather than FastAPI's `HTTPException`, because `HTTPException` always wraps
messages in `{ "detail": ... }` and the API contract requires the `error` key.

POST and PUT read the raw request body (via `Request`) instead of a Pydantic
model. This was a deliberate trade: a Pydantic model rejects a malformed body
with 422, but the API requires 400, so I parse and validate the body myself to
control the status code. One side effect is that Swagger's "Try it out" shows
input boxes for the GET endpoints but not for POST/PUT. Those two endpoints are
fully tested with curl — see the example above — and work correctly for the
whole create/update cycle.

Storage has moved through three backends behind an unchanging API. It began as
an in-memory Python list, where tasks vanished on restart. It then moved to a
single-file SQLite database, so data survived restarts. It now runs against
PostgreSQL in a Docker container: a real database server, with data on a
persistent volume that outlives the container itself. Across all three, the
endpoints, status codes, and request/response shapes never changed — only the
storage code behind them. The endpoint table above needed no edits through any
of these migrations, which is the clearest evidence that storage is an
implementation detail the client never sees.

## Database

Tasks are stored in PostgreSQL, running as a container defined in
`compose.yaml`. The app connects using the `DATABASE_URL` from the environment.

**Why PostgreSQL:** it's a real database server — the same engine behind a large
share of production backends. Running it in Docker means no local install and
identical behaviour on any machine. Data lives on a named Docker volume
(`taskdata`), so it survives not just a server restart but the container being
destroyed and recreated (`docker compose down` then `up`).

**Setup is automatic.** On first run the app creates the `tasks` table if
missing and seeds three example tasks only when the table is empty, so restarts
never duplicate them. A fresh clone that runs `docker compose up` gets a
working, seeded database with no manual steps.

All queries use parameterized placeholders (`%s`), so user input is never
interpreted as SQL.

### Example query

```sql
SELECT COUNT(*) FROM tasks;
```

Returned 3 — the number of rows in the table after a fresh start.

![The tasks table in PostgreSQL, viewed in DBeaver](database.png)
