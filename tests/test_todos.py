import os

os.environ["TODO_DB_PATH"] = ":memory:"

import app.main as main
from fastapi.testclient import TestClient


def build_client():
    connection = main.sqlite3.connect(":memory:", check_same_thread=False)
    connection.row_factory = main.sqlite3.Row
    connection.execute(
        """
        CREATE TABLE todos (
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

    def get_test_connection():
        try:
            yield connection
        finally:
            pass

    main.app.dependency_overrides[main.get_connection] = get_test_connection
    client = TestClient(main.app)
    return client, connection


def test_todo_crud_flow():
    client, connection = build_client()
    try:
        response = client.post(
            "/todos",
            json={
                "title": "Write tests",
                "description": "Cover the basic todo flow",
                "priority": 2,
            },
        )
        assert response.status_code == 201
        todo = response.json()
        assert todo["title"] == "Write tests"
        assert todo["completed"] is False

        todo_id = todo["id"]

        response = client.get(f"/todos/{todo_id}")
        assert response.status_code == 200
        assert response.json()["id"] == todo_id

        response = client.patch(f"/todos/{todo_id}", json={"priority": 1})
        assert response.status_code == 200
        assert response.json()["priority"] == 1

        response = client.post(f"/todos/{todo_id}/complete")
        assert response.status_code == 200
        assert response.json()["completed"] is True

        response = client.get("/todos/stats")
        assert response.status_code == 200
        assert response.json() == {"total": 1, "completed": 1, "active": 0}

        response = client.post(f"/todos/{todo_id}/reopen")
        assert response.status_code == 200
        assert response.json()["completed"] is False

        response = client.delete(f"/todos/{todo_id}")
        assert response.status_code == 204

        response = client.get(f"/todos/{todo_id}")
        assert response.status_code == 404
    finally:
        connection.close()
        main.app.dependency_overrides.clear()


def test_list_search_and_clear_completed():
    client, connection = build_client()
    try:
        client.post("/todos", json={"title": "Buy milk", "priority": 4})
        done = client.post("/todos", json={"title": "File taxes", "priority": 1}).json()
        client.post(f"/todos/{done['id']}/complete")

        response = client.get("/todos", params={"search": "milk"})
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["title"] == "Buy milk"

        response = client.delete("/todos", params={"completed_only": True})
        assert response.status_code == 200
        assert response.json()["message"] == "Deleted 1 completed todos."

        response = client.get("/todos/stats")
        assert response.json() == {"total": 1, "completed": 0, "active": 1}
    finally:
        connection.close()
        main.app.dependency_overrides.clear()
