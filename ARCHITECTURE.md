# System Architecture & High-Level Design Flow 🏗️

This document details the architectural design, core subsystems, data models, and end-to-end execution flow of the **Autonomous Threads Affiliate Marketing Bot**.

---

## 1. High-Level Architecture Overview

![System Architecture](docs/images/architecture_flow.jpg)

The platform is designed as a decoupled, asynchronous multi-tier architecture with zero external database dependencies:

```mermaid
graph TB
    subgraph "External Cloud / Services"
        GH["GitHub Actions CI/CD<br/>(Tagged Releases)"]
        DOPPLER["Doppler Secrets Vault<br/>(BE / FE Service Tokens)"]
        OPENROUTER["OpenRouter AI Gateway<br/>(openrouter/free)"]
        THREADS["Meta Threads<br/>(threads.net)"]
    end

    subgraph "Host / VPS Environment"
        subgraph "Docker Compose Network"
            FE["Frontend Service (Next.js 14)<br/>Port: 7082"]
            BE["Backend Service (FastAPI / Uvicorn)<br/>Port: 8084"]
            DB[("SQLite Database<br/>WAL Mode enabled")]
            PLAYWRIGHT["Playwright Automation Engine<br/>(Chromium Headless)"]
        end
    end

    GH -->|Deploy via SSH| BE
    GH -->|Deploy via SSH| FE
    DOPPLER -->|Sync .env| BE
    DOPPLER -->|Sync .env| FE

    FE -->|REST API / x-admin-key| BE
    BE -->|Async SQLAlchemy| DB
    BE -->|Copy Generation| OPENROUTER
    BE -->|Control Engine| PLAYWRIGHT
    PLAYWRIGHT -->|Scrape & Post| THREADS
```

---

## 2. Core Architectural Subsystems

### 2.1. Next.js Frontend UI (Port 7082)
- **Public Audit Feed (`/`)**: Read-only public dashboard showing the timeline of posted affiliate threads, status badges, generated Indonesian promotional copy, direct Threads reply links, and full Base64 screenshot modal previews without authentication.
- **Admin Portal (`/admin`)**: Protected by `x-admin-key` authentication. Provides:
  - CSV/TSV product upload with Shopee affiliate link deduplication.
  - Manual queue control and "Post Next Item Now" execution.
  - System configuration (Threads credentials, OpenRouter API keys, viral criteria thresholds, posting intervals).
  - Real-time step-by-step agent debug logs.
- **Client Architecture**: Next.js 14 App Router, React 18, Tailwind CSS, Lucide icons, and zero-storage Base64 Data URL image rendering.

### 2.2. FastAPI Backend Microservice (Port 8084)
- **Asynchronous Execution**: Fully async architecture powered by `asyncio`, `aiosqlite`, `httpx`, and `APScheduler`.
- **Domain Routers**:
  - `/api/products`: Queue operations (upload CSV, list, delete, bulk delete).
  - `/api/logs`: Audit logs retrieval and log clearing.
  - `/api/cron`: Background scheduler state management, manual trigger, interval adjustments.
  - `/api/settings`: Database-persisted configuration management.
  - `/api/health`: Container health check probe.
- **Security & Authorization**: Protected routes enforce `x-admin-key` header validation against database settings with fallback to `.env` (`X_ADMIN_KEY`).

### 2.3. SQLite with WAL Persistence Layer
- Stored on host-mounted volume `./backend/data/affiliate.db`.
- Operates in **Write-Ahead Logging (WAL)** mode for concurrent read/write transactions without table locking during Playwright execution.
- **Zero-Storage Screenshot Optimization**: Screenshots are captured as compressed in-memory JPEG bytes (`quality=65`) and stored as Base64 Data URLs (`data:image/jpeg;base64,...`) directly in the database. No raw image files are persisted on disk.

### 2.4. Playwright Browser Automation Engine
- Utilizes Microsoft Playwright Chromium (`mcr.microsoft.com/playwright/python:v1.62.0-noble`).
- **Session Persistence**: Saves authentication cookies into `backend/data/sessions/threads_session.json` upon initial login; subsequent runs reuse existing session cookies to bypass two-factor challenges and rate limits.
- **Targeted DOM Automation**: Uses synthetic human typing delays (`delay=15ms`) to properly populate Meta Threads' Lexical editor state, targeting the rotated 90-degree arrow SVG reply button (`div[role="button"][aria-label="Reply"]`).
- **Submission Guarantee**: Performs strict verification by monitoring that the composer textarea clears completely (`innerText == ""`) within an 8-second window.

### 2.5. Doppler Configuration & Environment Isolation
- Adheres to the **Strict Zero-Hardcoded Environment Values Standard**.
- All environment configurations (`DATABASE_URL`, `PORT`, `X_ADMIN_KEY`, `NEXT_PUBLIC_API_URL`) reside exclusively in `.env` files managed by Doppler.
- Docker Compose, Dockerfiles, and GitHub Actions contain zero hardcoded ports, passwords, or connection strings.

---

## 3. High-Level Design Flow (End-to-End Lifecycle)

The complete lifecycle from product upload to social posting and automatic queue cleanup:

