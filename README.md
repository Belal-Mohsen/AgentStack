# AgentStack

A production-ready SaaS AI agent platform powered by **LangGraph**, **FastAPI**, and **PostgreSQL**. Features conversational AI with tool use (web search), long-term memory via pgvector, JWT authentication, and full observability (Prometheus, Grafana, Langfuse).

---

## Features

- **Conversational AI Agent** — LangGraph-based agent with configurable LLM, tool calling, and stateful conversations
- **Long-Term Memory** — pgvector-backed memory (mem0ai) for persistent user context across sessions
- **Streaming Responses** — Server-Sent Events (SSE) for real-time token streaming
- **Authentication** — JWT-based auth with user registration, login, and session management
- **Rate Limiting** — Per-endpoint rate limits via SlowAPI
- **Observability** — Prometheus metrics, Grafana dashboards, Langfuse tracing
- **Evaluation Framework** — LLM-as-a-judge evals for quality metrics (helpfulness, relevancy, toxicity, etc.)
- **Docker Support** — Full stack with PostgreSQL, app, Prometheus, Grafana, cAdvisor

---

## Tech Stack

| Layer          | Technology                          |
| -------------- | ----------------------------------- |
| API            | FastAPI, Uvicorn, uvloop             |
| Agent          | LangGraph, LangChain, OpenAI         |
| Memory         | mem0ai + pgvector                   |
| Database       | PostgreSQL 16 + pgvector            |
| Auth           | JWT (python-jose), bcrypt            |
| Observability  | Prometheus, Grafana, Langfuse       |
| Package Mgmt   | uv                                  |

---

## Project Structure

```
├── app/                         # Main application
│   ├── api/v1/                  # Versioned API routes
│   │   ├── auth.py              # Registration, login, sessions
│   │   ├── chatbot.py           # Chat (sync/stream), message history
│   │   └── api.py               # Router aggregation
│   ├── core/
│   │   ├── config/              # Settings, logging
│   │   ├── langgraph/           # Agent graph, tools
│   │   │   ├── graph.py         # LangGraph workflow
│   │   │   └── tools/           # Agent tools (e.g. DuckDuckGo search)
│   │   ├── prompts/             # System prompts
│   │   ├── limiter.py           # Rate limiting
│   │   ├── metrics.py           # Prometheus metrics
│   │   └── middleware.py        # Logging, metrics middleware
│   ├── models/                  # SQLModel database models
│   ├── schemas/                 # Pydantic request/response schemas
│   ├── services/                # Database, LLM services
│   └── utils/                   # Auth, sanitization, graph helpers
├── evals/                       # Evaluation framework
│   ├── main.py                  # CLI for running evals
│   ├── evaluator.py             # Evaluation orchestration
│   ├── helpers.py               # Trace fetching, formatting
│   ├── schemas.py               # Eval data models
│   └── metrics/
│       └── prompts/             # LLM-as-judge prompts (toxicity, relevancy, etc.)
├── docker/
│   ├── app/                     # Dockerfile, entrypoint
│   ├── docker-compose.yml       # Full stack (DB, app, Prometheus, Grafana, cAdvisor)
│   ├── grafana/                 # Dashboards
│   └── prometheus/              # Prometheus config
├── scripts/
│   ├── set_env.sh               # Environment setup
│   └── build-docker.sh          # Env-specific Docker builds
├── .github/workflows/           # CI/CD (build, scan, push)
├── .env.example                 # Environment template
├── Makefile                     # Common commands
├── pyproject.toml               # Dependencies
└── uv.lock                      # Locked dependencies
```

---

## Prerequisites

