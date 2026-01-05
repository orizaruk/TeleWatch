# Telegram Job Listing Bot - Roadmap

## Overview

Transform the script into a portable, containerized daemon that:
- Runs 24/7 with no terminal window needed
- Works identically on mini-PC, VPS, or cloud
- Retains full interactive mode (`python main.py`) for configuration
- Adds Docker mode for headless background operation

---

## Phase 1: Production-Ready Self-Hosted Daemon

Goal: Add Docker support and improve resilience while keeping existing functionality intact.

### 1.1 Signal-Based Shutdown (replaces stdin 'q')
- **File**: `main.py`
- Replace the `input()` loop in `run_bot()` with proper signal handlers
- Handle SIGTERM and SIGINT for graceful shutdown
- Works correctly in Docker (receives SIGTERM on stop)

### 1.2 Retry Logic for Notifications
- **File**: `notifiers/__init__.py` or individual notifiers
- Add configurable retry (e.g., 3 attempts with exponential backoff)
- Log retries and final failures
- Prevent notification loss from transient failures

### 1.3 Docker Containerization
- **New files**: `Dockerfile`, `docker-compose.yml`, `.dockerignore`
- Lightweight Python image (python:3.11-slim)
- Volume mounts for persistent data: `config.json`, `sesh.session`
- Environment variables for credentials (no .env file needed in container)
- Auto-restart policy

### 1.4 Health Monitoring
- **File**: `main.py` (new function)
- Write timestamp to a health file periodically (e.g., every 60s)
- External monitoring can check file age

### 1.5 Improved Logging for Daemon Mode
- **File**: `main.py`
- Structured logging with timestamps
- Log rotation (prevent bot.log growing forever)
- Summary stats on shutdown (messages processed, matches found, notifications sent)

### 1.6 Configuration via Environment Variables
- **File**: `config.py`
- Allow `CHATS`, `KEYWORDS`, `DESTINATIONS` to be set via env vars
- Useful for Docker deployments and CI/CD
- Falls back to config.json if not set

### 1.7 Bug Fixes
- Fix `TWILIO_PHONE_NUMBE` typo in documentation/.env.example
- Investigate email auth failures

---

## Phase 2: Web App Service (Future Exploration)

Goal: Offer this as a hosted service where users configure via web UI.

### Architecture Overview

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   Web Frontend  │──────│   API Server    │──────│    Database     │
│  (React/Vue)    │      │   (FastAPI)     │      │  (PostgreSQL)   │
└─────────────────┘      └────────┬────────┘      └─────────────────┘
                                  │
                         ┌────────▼────────┐
                         │  Worker Processes│
                         │  (per-user bots) │
                         └─────────────────┘
```

### Key Components

**2.1 User Authentication**
- OAuth with Google/GitHub, or email/password
- JWT tokens for API auth

**2.2 Database Schema**
- Users table (auth, subscription tier)
- Telegram sessions (encrypted, per-user)
- Configurations (chats, keywords, destinations per user)
- Notification logs (for debugging/history)

**2.3 Background Worker Architecture**
- Options: Celery + Redis, or simpler ARQ/dramatiq
- One monitoring task per user
- Graceful scaling: add workers as users grow

**2.4 Telegram Session Challenge**
- **Problem**: Each user needs their own Telegram session (phone auth)
- **Options**:
  a) User provides existing session file (advanced users)
  b) Web-based QR code auth flow (complex to implement)
  c) Bot token approach (user creates bot, adds to groups - limited)
- This is the hardest part of the web app

**2.5 Web UI Features**
- Dashboard: active monitors, recent matches
- Chat selector (list user's Telegram groups)
- Keyword manager
- Destination configuration (with test send)
- Notification history

**2.6 Billing/Quotas (if monetized)**
- Free tier: 1 chat, 5 keywords, Telegram-only forwarding
- Paid tier: unlimited chats, all notification channels

### Complexity Assessment

| Component | Difficulty | Notes |
|-----------|------------|-------|
| API + Database | Medium | Standard CRUD operations |
| Worker system | Medium | Celery/ARQ well-documented |
| Web UI | Medium | Basic forms and dashboards |
| Telegram session flow | **High** | Auth UX is the challenge |
| Multi-tenancy security | **High** | Handling user sessions securely |
| Scaling | Medium | Stateless workers + DB |

### Recommended Stack
- **Backend**: FastAPI (async, fast, good docs)
- **Database**: PostgreSQL + SQLAlchemy
- **Task queue**: ARQ (async, simple) or Celery (more features)
- **Frontend**: React or Vue (or start with server-rendered Jinja)
- **Hosting**: Railway, Render, or VPS with Docker Compose

---

## Implementation Order

### Phase 1 (Self-Hosted) - Recommended Order:
1. Signal-based shutdown (foundational for Docker)
2. Dockerfile + docker-compose.yml
3. Retry logic for notifications
4. Health monitoring
5. Logging improvements
6. Env var configuration

### Phase 2 (Web App) - If pursued:
1. Spike: Telegram web auth flow feasibility
2. API server skeleton with user auth
3. Database schema + basic CRUD
4. Single-user worker prototype
5. Web UI MVP
6. Multi-user scaling

---

## Decisions Made
- **Deployment**: Docker (portable, works on mini-PC, VPS, or cloud)
- **Backwards compatible**: Interactive mode (`python main.py`) unchanged
- **Phases**: Sequential (perfect self-hosted first, then revisit web app)
- **Health monitoring**: File-based (simple, no extra dependencies)
- **Scope**: Docker only (no systemd instructions needed)
- **Phase 2**: Keep as future sketch, revisit after Phase 1 complete

## Portability

The same Docker setup works on:
- **Mini-PC at home** (free, always on)
- **VPS** (Oracle free tier, Hetzner $3/mo)
- **Cloud platforms** (Railway, Fly.io - auto-deploy from git)

To move between environments:
1. Copy `config.json` and `sesh.session`
2. Set env vars (API_ID, API_HASH, etc.)
3. `docker-compose up -d`
