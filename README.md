# BiblioTPV

A web point-of-sale application for independent bookshops. The React/TypeScript frontend, FastAPI backend, and PostgreSQL database run through Docker Compose. Python, Node.js, npm, and PostgreSQL are not required on the host; Docker Engine with the Compose v2 plugin is required.

## Quick Start

1. Copy `.env.example` to `.env`. Set unique values for `POSTGRES_PASSWORD`, `APP_SECRET` (at least 32 characters), and `BOOTSTRAP_ADMIN_PASSWORD` (at least 12 characters). The blank placeholders intentionally prevent startup until secrets are configured. Keep `.env` out of version control.
2. Set `BOOTSTRAP_ADMIN_USERNAME` and `BOOTSTRAP_ADMIN_PASSWORD` to the first administrator credentials.
3. Start the application:

   ```bash
   sh scripts/up.sh
   ```

The startup script generates `frontend/package-lock.json` inside Docker if it is missing, then builds and starts the stack. Compose waits for PostgreSQL, applies Alembic migrations, creates the first administrator, and only then starts the API and web service. Bootstrap is a no-op after the database already contains users.

Open <http://localhost:8080>. Change the port with `WEB_PORT`. The first startup requires internet access to download base images and dependencies. Docker must be running, and the current user must have permission to access its daemon.

## Development

```bash
docker compose -f compose.yaml -f compose.dev.yaml --profile dev up --build
```

Vite is available at <http://localhost:5173> and FastAPI at <http://localhost:8000>. Source code is mounted into the containers for hot reload. Database migrations and first-admin creation are handled by the `init` service.

## Tests and Quality

```bash
make test
make lint
docker compose --profile test run --build --rm frontend-tests npm run build
docker compose build
```

Backend tests use an ephemeral PostgreSQL service in the `test` profile, separate from the persistent application database. The `make test` target stops that database container when the backend suite exits, including on failure.

## Operations

- `docker compose ps`: show service status.
- `docker compose logs -f`: follow application logs.
- `docker compose --profile tools run --rm migrate`: apply database migrations explicitly.
- `docker compose down`: stop services while preserving PostgreSQL data.
- Avoid `docker compose down -v` for routine cleanup; it permanently deletes the database volume.

PostgreSQL is not published to the host. For production, use HTTPS, set `APP_ENV=production`, `COOKIE_SECURE=true`, and `ALLOWED_ORIGIN` to the exact public origin. Use deployment-managed secrets instead of development credentials. `PRICES_INCLUDE_TAX` controls whether catalog prices include tax. MVP receipts are informational, not certified invoices; verify local tax and invoicing requirements before commercial use.

## Documentation

- [Architecture](doc/arquitectura.md)
- [API reference](doc/api-reference.md)
- [Installation and recovery guide](doc/guia-instalacion.md)
- [User manual](doc/manual-usuario.md)
