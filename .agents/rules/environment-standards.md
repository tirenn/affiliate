# Strict Zero-Hardcoded Environment Values Rule

1. **Zero Hardcoded Values in Code**:
   - Connection strings, URLs, ports, secrets, hostnames, and credentials MUST NEVER be hardcoded in application code, Dockerfiles, or docker-compose files.
   - Fallback defaults in code (e.g. os.getenv("KEY", "default"), process.env.VAR || "default", or VAR: str = "default") are strictly forbidden for environment configurations.

2. **Values Exist ONLY in .env**:
   - Configuration values reside exclusively in .env.
   - The code reads directly from the environment without embedding default fallback values.

3. **Template in .env.example**:
   - All necessary environment variable keys must be documented in .env.example.
   - .env must be in .gitignore and never committed to version control.

4. **Docker & Compose**:
   - docker-compose.yml must use variable expansion (e.g. ${DATABASE_URL}, ${BACKEND_PORT}, ${FRONTEND_PORT}) loaded from .env, without hardcoded inline values.
