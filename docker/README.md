# Install and run via Docker

Re-use the `docker/docker-compose.example.yml` and create the volumes directory
(see below)

## Database

See main README for configuration, the container is not started in host
network mode anymore and `postgres` is now part of `docker-compose.yml`.

## Volumes

> Please note that the container runs as user `www-data` (uid **33**), so at
> least the `theme` and, if used, `logs` volumes **need** to be owned by
> `www-data` (uid **33**)

There is now only one mandatory volumes to setup:

- `/app/governanceplatform/config.py`  
  The application configuration, based on `governanceplatform/config_dev.py`

The theme is now pulled from a docker image also, theme volume need to be
deleted before update, to ensure data is pulled again and the Django `collectstatic`
operation runs on fresh data. You can either delete the volume (`docker volume
rm`), or, if and only if, `theme` is your only docker-compose *named volume*, use
`docker-compose down -v && docker-compose up -d`. DO NOT use `docker-compose
down -v` if you put your postgres volume in a named volume instead of a host
path volume (`postgres:/var/lib/postgresql/data` vs
`./volumes/postgres/data:/var/lib/postgresql/data`)

## Logging configuration

If you want to use a pure stdout based logging (no `django.log` file), the
following configuration excerpt may be useful.

```
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "root": {"level": "INFO", "handlers": ["console"]},
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
            "formatter": "app",
        },
    },
    "formatters": {
        "app": {
            "format": (
                "[%(asctime)s] [%(levelname)-8s] (%(module)s.%(funcName)s) %(message)s"
            ),
            "datefmt": "%Y-%m-%d %H:%M:%S %z",
        },
    },
}
```

## Database configuration

To setup your `postgres` credentials in the Django application from environment
variables you may use the following piece of configuration (check
`docker-compose.yml` for example).

```
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "serima-governance"),
        "USER": os.getenv("POSTGRES_USER", "<user>"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "<password>"),
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": int(os.getenv("POSTGRES_PORT", 5432)),
    },
}
```

## Celery configuration

Celery broker can be configured in the config.py file with:

```
CELERY_BROKER_URL =  os.getenv("CELERY_BROKER_URL", 'redis://redis:6379/0')
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", 'redis://redis:6379/1')
```

## Startup scripts

Any `*.sh` script found under `/docker-init.d/` will be *sourced* before the
various static assets generation, Django migration etc ... this directory can
be exposed as a Docker volume also.

This allows application deployers to inject/fix anything they deem necessary
before the actual Django runtime init and application startup.

## Startup

`SERIMA_VERSION=vX.Y.Z SERIMA_ENVIRONMENT=prod docker-compose up -d`

- `SERIMA_VERSION` (required): which tag to deploy
- `SERIMA_IMAGE`: container image path (without version) (defaults to `ghcr.io/informed-governance-project/serima`)
- `SERIMA_ENVIRONMENT` (required): identifier for your environment, mainly for container naming
- `THEME_IMAGE`: theme container image path (without version) (defaults to `ghcr.io/informed-governance-project/default-theme`)
- `THEME_VERSION` (required): whith theme tag to deploy
- `POSTGRES_PASSWORD` (required): postgres db user password
- `POSTGRES_USER`: defaults to `governanceplatform`
- `POSTGRES_DB`: defaults to `governanceplatform`
- `POSTGRES_HOST`: defaults to `postgres`
- `CELERY_BROKER_URL`: defaults to 'redis://redis:6379/0'
- `CELERY_RESULT_BACKEND`: defaults to 'redis://redis:6379/1'
- `CELERY_CONCURRENCY`: defaults to `3`
- `KALEIDO_CONCURRENCY_PER_WORKER`: defaults to `1`
- `SUPERUSER_EMAIL` and `SUPERUSER_PASSWORD`: if *both* are set, Django initial
  superuser is created (password can be updated in Django WebUI afterwards),
  the initial creation is only performed if user does **not** already exist
- `MAIN_SITE` and `MAIN_SITE_NAME`: if *both* are set, Django initial site
  config is done on startup
- `APP_PORT`: which port to bind to (defaults to `8888`)
- `APP_BIND_ADDRESSS`: which address to bind to (defaults to `0.0.0.0`)

## Reverse proxy configuration

Static assets are handled by the Python `whitenoise` module that registers a handler to
serve static assets directly from the Python runtime.
