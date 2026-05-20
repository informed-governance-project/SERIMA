# CLAUDE.md — NISINP (Governance Platform)

## Project Overview

NIS2 incident notification and governance platform for NC3-LU. Django monolith with two main apps:
- `governanceplatform/` — core: users, auth, regulated entities, sectors, regulations
- `incidents/` — incident workflow, notifications, PDF reports

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Language | Python | >=3.12,<4 |
| Framework | Django | >=6.0,<7 |
| Database | PostgreSQL | 15 (CI) |
| Package manager | Poetry | — |
| Translations | django-parler | custom fork (github.com/informed-governance-project/django-parler) |
| Auth | django-otp + two-factor-auth | >=1.1.6 / >=1.15.5 |
| API | Django REST Framework + drf-spectacular | >=0.29.0,<0.30 |
| Async tasks | Celery + Redis | >=5.5.1 / >=7.4.0 |
| PDF generation | WeasyPrint | >=68.0,<69 |
| Frontend | Bootstrap 5 + bootstrap-icons | ^5.3.3 / ^1.11.3 |
| JS build | Node.js + npm | 24.x / 11.x |
| Type checking | mypy | ^2.0.0 |
| Testing | pytest-django | ^4.11.1 |

## Build & Run

```bash
# Install dependencies
poetry install

# Dev server (requires config.py — copy from config_dev.py as starting point)
python manage.py runserver

# Or use the Makefile shortcuts
make run          # dev server
make migrate      # apply migrations
make migration    # create new migrations
make superuser    # create admin user
make update       # install deps + collectstatic + compilemessages + migrate
```

## Configuration

Config is loaded from `governanceplatform/config.py` (not in repo).
In CI and dev, `governanceplatform/config_dev.py` is used as fallback.

**Required config values**: `SECRET_KEY`, `HASH_KEY`, `DEBUG`, `DATABASES`, `ALLOWED_HOSTS`, `PUBLIC_URL`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_SENDER`, `REGULATOR_CONTACT`, `SITE_NAME`, `CELERY_BROKER_URL`, `API_ENABLED`, `COOKIEBANNER`, `MAX_PRELIMINARY_NOTIFICATION_PER_DAY_PER_USER`.

Also set `PARLER_LANGUAGES` and `PARLER_DEFAULT_LANGUAGE_CODE` for translation config.

## Testing

```bash
# Run all tests
poetry run pytest

# Run with output
poetry run pytest -v

# Run specific app
poetry run pytest governanceplatform/tests/
poetry run pytest incidents/tests/

# Run with HTML report
poetry run pytest --html=../report.html --self-contained-html
```

Tests require a running PostgreSQL instance matching the config. In CI, `DJANGO_CI=True` env var triggers `config_dev.py` automatically.

Test files: `governanceplatform/tests/test_*.py`, `incidents/tests/test_*.py`
Root `conftest.py` provides: `client`, `otp_client` fixtures, and `import_from_json` / `get_or_create_related` helpers used across tests.

### Testing philosophy

- Write tests before or alongside new code; don't leave coverage as an afterthought.
- Target 80 %+ line coverage on new code paths.
- Test **behaviours**, not implementation details — assert what the system does, not how.
- Avoid mocking the database. Integration tests that hit a real PostgreSQL instance catch regressions that pure mock-based tests miss.
- One test per logical scenario. Prefer many focused tests over one large test with multiple assertions.
- Use `pytest.mark.django_db` and the provided fixtures (`client`, `otp_client`) rather than rolling your own setup.

## Project Structure

```
governanceplatform/   Core app — users, auth, settings, admin site
  models.py           TranslatableModel subclasses (Sector, Regulator, Regulation…)
  settings.py         Main Django settings (reads from config.py)
  config_dev.py       Dev/CI fallback configuration
  admin.py            Custom admin site registration
  views.py            Auth + account views
  middleware.py       OTP enforcement, terms acceptance
  migrations/         60+ database migrations

incidents/            Incident app — forms, workflow, PDF, email
  models.py           TranslatableModel subclasses (Impact, Question, Workflow…)
  views.py            Incident CRUD and notification workflows
  admin.py            Admin configuration for incident models
  migrations/

docker/               Docker + docker-compose files
docs/                 Sphinx documentation
locale/               .po translation files (en, fr, nl, de)
templates/            HTML templates (base, registration, incidents…)
theme/                External theme repo (not committed here)
```

## Translations (django-parler)

Almost all domain models inherit from `parler.models.TranslatableModel` with a `translations = TranslatedFields(...)` attribute. Supported languages: `en`, `fr`, `nl`, `de`.

```python
from parler.models import TranslatableModel, TranslatedFields


class MyModel(TranslatableModel):
    translations = TranslatedFields(name=models.CharField(max_length=100))
