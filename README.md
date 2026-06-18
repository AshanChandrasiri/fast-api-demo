# Todo FastAPI App

A small Todo API built with FastAPI and local SQLite. It does not require an
external database; by default it writes to `todos.db` in the project root.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

Open the interactive API docs at:

- http://127.0.0.1:8000/docs
- http://127.0.0.1:8000/redoc

## Docker

Build the image:

```bash
docker build -t todo-fastapi .
```

Run the container:

```bash
docker run --rm -p 8000:8000 todo-fastapi
```

Run with a persisted SQLite file:

```bash
docker run --rm -p 8000:8000 -v "${PWD}\data:/app/data" -e TODO_DB_PATH=/app/data/todos.db todo-fastapi
```

## APIs

- `GET /health`
- `POST /todos`
- `GET /todos`
- `GET /todos/stats`
- `GET /todos/{todo_id}`
- `PATCH /todos/{todo_id}`
- `POST /todos/{todo_id}/complete`
- `POST /todos/{todo_id}/reopen`
- `DELETE /todos/{todo_id}`
- `DELETE /todos`

## Example

```bash
curl -X POST http://127.0.0.1:8000/todos ^
  -H "Content-Type: application/json" ^
  -d "{\"title\":\"Buy milk\",\"priority\":2}"
```

## Test

```bash
pytest
```
