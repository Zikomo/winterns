# Wintern API

FastAPI backend for Wintern - AI-powered web research agents.

## Development

```bash
# Install dependencies
uv sync

# Run development server
uv run uvicorn wintern.main:app --reload

# Run tests
uv run pytest

# Run linter
uv run ruff check .
```

## Project Structure

```
src/wintern/
├── main.py           # FastAPI application entry point
├── core/             # Configuration, database, shared utilities
├── auth/             # Authentication (fastapi-users)
├── winterns/         # Wintern CRUD operations
├── execution/        # Job executor and scheduler
├── agents/           # Pydantic AI agents
├── sources/          # Data source integrations
└── delivery/         # Output channel integrations
```
