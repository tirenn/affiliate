# Autonomous Threads Affiliate Marketing Bot 🚀

An autonomous AI affiliate marketing system that uses an LLM agent with Playwright browser tools to compose viral promotional copy and publish directly to [Meta Threads](https://www.threads.net) on a configurable schedule (cron/interval) or on-demand.

---

## 🌟 Key Features

1. **Agentic LLM with Playwright Browser Tools**:
   - The LLM acts as an autonomous browser agent with dynamic tool calling: `browser_navigate`, `browser_click`, `browser_fill`, `browser_press_key`, `browser_wait`, `browser_take_screenshot`, `browser_get_page_summary`, and `finish_post`.
   - **OpenRouter Free Tier**: Powered exclusively by OpenRouter's free models (default: `openrouter/free`, routing to the best available free model with zero cost). All other proprietary models removed.
2. **SQLite Storage (Zero-Config Database)**:
   - Stores all products, settings, execution logs, and step-by-step traces directly in a high-performance SQLite database with WAL mode enabled.
3. **Automatic Queue Deletion on Post Success**:
   - **Per requirement:** As soon as a product is successfully published on Threads, its row is automatically removed from the active `products` queue, while the complete post and screenshot audit history is retained in `post_logs`.
4. **Dual Interface**:
   - **Page 1: Public History Log (`/`)**: Read-only public feed with product names, affiliate links, generated post text, status badges, and screenshots. **No login required.**
   - **Page 2: Admin Portal (`/admin`)**: Secured with an admin passcode. Allows uploading product CSVs, managing the queue, configuring Threads credentials / LLM keys, triggering manual "Post Next Item Now" runs, and inspecting granular step-by-step agent traces.
5. **Anti-Spam Scheduling**:
   - Configurable posting interval (in minutes/hours) with randomized anti-spam jitter delay to prevent bot rate-limits.

---

## 📋 CSV Format

Create or upload a `.csv` file with the following headers:

```csv
product_name,affiliate_url
Sony WH-1000XM5 Wireless Noise Canceling Headphones,https://amzn.to/example-sony-xm5
Logitech MX Master 3S Wireless Performance Mouse,https://amzn.to/example-mx-master-3s
Apple 2024 MacBook Air 13-inch M3 Chip,https://amzn.to/example-macbook-air-m3
```

A sample file is provided at `sample_products.csv`.

---

## 🚀 Quickstart Guide

### Option 1: Run Locally (Windows / macOS / Linux)

#### 1. Backend Setup
```bash
cd backend

# Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

# Install dependencies and Playwright browser
pip install -r requirements.txt
playwright install chromium

# Copy environment variables
copy .env.example .env

# Run FastAPI server
uvicorn app.main:app --reload --port 8000
```
API Documentation will be live at `http://localhost:8000/docs`.

#### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
The application will be accessible at:
- Public Post Feed: `http://localhost:3000`
- Admin Console: `http://localhost:3000/admin` (Default passcode: `admin123`)

---

### Option 2: Run with Docker Compose

```bash
docker compose up --build -d
```
This builds and starts both the FastAPI backend and Next.js frontend with persistent SQLite storage mounted at `./backend/data`.
- **Public Post Log**: [http://localhost:3005](http://localhost:3005)
- **Admin Console**: [http://localhost:3005/admin](http://localhost:3005/admin) *(Passcode: `admin123`)*
- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🔒 Configuration & Environment Variables

Copy `.env.example` to `backend/.env` or configure via the Admin UI at `/admin`:

| Variable | Description | Default |
| :--- | :--- | :--- |
| `ADMIN_PASSCODE` | Secret key required to access `/admin` and protected APIs | `admin123` |
| `DATABASE_URL` | SQLite database URI | `sqlite+aiosqlite:///./data/affiliate.db` |
| `OPENROUTER_API_KEY` | OpenRouter API Key (get from openrouter.ai/keys) | - |
| `OPENROUTER_MODEL` | Model identifier on OpenRouter | `openrouter/free` |
| `THREADS_USERNAME` | Threads / Instagram account username or email | - |
| `THREADS_PASSWORD` | Threads / Instagram account password | - |
| `HEADLESS_BROWSER` | Run Playwright in headless mode | `true` |
| `SCHEDULER_ENABLED` | Enable automated interval posting | `false` |
| `SCHEDULER_INTERVAL_MINUTES` | Interval between posts | `60` |
| `SCHEDULER_JITTER_MINUTES` | Random jitter delay added to each post | `5` |

---

## 🧪 Testing

Run backend unit tests:
```bash
# In project root:
$env:PYTHONPATH="backend"
.venv\Scripts\pytest -v backend\tests
```
Tests cover:
- Health check & API routes
- Admin authentication enforcement
- CSV parser & queue insertion
- Public access to logs without credentials
- **Verification of product row deletion from SQLite upon successful post**