- **Python 3.13+**
- **uv** (install via `pip install uv` or [uv docs](https://docs.astral.sh/uv/))
- **Docker** and **Docker Compose** (optional, for containerized runs)
- **PostgreSQL 16** with pgvector (or use Docker)

---

## Quick Start

### 1. Clone & Install

```bash
git clone <repository-url>
cd AgentStack
make install
```

### 2. Configure Environment

```bash
cp .env.example .env.development
# Edit .env.development and set required variables (see Configuration)
```

### 3. Run Locally

**Without Docker** (requires PostgreSQL with pgvector):

```bash
make dev
```

**With Docker** (starts PostgreSQL + app):

```bash
make docker-run-env ENV=development
```

API: **http://localhost:8000**  
Docs: **http://localhost:8000/docs**

---

## Configuration

Copy `.env.example` to `.env.development` (or `.env.staging` / `.env.production`) and set:

| Variable            | Description                          | Example (placeholder)     |
| ------------------- | ------------------------------------ | ------------------------- |
| `APP_ENV`           | Environment (development/staging/production) | `development`      |
| `OPENAI_API_KEY`    | LLM provider API key                 | `sk-...`                  |
| `JWT_SECRET_KEY`    | Secret for signing JWT tokens         | Long random string        |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key (optional)    | —                         |
| `LANGFUSE_SECRET_KEY` | Langfuse secret (optional)         | —                         |
| `POSTGRES_HOST`     | Database host                        | `localhost` or `db`       |
| `POSTGRES_PORT`     | Database port                        | `5432`                    |
| `POSTGRES_DB`       | Database name                        | `mydb`                    |
| `POSTGRES_USER`     | Database user                        | —                         |
| `POSTGRES_PASSWORD` | Database password                    | —                         |

See `.env.example` for all options (CORS, rate limits, logging, etc.).

---

## Running the Application

| Command                                  | Description                          |
| ---------------------------------------- | ------------------------------------ |
| `make dev`                               | Development server (reload)           |
| `make prod`                              | Production server                    |
| `make staging`                           | Staging server                       |
| `make docker-run`                        | Run app + DB (development)           |
| `make docker-run-env ENV=production`     | Run app + DB for given env           |
| `make docker-compose-up ENV=development` | Full stack (Prometheus, Grafana, …)  |
| `make docker-logs ENV=development`       | View container logs                  |
| `make docker-stop ENV=development`       | Stop containers                      |

---

## API Overview

| Endpoint                  | Method | Description                    |
| ------------------------- | ------ | ------------------------------ |
| `/`                       | GET    | Service info                   |
| `/health`                 | GET    | Health check (API + DB)         |
| `/api/v1/auth/register`   | POST   | User registration              |
| `/api/v1/auth/login`      | POST   | Login (Form: username, password) |
| `/api/v1/auth/session`    | POST   | Create chat session (Bearer)   |
| `/api/v1/auth/sessions`    | GET    | List user sessions (Bearer)    |
| `/api/v1/chatbot/chat`    | POST   | Sync chat (Bearer)             |
| `/api/v1/chatbot/chat/stream` | POST | Streaming chat (Bearer)       |
| `/api/v1/chatbot/messages` | GET    | Get session history (Bearer)   |
| `/api/v1/chatbot/messages` | DELETE | Clear history (Bearer)        |

Chat endpoints expect `ChatRequest` with `messages` array. Session-scoped JWT is used to identify the conversation thread.

---

## Evaluation Framework

Run LLM-as-judge evaluations on traces (e.g. from Langfuse):

```bash
make eval              # Interactive mode
make eval-quick        # Default settings
make eval-no-report    # No JSON report
```

Metrics (defined in `evals/metrics/prompts/`): conciseness, hallucination, helpfulness, relevancy, toxicity.

---

## Observability

### Prometheus

- **Metrics**: `http_request_duration_seconds`, `llm_stream_duration_seconds`, etc.
- **UI**: http://localhost:9090 (when stack is running)

### Grafana

- **UI**: http://localhost:3000 (default credentials: admin/admin)
- Pre-provisioned dashboards for LLM latency and related metrics

### Langfuse

- Traces LLM calls when `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set.
- Configure host via `LANGFUSE_HOST` (default: https://cloud.langfuse.com)

---

## CI/CD

GitHub Actions workflow (`.github/workflows/deploy.yml`):

- **Triggers**: Push to `main` or tags `v*.*.*`, pull requests
- **Steps**:
  1. Build Docker image
  2. Run Trivy security scan (fails on CRITICAL/HIGH)
  3. Push to Docker Hub on success (non-PR)

**Required secrets**: `DOCKER_USERNAME`, `DOCKER_PASSWORD`

---

## Development

| Command              | Description           |
| -------------------- | --------------------- |
| `make install`       | Install dependencies  |
| `make lint`          | Run ruff check        |
| `make format`        | Run ruff format       |
| `make clean`         | Remove `.venv`, caches |
| `make help`          | List all targets      |

### Docker Builds

```bash
make docker-build                    # Default image
make docker-build-env ENV=production # Environment-specific build
```

---
