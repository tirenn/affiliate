# Strict Zero-Hardcoded Environment Values Rule

1. **Zero Hardcoded Values in Code**:
   - Connection strings, URLs, ports, secrets, hostnames, and credentials MUST NEVER be hardcoded in application code, Dockerfiles, or docker-compose files.
   - Fallback defaults in code (e.g. os.getenv("KEY", "default"), process.env.VAR || "default", or VAR: str = "default") are strictly forbidden for environment configurations.

2. **Values Exist ONLY in .env**:
   - Configuration values reside exclusively in .env.
   - The code reads directly from the environment without embedding default fallback values.

3. **Zero Env Values or Fallbacks in ANY YAML / Workflow Files**:
   - NEVER expose or hardcode environment values, secrets, ports, URLs, or fallback defaults in ANY YAML file (docker-compose.yml, .github/workflows/*.yml, etc.).
   - Inline fallbacks such as ${PORT:-8084}, ${VAR:-default}, or ${{ secrets.X || 'fallback' }} are STRICTLY FORBIDDEN. Use strict variable substitution ${VARIABLE_NAME} only.
   - In GitHub Actions CI/CD workflows, NEVER put hardcoded passwords, tokens, API URLs, or admin keys in env: blocks. Use repository secrets ${{ secrets.SECRET_NAME }} or dynamic environment derivation.

4. **Template in .env.example**:
   - All necessary environment variable keys must be documented in .env.example.
   - .env must be in .gitignore and never committed to version control.