```mermaid
sequenceDiagram
    autonumber
    actor Admin as User / Admin
    participant FE as Next.js (Admin UI)
    participant BE as FastAPI Backend
    participant DB as SQLite DB
    participant LLM as OpenRouter AI
    participant PW as Playwright Engine
    participant TH as Meta Threads

    Note over Admin,DB: Phase 1: Product Ingestion & Queueing
    Admin->>FE: Upload Shopee / Affiliate CSV
    FE->>BE: POST /api/products/upload-csv (x-admin-key)
    BE->>DB: Deduplicate & Insert unposted products
    DB-->>BE: Confirm queued products
    BE-->>FE: Return uploaded summary

    Note over BE,TH: Phase 2: Autonomous Posting Cycle
    alt Triggered by Cron Interval OR Manual Button Click
        BE->>DB: Fetch next unposted product
        DB-->>BE: Return Product (Name, Category, Affiliate URL)
        
        BE->>PW: Launch browser & load session cookies
        PW->>TH: Navigate to Threads feed (https://www.threads.com)
        
        opt Session Expired or Not Logged In
            PW->>TH: Perform login with saved credentials
            PW->>BE: Save fresh cookies to threads_session.json
        end

        PW->>TH: Scan feed for viral threads (Min Comments OR Likes)
        TH-->>PW: Return matching viral thread URL & context snippet
        
        BE->>LLM: Generate casual Indonesian reply copy with affiliate link
        LLM-->>BE: Return generated marketing copy
        
        PW->>TH: Navigate to viral thread URL
        PW->>TH: Locate inline reply composer & type text (human delay)
        PW->>TH: Click reply submit button (SVG arrow)
        PW->>TH: Verify composer cleared & capture Base64 screenshot
        
        Note over BE,DB: Phase 3: Audit Logging & Queue Cleanup
        BE->>DB: INSERT post_logs (status='success', post_url, base64_screenshot)
        BE->>DB: DELETE FROM products WHERE id = product.id (Auto-removal)
        
        BE-->>FE: Real-time update (Public feed & Admin log refreshed)
    end
```

---

## 4. Database Schema Design

The SQLite database comprises 4 core tables:

```mermaid
erDiagram
    PRODUCT ||--o{ POST_LOG : "referenced_in"
    
    PRODUCT {
        int id PK
        string product_id "Shopee/Affiliate Product ID"
        string product_name "Product Title"
        string affiliate_url "Primary Affiliate Link"
        string extra_commission_url "Direct Short Link"
        string category "Extracted category"
        float price "Extracted price"
        boolean is_posted "Flag before auto-delete"
        datetime created_at "Ingestion timestamp"
    }

    POST_LOG {
        int id PK
        int product_id FK "Nullable reference"
        string product_name "Snapshot product title"
        string affiliate_url "Used affiliate link"
        string extra_commission_url "Used commission link"
        string target_thread_url "Threads URL commented on"
        text target_thread_snippet "Context of parent post"
        text post_text "AI-generated Indonesian copy"
        string threads_post_url "Direct permalink to reply"
        string threads_post_id "Internal Threads post ID"
        string status "success | failed | running"
        text error_message "Diagnostic failure details"
        text final_screenshot "Base64 JPEG Data URL"
        datetime created_at "Execution timestamp"
    }

    SYSTEM_SETTING {
        int id PK
        string key "threads_username | openrouter_api_key | etc."
        text value "Configured value"
        datetime updated_at "Last update timestamp"
    }

    CRON_STATE {
        int id PK
        boolean is_running "Active execution lock"
        datetime last_run_time "Previous run timestamp"
        datetime next_run_time "Scheduled next run"
        text error_message "Scheduler exception trace"
    }
```

---

## 5. CI/CD & Deployment Architecture

```mermaid
flowchart TD
    DEV[Developer / Committer] -->|Push Code to master| PR[PR / Master Push]
    PR -->|Trigger| CI_BE[Backend CI: Python 3.12, Syntax & Pytest]
    PR -->|Trigger| CI_FE[Frontend CI: Node.js 20, Next.js Build]

    DEV -->|Create Git Tag v1.0.0-be| TAG_BE[Tag: v*-be]
    DEV -->|Create Git Tag v1.0.0-fe| TAG_FE[Tag: v*-fe]
    DEV -->|Any invalid tag format| TAG_REJECT[Deploy Rejected ❌]

    TAG_BE -->|Trigger CD| DEPLOY[Deploy Workflow: appleboy/ssh-action]
    TAG_FE -->|Trigger CD| DEPLOY

    subgraph "VPS Server (/root/Projects/affiliator)"
        DEPLOY -->|SSH Command| SSH[Checkout Tag & Install Doppler CLI]
        SSH -->|Token DOPPLER_TOKEN_BE| DOP_BE[Download backend/.env]
        SSH -->|Token DOPPLER_TOKEN_FE| DOP_FE[Download frontend/.env]
        DOP_BE --> DOCKER_BUILD[docker compose up -d --build target_service]
        DOP_FE --> DOCKER_BUILD
        DOCKER_BUILD --> HEALTH[Verify Container Health & Output Logs]
        HEALTH --> PRUNE[Docker Image & Cache Prune]
    end
```

### Tag Conventions
- `vX.Y.Z-be`: Triggers deployment of the **FastAPI Backend** service.
- `vX.Y.Z-fe`: Triggers deployment of the **Next.js Frontend** service.
- **Strict Format Enforced**: Tags outside `^v[0-9]+\.[0-9]+\.[0-9]+-(be|fe)$` automatically terminate the GitHub Action with an exit code of 1.

---

## 6. Security & Operational Guardrails

1. **Strict Zero-Hardcoded Environment Values**:
   - Secrets, ports, credentials, and connection strings are strictly read from `.env` and Doppler.
   - Zero fallback strings or default values exist in code or YAML manifests.
2. **Rate-Limit & Anti-Spam Mitigation**:
   - APScheduler enforces minimum wait times between automated replies.
   - Configurable jitter delays randomize execution timestamps.
   - Playwright mimics human typing with natural character delays.
3. **Queue Integrity Guarantee**:
   - Products are deleted from the active queue only upon verified reply publication (`innerText == ""`).
   - If an error occurs (e.g. network failure, rate limit), the product remains safely in the queue for the next retry.
