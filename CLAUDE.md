# CLAUDE.md — SERIMA (Governance Platform)

## Project Overview

NIS2 incident notification and governance platform for NC3-LU. Django monolith with four apps:
- `governanceplatform/` — core: users, auth, regulated entities, sectors, regulations
- `incidents/` — incident workflow, notifications, PDF reports
- `securityobjectives/` — operator declarations against a regulator's framework, and the review cycle
- `reporting/` — report projects, MONARC risk-analysis import, DOCX/PDF report generation

`securityobjectives/` and `reporting/` are gated per regulator by the `Functionality` model, enforced in `governanceplatform/middleware.py`. A platform administrator must grant a regulator the functionality before its pages and menu entries become reachable — having the app installed is not enough.

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Language | Python | >=3.14,<4 |
| Framework | Django | >=6.0,<7 |
| Database | PostgreSQL | 18 (CI) |
| Package manager | Poetry | — |
| Translations | django-parler | >=2.4,<3 |
| Auth | django-otp + two-factor-auth | >=1.1.6,<2 / >=1.15.5,<2 |
| API | Django REST Framework + drf-spectacular | 3.17 (transitive) / >=0.30.0,<0.31 |
| Async tasks | Celery + Redis | >=5.5.1,<6 / >=8.0.0,<9 |
| PDF generation | WeasyPrint | >=70.0,<71 |
| Charts | Plotly + Kaleido | >=7.0.0,<8 / >=1.2.0,<2 |
| DOCX generation | docxtpl + python-docx | >=0.20.2,<0.21 / >=1.2.0,<2 |
| Admin import/export | django-import-export-extensions | >=1.10.0,<2 |
| Colour fields | django-colorfield | >=0.14.0,<0.15 |
| Frontend | Bootstrap 5 + bootstrap-icons | ^5.3.8 / ^1.13.1 |
| JS build | Node.js + npm | 24.x / 11.x |
| Lint & format | ruff | ^0.16.1 |
| Type checking | mypy | <2.4 |
| Testing | pytest-django | ^4.11.1 |

Kaleido renders Plotly charts to static images for the generated reports and bundles its own Chromium. It is the heaviest runtime dependency, and the reason `KALEIDO_CONCURRENCY_PER_WORKER` exists to cap how many renders a Celery worker runs at once.

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

**Optional values.** `settings.py` catches `AttributeError` for each of these and applies a default, so an older `config.py` still boots: `PATH_FOR_REPORTING_PDF` (where generated reports and admin import/export files are written), `SECURITY_OBJECTIVE_RETENTION_TIME_IN_DAY` (1825), `KALEIDO_CONCURRENCY_PER_WORKER` (1), `INCIDENT_RETENTION_TIME_IN_DAY` (1825), `TERMS_ACCEPTANCE_TIME_IN_DAYS` (365).

## Testing

```bash
# Run all tests
poetry run pytest

# Run with output
poetry run pytest -v

# Run specific app
poetry run pytest governanceplatform/tests/
poetry run pytest incidents/tests/
poetry run pytest securityobjectives/tests/
poetry run pytest reporting/tests/

# Run with HTML report
poetry run pytest --html=../report.html --self-contained-html
```

Test configuration lives in `pytest.ini` (not `pyproject.toml`). Its `addopts` are always applied:

```ini
addopts = --create-db --cov=governanceplatform --cov=incidents --cov=securityobjectives --cov=reporting --cov-report=term-missing
```

So every run recreates the test database and writes a `.coverage` file into the repo root. Set `COVERAGE_FILE` to a path outside the repo, or delete `.coverage` afterwards, to keep the working tree clean.

Tests require a running PostgreSQL instance matching the config. In CI, `DJANGO_CI=True` env var triggers `config_dev.py` automatically.

Test files: `<app>/tests/test_*.py` in each of the four apps.
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
  migrations/         65 database migrations

incidents/            Incident app — forms, workflow, PDF, email
  models.py           TranslatableModel subclasses (Impact, Question, Workflow…)
  views.py            Incident CRUD and notification workflows
  admin.py            Admin configuration for incident models
  migrations/

securityobjectives/   Security objectives app — declarations and regulator review
  models.py           Standard, Domain, SecurityObjective, SecurityMeasure, StandardAnswer…
  views.py            Declaration workflow, submit/review, Excel import, PDF download
  globals.py          Review statuses, `SO_` reference prefix, sortable fields
  tasks.py            Celery tasks
  migrations/         43 migrations

reporting/            Reporting app — report projects and document generation
  models.py           Project, RiskData, Observation, Template, GeneratedReport…
  views.py            Project CRUD, dashboard, generation status, recommendations
  import_risk_analysis.py  MONARC JSON validation and import
  tasks.py            Celery report generation
  migrations/         23 migrations

