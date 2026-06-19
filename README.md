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

## Google Cloud Build

`cloudbuild.yaml` builds and pushes this Docker Hub image:

```bash
ashan97/fast-api-to-do:latest
```

Create the `ashan97/fast-api-to-do` repository in Docker Hub and set its
visibility to Public.

Create a Docker Hub access token, then store it in Google Secret Manager:

```bash
gcloud secrets create dockerhub-token --replication-policy=automatic
echo "YOUR_DOCKER_HUB_ACCESS_TOKEN" | gcloud secrets versions add dockerhub-token --data-file=-
```

Allow the Cloud Build service account to read the secret:

```bash
gcloud secrets add-iam-policy-binding dockerhub-token --member="serviceAccount:PROJECT_NUMBER@cloudbuild.gserviceaccount.com" --role="roles/secretmanager.secretAccessor"
```

Run the build:

```bash
gcloud builds submit --config cloudbuild.yaml .
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
