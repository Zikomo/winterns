# Wintern

AI-powered web research agents that periodically search the web for content matching your interests and deliver curated digests.

## What is Wintern?

Wintern lets you create autonomous research agents ("Winterns") that:

1. **Interpret** your research context and objectives
2. **Search** multiple sources (web, Reddit, etc.)
3. **Curate** relevant content using AI
4. **Deliver** personalized digests via Slack or email

Perfect for staying on top of industry news, tracking competitors, monitoring topics, or research aggregation.

## Tech Stack

- **Backend:** FastAPI, Python 3.12+, Pydantic AI
- **Frontend:** React, TypeScript, Vite, TailwindCSS
- **Database:** PostgreSQL
- **LLM:** OpenRouter (supports Claude, GPT-4, Llama, etc.)
- **Infrastructure:** Docker, AWS (ECS Fargate, RDS)

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 20+
- pnpm
- Docker

### Local Development

```bash
# Clone the repo
git clone https://github.com/Zikomo/winterns.git
cd winterns

# Copy environment variables
cp .env.example .env
# Edit .env with your API keys

# Start services
docker compose up -d

# Install dependencies
pnpm install

# Run the API
cd apps/api
pip install -e ".[dev]"
uvicorn wintern.main:app --reload

# Run the frontend (separate terminal)
cd apps/web
pnpm dev
```

### Required API Keys

| Service | Purpose | Get it at |
|---------|---------|-----------|
| OpenRouter | LLM provider | [openrouter.ai/keys](https://openrouter.ai/keys) |
| Brave Search | Web search | [brave.com/search/api](https://brave.com/search/api/) |
| Reddit | Reddit search | [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) |
| Google OAuth | Authentication | [console.cloud.google.com](https://console.cloud.google.com/apis/credentials) |

## Project Status

🚧 **Under active development** - See [Issues](https://github.com/Zikomo/winterns/issues) for the roadmap.

## License

MIT
