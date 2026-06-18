from __future__ import annotations

import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from pydantic import BaseModel, Field


DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "todos.db"
DB_PATH = os.getenv("TODO_DB_PATH", str(DEFAULT_DB_PATH))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_connection() -> Generator[sqlite3.Connection, None, None]:
    if DB_PATH != ":memory:":
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


def init_db() -> None:
    if DB_PATH != ":memory:":
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH, check_same_thread=False) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                completed INTEGER NOT NULL DEFAULT 0,
                priority INTEGER NOT NULL DEFAULT 3,
                due_date TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def row_to_todo(row: sqlite3.Row) -> "Todo":
    return Todo(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        completed=bool(row["completed"]),
        priority=row["priority"],
        due_date=row["due_date"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def dump_model(model: BaseModel, **kwargs) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump(**kwargs)
    return model.dict(**kwargs)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Todo API",
    description="A small FastAPI Todo application backed by local SQLite.",
    version="1.0.0",
    lifespan=lifespan,
)


class TodoBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)
    priority: int = Field(default=3, ge=1, le=5)
    due_date: Optional[str] = Field(
        default=None,
        description="Optional due date as a string, for example 2026-06-30.",
    )


class TodoCreate(TodoBase):
    completed: bool = False


class TodoUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=1000)
    completed: Optional[bool] = None
    priority: Optional[int] = Field(default=None, ge=1, le=5)
    due_date: Optional[str] = None


class Todo(TodoBase):
    id: int
    completed: bool
    created_at: str
    updated_at: str


class TodoStats(BaseModel):
    total: int
    completed: int
    active: int


class Message(BaseModel):
    message: str


def fetch_todo_or_404(todo_id: int, connection: sqlite3.Connection) -> Todo:
    row = connection.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Todo {todo_id} was not found.",
        )
    return row_to_todo(row)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/todos",
    response_model=Todo,
    status_code=status.HTTP_201_CREATED,
    tags=["todos"],
)
def create_todo(
    payload: TodoCreate,
    connection: sqlite3.Connection = Depends(get_connection),
) -> Todo:
    now = utc_now()
    cursor = connection.execute(
        """
        INSERT INTO todos (
            title, description, completed, priority, due_date, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload.title,
            payload.description,
            int(payload.completed),
            payload.priority,
            payload.due_date,
            now,
            now,
        ),
    )
    connection.commit()
    return fetch_todo_or_404(cursor.lastrowid, connection)


@app.get("/todos", response_model=list[Todo], tags=["todos"])
def list_todos(
    completed: Optional[bool] = Query(default=None),
    search: Optional[str] = Query(default=None, min_length=1),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    connection: sqlite3.Connection = Depends(get_connection),
) -> list[Todo]:
    clauses: list[str] = []
    values: list[object] = []

    if completed is not None:
        clauses.append("completed = ?")
        values.append(int(completed))

    if search:
        clauses.append("(LOWER(title) LIKE ? OR LOWER(description) LIKE ?)")
        search_value = f"%{search.lower()}%"
        values.extend([search_value, search_value])

    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = connection.execute(
        f"""
        SELECT * FROM todos
        {where_clause}
        ORDER BY completed ASC, priority ASC, id DESC
        LIMIT ? OFFSET ?
        """,
        (*values, limit, offset),
    ).fetchall()
    return [row_to_todo(row) for row in rows]


@app.get("/todos/stats", response_model=TodoStats, tags=["todos"])
def get_todo_stats(
    connection: sqlite3.Connection = Depends(get_connection),
) -> TodoStats:
    row = connection.execute(
        """
        SELECT
            COUNT(*) AS total,
            COALESCE(SUM(completed), 0) AS completed
        FROM todos
        """
    ).fetchone()
    completed = int(row["completed"])
    total = int(row["total"])
    return TodoStats(total=total, completed=completed, active=total - completed)


@app.get("/todos/{todo_id}", response_model=Todo, tags=["todos"])
def get_todo(
    todo_id: int,
    connection: sqlite3.Connection = Depends(get_connection),
) -> Todo:
    return fetch_todo_or_404(todo_id, connection)


@app.patch("/todos/{todo_id}", response_model=Todo, tags=["todos"])
def update_todo(
    todo_id: int,
    payload: TodoUpdate,
    connection: sqlite3.Connection = Depends(get_connection),
) -> Todo:
    fetch_todo_or_404(todo_id, connection)
    updates = dump_model(payload, exclude_unset=True)
    if not updates:
        return fetch_todo_or_404(todo_id, connection)

    updates["updated_at"] = utc_now()
    if "completed" in updates:
        updates["completed"] = int(updates["completed"])

    assignments = ", ".join(f"{field} = ?" for field in updates)
    values = list(updates.values())
    values.append(todo_id)

    connection.execute(
        f"UPDATE todos SET {assignments} WHERE id = ?",
        values,
    )
    connection.commit()
    return fetch_todo_or_404(todo_id, connection)


@app.post("/todos/{todo_id}/complete", response_model=Todo, tags=["todos"])
def complete_todo(
    todo_id: int,
    connection: sqlite3.Connection = Depends(get_connection),
) -> Todo:
    fetch_todo_or_404(todo_id, connection)
    connection.execute(
        "UPDATE todos SET completed = 1, updated_at = ? WHERE id = ?",
        (utc_now(), todo_id),
    )
    connection.commit()
    return fetch_todo_or_404(todo_id, connection)


@app.post("/todos/{todo_id}/reopen", response_model=Todo, tags=["todos"])
def reopen_todo(
    todo_id: int,
    connection: sqlite3.Connection = Depends(get_connection),
) -> Todo:
    fetch_todo_or_404(todo_id, connection)
    connection.execute(
        "UPDATE todos SET completed = 0, updated_at = ? WHERE id = ?",
        (utc_now(), todo_id),
    )
    connection.commit()
    return fetch_todo_or_404(todo_id, connection)


@app.delete(
    "/todos/{todo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["todos"],
)
def delete_todo(
    todo_id: int,
    connection: sqlite3.Connection = Depends(get_connection),
) -> Response:
    fetch_todo_or_404(todo_id, connection)
    connection.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
    connection.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.delete("/todos", response_model=Message, tags=["todos"])
def clear_completed_todos(
    completed_only: bool = Query(default=True),
    connection: sqlite3.Connection = Depends(get_connection),
) -> Message:
    if completed_only:
        cursor = connection.execute("DELETE FROM todos WHERE completed = 1")
        target = "completed todos"
    else:
        cursor = connection.execute("DELETE FROM todos")
        target = "todos"

    connection.commit()
    return Message(message=f"Deleted {cursor.rowcount} {target}.")
