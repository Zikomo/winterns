# Agent Guidelines

This file provides context for AI coding agents (Claude Code, Cursor, Copilot, etc.) working on this repository.

## Project Overview

**Wintern** is an AI-powered web research agent platform built with:
- **Backend:** FastAPI (Python 3.12+), Pydantic AI, SQLAlchemy 2.0
- **Frontend:** React 18, TypeScript, Vite, TailwindCSS
- **Database:** PostgreSQL 16
- **LLM:** OpenRouter (supports multiple models)

## Branching Strategy

We follow a simplified Git Flow approach:

```
main (protected)
  │
  ├── feature/issue-1-monorepo-setup
  ├── feature/issue-7-auth
  ├── feature/issue-9-context-interpreter
  │
  └── topic/phase-2-backend (optional, for grouping related features)
        ├── feature/issue-9-context-interpreter
        ├── feature/issue-10-content-curator
        └── feature/issue-11-digest-composer
```

### Branch Naming

| Type | Pattern | Example |
|------|---------|---------|
| Feature | `feature/issue-{N}-{short-description}` | `feature/issue-7-auth` |
| Topic | `topic/{phase-or-epic}` | `topic/phase-2-backend` |
| Bugfix | `fix/issue-{N}-{short-description}` | `fix/issue-42-login-redirect` |
| Hotfix | `hotfix/{description}` | `hotfix/security-patch` |

### Workflow

1. **Create branch** from `main` (or from a topic branch if grouping work)
2. **Make commits** with clear messages
3. **Open PR** against `main` (or topic branch)
4. **Squash or rebase merge** to keep history linear
5. **Branch auto-deletes** after merge

### Rules

- **No direct pushes to `main`** - all changes via PR
- **Linear history required** - only squash or rebase merges allowed
- **Keep PRs focused** - one issue per PR when possible

## Project Structure

```
wintern/
├── apps/
│   ├── api/                 # FastAPI backend (domain-based structure)
│   │   └── src/wintern/
│   │       ├── core/        # Config, database, exceptions
│   │       ├── auth/        # Authentication domain
│   │       ├── winterns/    # Wintern CRUD domain
│   │       ├── execution/   # Run execution + scheduler
│   │       ├── agents/      # Pydantic AI agents
│   │       ├── sources/     # Data sources (Brave, Reddit)
│   │       └── delivery/    # Delivery channels (Slack, email)
│   │
│   └── web/                 # React frontend
│       └── src/
│           ├── components/  # UI components
│           ├── pages/       # Route pages
│           ├── hooks/       # Custom hooks
│           ├── lib/         # API client, utils
│           └── types/       # TypeScript types
│
└── infrastructure/
    ├── docker-compose.yml   # Local development
    └── terraform/           # AWS infrastructure (P2)
```

## Development Commands

```bash
# Backend
cd apps/api
pip install -e ".[dev]"
uvicorn wintern.main:app --reload
pytest
ruff check .

# Frontend
cd apps/web
pnpm install
pnpm dev
pnpm test
pnpm lint
pnpm typecheck

# Database
cd infrastructure
docker compose up -d
```

## Code Style

### Python
- Type hints on all functions
- Async/await for all I/O
- Ruff for linting/formatting
- Domain-based organization (not file-type based)

### TypeScript
- Strict mode enabled
- No `any` types
- Functional components only
- React Query for server state

## Working on Issues

Each GitHub issue is self-contained with:
- Acceptance criteria (checkboxes)
- Technical notes / code snippets
- Dependencies listed

When starting work:
1. Check the issue for dependencies
2. Create a feature branch: `git checkout -b feature/issue-{N}-{description}`
3. Implement the acceptance criteria
4. Open a PR referencing the issue: `Closes #N`