docker/               Docker + docker-compose files
docs/                 Sphinx documentation
locale/               .po translation files (fr, nl, de — en is the source language)
templates/            HTML templates (base, registration, incidents…)
theme/                Separate git clone, gitignored from this repo — see below
```

### Modules not on `dev`

`reporting/` and `securityobjectives/` merged into `dev` on 2026-09-18 (PR #880) and are ordinary apps now — see Project Structure above.

`governanceplatform/connectors/` still lives only on `feat/observer-connectors`, where its commits are tagged `[Observer]`. On `dev` the directory may appear on disk holding only `__pycache__` — bytecode left by switching branches. It carries no source files there, is tracked by neither git nor `.gitignore`, and is absent from `INSTALLED_APPS`, so it does nothing on `dev`. The leftover bytecode is safe to drop at any time; it is regenerated on the branch that owns the source:

```bash
find governanceplatform/connectors -name __pycache__ -type d -exec rm -rf {} +
```

## Frontend (theme repo)

**All frontend code (templates, static assets, CSS/JS, theme-level translations) lives in a separate repo checked out at `theme/`.** It is a standalone git clone (not a submodule) and is gitignored from the main `serima` repo — changes made inside `theme/` must be committed and pushed from within that directory, not from `serima`.

- Remotes: `origin` → `informed-governance-project/default-theme` (upstream default theme), `serimabe-theme` → `informed-governance-project/serimabe-theme` (NC3/SERIMA-specific fork)
- Working branch there is typically `dev`
- Contains its own `templates/`, `static/`, `locale/`, `docker/`, and `globals.py`
- **CI pins a theme branch.** `.github/workflows/pytest.yml` checks out `default-theme` at a fixed `ref:`, and each serima branch points at its counterpart — `dev` → theme `dev`, `reporting` → theme `reporting`. A frontend change lands in two repos, and merging a serima branch without fixing that `ref:` silently leaves CI building against the wrong theme.

When a task touches UI/frontend (templates, CSS, JS, static assets), check `theme/` first — it likely overrides or supplies the actual rendered templates rather than `serima/templates/`.

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

**There is no API.** DRF and drf-spectacular are installed and configured in `settings.py`, but `rest_framework` is imported nowhere else: there are no serializers, no viewsets, no routers, and no API paths in any `urls.py`. `API_ENABLED` is copied from `config.py` into settings and then consumed nowhere.

```bash
make openapi   # writes docs/_static/openapi.yml
```

The generated schema is therefore empty (`paths: {}`), and so is the committed `docs/_static/openapi.yml`. Setting `API_ENABLED = True` does not change this — the flag is inert. Building an API here means adding serializers, views, and URL routes from scratch; there is no existing endpoint to mirror.

## Conventions

- **Commit style**: `type: description` (feat, fix, refactor, docs, test, chore) or `[APP]Message`, optionally with a sub-level tag: `[APP][sub-area]Message` (e.g. `[NI][views]`, `[NI][forms]`)
  - `[NI]` — incident notification changes (`incidents/` folder)
  - `[GOV]` — governance changes (`governanceplatform/` folder)
  - `[SO]` — security objectives changes (`securityobjectives/` folder)
  - `[RG]` — reporting changes (`reporting/` folder)
  - `[Observer]` — observer connector changes (`governanceplatform/connectors/`) — on `feat/observer-connectors`, not merged
- **Branch naming**: `feat/`, `fix/`, `test/`, `review/`, descriptive kebab-case
- **Main branch**: `main`
- **Target branch for PRs**: `dev` — open all pull requests against `dev`, not `main`. `main` is updated only via releases.
- **Python style**: ruff format (`[tool.ruff]` in pyproject.toml — line length 140, target `py314`, `migrations/` excluded)
- **Linting**: ruff (`[tool.ruff.lint]` — includes import sorting via `I`, so no separate isort step)

```bash
poetry run ruff check --fix .   # lint + autofix, includes import sorting
poetry run ruff format .        # format
```

Both run automatically via pre-commit (`.pre-commit-config.yaml`) and are enforced in CI by `codeql.yml`, which runs `ruff check .` and `ruff format --check .`.

```bash
poetry run pre-commit run --all-files
```

### Code style principles

- **No speculative code.** Don't add features, fallbacks, or abstractions beyond what the task requires. A bug fix doesn't need surrounding cleanup.
- **No defensive validation for impossibilities.** Only validate at system boundaries (user input, external APIs). Trust Django's ORM and framework guarantees internally.
- **Comments explain WHY, never WHAT.** Well-named identifiers already document what the code does. Add a comment only when there is a hidden constraint, a subtle invariant, or a known bug workaround. Remove any comment that restates the code.
- **Prefer editing existing files** to creating new ones. Don't duplicate logic; extend what already exists.
- **Errors must surface.** Never swallow exceptions silently (`except: pass`). Let Django's error handling and Celery's retry mechanisms propagate failures where they can be logged and acted upon.
- **Type hints on new public functions.** Python 3.14 supports full PEP 604 union types (`X | Y`). Use them.

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
| Add an admin view | the `admin.py` of the app concerned |
| Add an API endpoint | No API exists yet — see the API section before starting |
| Add a test | Mirror the files in `<app>/tests/` |
| Update config defaults | `governanceplatform/config_dev.py` |
| Change middleware order | `governanceplatform/settings.py` → `MIDDLEWARE` list |
| Add a Celery task | the `tasks.py` of the app concerned |
| Gate a feature per regulator | `governanceplatform/globals.py` → `FUNCTIONALITIES`, enforced in `middleware.py` |
| Change group permissions | `governanceplatform/permissions.py` → `GROUP_PERMISSIONS`, then run `manage.py update_group_permissions` |
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
- `codeql.yml` — static security analysis (Python + JavaScript), plus Django deploy checks, pip-audit, `ruff check`, `ruff format --check` and mypy
- `pythonapp.yml` — additional Python checks

**Never bypass CI.** If a check fails, fix the root cause — don't skip hooks (`--no-verify`) or force-push over a failing status. A green CI pipeline is the minimum bar for merging.
