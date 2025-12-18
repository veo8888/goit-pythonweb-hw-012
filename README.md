# goit-pythonweb-hw-12

## 📌 Project Overview

REST API for contact management built with FastAPI.

Implemented features:

- REST API using FastAPI, SQLAlchemy, Alembic, and PostgreSQL

- Fully Dockerized application with hot reload and migration support

- JWT authentication with:

- email verification

- refresh tokens

- role-based access control

- Redis integration for:

- rate limiting

- user caching

- Password reset mechanism via email

- CORS configuration

- Automated testing with pytest

- Project documentation generated using Sphinx

## 🚀 Running the Project in VS Code (Windows)

1. Open the project in **VS Code**.

2. Create `.env` in the project root.

## 🐳 Run with Docker

```bash
docker compose up --build
```

- Note: All subsequent Docker commands should be executed in a separate terminal window.

## 📘 Swagger UI

Interactive API documentation:

- http://localhost:8000/docs

- http://127.0.0.1:8000/docs

## 🛠 Alembic Migrations (Docker)

1️⃣ Create migration:

```bash
docker exec hw12-web-authentication alembic revision --autogenerate -m "init"
```

2️⃣ Apply migration:

```bash
docker exec hw12-web-authentication alembic upgrade head
```

3️⃣ Roll back migration:

```bash
docker exec hw12-web-authentication alembic downgrade -1
```

## 🧪 Running Tests (Docker)

```bash
docker exec hw12-web-authentication pytest
```

## 📚 Generate Documentation with Sphinx (Docker)

```bash
docker exec hw12-web-authentication sphinx-build -b html docs build/html
```

- Note: The generated HTML documentation will be available locally in:

```
docs/build/html
```

## ✔ Notes

- All files created or modified inside the container are persisted locally via Docker volumes.

- No additional setup is required after the containers are started.
