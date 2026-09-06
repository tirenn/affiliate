# Autonomous Threads Affiliate Marketing Bot 🚀

An autonomous AI affiliate marketing system that uses an LLM agent with Playwright browser tools to discover viral discussions, compose context-aware promotional copy, and publish replies directly to [Meta Threads](https://www.threads.net) on a configurable schedule or on-demand.

[![Architecture Document](https://img.shields.io/badge/Architecture-Overview-blue?style=for-the-badge)](ARCHITECTURE.md)

---

## 🏗️ System Architecture & High-Level Design Flow

Detailed architecture documentation, sequence diagrams, and database schema are available in [**ARCHITECTURE.md**](ARCHITECTURE.md).

![System Architecture Overview](docs/images/architecture_flow.jpg)

---

## 🌟 Key Features

1. **Agentic LLM with Playwright Browser Tools**:
   - Autonomous browser automation using Playwright Chromium (`mcr.microsoft.com/playwright/python:v1.62.0-noble`).
   - Session cookie persistence (`threads_session.json`) to prevent repeated logins and bypass 2FA challenges.
   - Targeted DOM locator targeting the 90-degree rotated SVG arrow reply button with post-submission verification.
2. **AI Copy Generation (OpenRouter Free Tier)**:
   - Context-aware Indonesian marketing copy generated using OpenRouter (`openrouter/free`).
3. **Zero-Storage Base64 Screenshot Storage**:
   - In-memory JPEG capture (`quality=65`) stored directly as Base64 Data URLs (`data:image/jpeg;base64,...`) in SQLite. Zero disk clutter.
4. **Automatic Queue Deletion on Post Success**:
   - As soon as an affiliate comment is verified live on Threads, the product is removed from the active queue while the full history log is preserved in `post_logs`.
5. **Dual Interface**:
   - **Public History Log (`/`)**: Read-only public timeline showing posted threads, affiliate links, and Base64 screenshots (Port 7082).
   - **Admin Portal (`/admin`)**: Secured with `x-admin-key`. Allows CSV product uploading, queue management, live testing, and system settings.
6. **Strict Zero-Hardcoded Environment Standard**:
   - Zero hardcoded ports, passwords, or connection strings in code or YAML files.
   - Secrets managed via Doppler; variables isolated in `.env` files.

---

## 📋 CSV Format

Create or upload a `.csv` or `.tsv` file with the following headers:

```csv
product_name,affiliate_url
Sony WH-1000XM5 Wireless Noise Canceling Headphones,https://amzn.to/example-sony-xm5
Logitech MX Master 3S Wireless Performance Mouse,https://amzn.to/example-mx-master-3s
```

*Note: Shopee affiliate export format (tab-delimited TSV containing `ID Produk`, `Nama Produk`, `Link Komisi Ekstra`) is also supported natively with automatic deduplication.*

---

## 🚀 Quickstart Guide

### Option 1: Run with Docker Compose (Recommended)

```bash
# 1. Copy environment template
copy .env.example .env
copy backend\.env.example backend\.env
copy frontend\.env.example frontend\.env

# 2. Build and start containers
docker compose up --build -d
```

- **Public Post Log**: [http://localhost:7082](http://localhost:7082)
- **Admin Console**: [http://localhost:7082/admin](http://localhost:7082/admin)
- **API Documentation**: [http://localhost:8084/docs](http://localhost:8084/docs)

---

### Option 2: Run Locally for Development

#### 1. Backend Setup
```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
playwright install chromium

copy .env.example .env
# Start FastAPI backend
uvicorn app.main:app --reload --port 8084
```

#### 2. Frontend Setup
```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

---

## 🔒 Configuration & Environment Isolation

All infrastructure settings are strictly loaded from `.env` files (or Doppler in production).

### Root `.env`
```env
DATABASE_URL=sqlite+aiosqlite:///./data/affiliate.db
BACKEND_PORT=8084
FRONTEND_PORT=7082
NEXT_PUBLIC_API_URL=http://localhost:8084
X_ADMIN_KEY=your_secret_admin_key
```

### Dynamic Settings in Web Admin Dashboard
All bot credentials and runtime behaviors are managed directly in the Web Admin Dashboard (`http://localhost:7082/admin`) and stored securely in SQLite:
- Threads Username & Password
- OpenRouter API Key & Model
- Viral Post Criteria (Min Comments & Likes threshold)
- Cron Scheduling Interval (minutes) & Window Limiting
- Headless Browser Mode toggle

---

## 🔄 CI/CD & Deployment via GitHub Actions

The repository includes complete GitHub Actions CI/CD workflows:

| Workflow | Trigger | Description |
| :--- | :--- | :--- |
| **`ci-backend.yml`** | PR / Push to `main` / `master` (`backend/**`) | Python 3.12 syntax compile checks & Pytest unit tests |
| **`ci-frontend.yml`** | PR / Push to `main` / `master` (`frontend/**`) | Node.js 20 dependency install & Next.js production build check |
| **`deploy.yml`** | Push Git Tag `v*-be` or `v*-fe` | Automated SSH deployment to VPS (`/root/Projects/affiliator`) with Doppler secrets sync |

### Tag Deployment Commands

- **Deploy Backend**:
  ```bash
  git tag v1.0.0-be
  git push origin v1.0.0-be
  ```
- **Deploy Frontend**:
  ```bash
  git tag v1.0.0-fe
  git push origin v1.0.0-fe
  ```

> *Tags outside `^v[0-9]+\.[0-9]+\.[0-9]+-(be|fe)$` are strictly rejected by the deployment pipeline.*

---

## 🧪 Testing

Run backend unit tests:
```bash
# In backend directory:
python -m pytest -v tests
```

Tests verify:
- Health check & API routes
- Header-based authentication (`x-admin-key`)
- Shopee CSV upload, parser, and deduplication
- Bulk deletion and queue cleanup
- **Automatic product deletion from SQLite upon successful posting**