```

When writing fixtures or test data, always call `obj.set_current_language("en")` before setting translated fields. The `import_from_json` helper in `conftest.py` handles this automatically.

To regenerate `.po` files:
```bash
make generatepot   # runs makemessages -a --keep-pot
python manage.py compilemessages
```

## API

REST API via DRF. OpenAPI schema auto-generated by drf-spectacular.

```bash
make openapi   # writes docs/_static/openapi.yml
```

API is feature-flagged: set `API_ENABLED = True` in config to expose endpoints.

## Conventions

- **Commit style**: `type: description` (feat, fix, refactor, docs, test, chore) or `[APP]Message`
- **Branch naming**: `feat/`, `fix/`, `test/`, `review/`, descriptive kebab-case
- **Main branch**: `master`
- **Target branch for PRs**: `dev` — open all pull requests against `dev`, not `master`. `master` is updated only via releases.
- **Python style**: Black + isort (configured in pyproject.toml)
- **Linting**: flake8

```bash
poetry run black .
poetry run isort .
poetry run flake8
```

### Code style principles

- **No speculative code.** Don't add features, fallbacks, or abstractions beyond what the task requires. A bug fix doesn't need surrounding cleanup.
- **No defensive validation for impossibilities.** Only validate at system boundaries (user input, external APIs). Trust Django's ORM and framework guarantees internally.
- **Comments explain WHY, never WHAT.** Well-named identifiers already document what the code does. Add a comment only when there is a hidden constraint, a subtle invariant, or a known bug workaround. Remove any comment that restates the code.
- **Prefer editing existing files** to creating new ones. Don't duplicate logic; extend what already exists.
- **Errors must surface.** Never swallow exceptions silently (`except: pass`). Let Django's error handling and Celery's retry mechanisms propagate failures where they can be logged and acted upon.
- **Type hints on new public functions.** Python 3.12 supports full PEP 604 union types (`X | Y`). Use them.

## Database & ORM

- **Always use the ORM** over raw SQL. Raw `cursor.execute` is only acceptable in migrations where the ORM is not yet available — and even there, prefer `RunPython` with ORM calls when possible.
- **Avoid N+1 queries.** Use `select_related` for ForeignKey/OneToOne traversals and `prefetch_related` for ManyToMany/reverse FK sets.
- **Add database indexes** for any field used in `filter()`, `order_by()`, or a JOIN predicate that isn't already indexed.
- **Migrations are append-only.** Never edit a committed migration. Create a new one.
- **Data migrations** must be reversible where feasible. Provide both `forwards` and `backwards` functions.

```python
# Good — ORM, avoids N+1
incidents = Incident.objects.select_related("company").prefetch_related("impacts")

# Avoid — raw SQL in application code
cursor.execute("SELECT * FROM incidents_incident WHERE company_id = %s", [cid])
```

## Security

This application handles sensitive incident data subject to NIS2 regulations. Security is not optional.

- **Input validation at every boundary.** Forms, API serializers, and management commands all receive untrusted data. Validate and sanitize before use.
- **Never expose internal identifiers** (primary keys, session tokens) in URLs or responses unless explicitly required. Use opaque slugs or UUIDs where possible.
- **CSRF, XSS, SQL injection** — rely on Django's built-in protections; don't bypass them. Never mark user-supplied content `safe` in templates without sanitisation.
- **No secrets in code or logs.** `SECRET_KEY`, credentials, and API tokens live in `config.py` only. If a secret appears in a diff, rotate it immediately.
- **Least-privilege queries.** Views should fetch only the objects the authenticated user is permitted to see. Always scope querysets by the request user's organisation/role.
- **2FA enforcement** is handled by `middleware.py`. Do not add views that bypass `OTPRequiredMixin` or the OTP middleware without an explicit sign-off.

## Performance

- Measure before optimising. Use Django Debug Toolbar in dev (`debug_toolbar` is already in installed apps when `DEBUG=True`).
- Prefer database-level aggregation (`annotate`, `aggregate`) over Python-level loops on large querysets.
- Celery tasks exist for anything slow: PDF generation (WeasyPrint), email dispatch, heavy report queries. Don't do these synchronously in a request/response cycle.
- Cache translated strings and expensive lookups at the view layer; `django-parler` translations hit the DB per language per object if not batched.

## Accessibility

Templates use Bootstrap 5. When adding or modifying UI components:

- Use semantic HTML elements (`<button>`, `<nav>`, `<main>`, `<section>`) rather than `<div>` with click handlers.
- Every interactive element must be keyboard-reachable and have a visible focus style.
- Form inputs must have associated `<label>` elements (not just placeholders).
- Error messages must be programmatically associated with their field (`aria-describedby` or Django form error rendering).
- Images require descriptive `alt` text; decorative images use `alt=""`.

## Common Tasks

| I want to… | Look at… |
|------------|---------|
| Add a translatable model | `governanceplatform/models.py` — mirror existing `TranslatableModel` pattern |
| Add an admin view | `governanceplatform/admin.py` or `incidents/admin.py` |
| Add an API endpoint | `incidents/` or `governanceplatform/` — add serializer + view + URL |
| Add a test | Mirror files in `governanceplatform/tests/` or `incidents/tests/` |
| Update config defaults | `governanceplatform/config_dev.py` |
| Change middleware order | `governanceplatform/settings.py` → `MIDDLEWARE` list |
| Add a Celery task | `governanceplatform/tasks.py` or `incidents/tasks.py` |
| Generate model diagram | `make models` |

## Changelog

`CHANGELOG.md` lives at the repo root and follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format.

**Every PR that ships user-facing changes must include a `CHANGELOG.md` update.**

Rules:
- Add entries under `## [Unreleased]` — never edit a released version's section.
- Use the correct category: `Added` (new feature), `Changed` (behaviour change), `Fixed` (bug fix).
- Reference the GitHub issue number where one exists, e.g. `Fixed: foo bar (#123)`.
- When a version is released, rename `[Unreleased]` to `[X.Y.Z] - YYYY-MM-DD` and add a fresh empty `[Unreleased]` block above it. Also add the comparison link at the bottom of the file.
- Omit pure chore entries (dependency bumps, translation updates, theme submodule bumps) unless they affect end-users.

## CI/CD

GitHub Actions workflows:
- `pytest.yml` — runs tests on push/PR against PostgreSQL service container
- `docker-ghcr.yml` — builds and pushes Docker image to ghcr.io
- `codeql.yml` — static security analysis (Python + JavaScript)
- `pythonapp.yml` — additional Python checks

**Never bypass CI.** If a check fails, fix the root cause — don't skip hooks (`--no-verify`) or force-push over a failing status. A green CI pipeline is the minimum bar for merging.
