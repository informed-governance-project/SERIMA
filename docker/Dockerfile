FROM node:24-bookworm-slim  AS npmbuilder

WORKDIR /app

COPY package.json package-lock.json /app/

RUN npm ci

FROM ubuntu:24.04

ARG APP_VERSION
ENV APP_VERSION=$APP_VERSION \
    DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="${PATH}:/var/www/.local/bin"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    # Python
    python3.12 \
    python3-pip \
    # LibreOffice — for document conversion
    python3-uno \
    libreoffice-writer \
    fonts-liberation \
    fonts-crosextra-carlito \
    fonts-crosextra-caladea \
    # WeasyPrint dependencies
    libpango-1.0-0 \
    libharfbuzz0b \
    libpangoft2-1.0-0 \
    libharfbuzz-subset0 \
    libffi-dev \
    libjpeg-dev \
    libopenjp2-7-dev \
    # Chrome runtime dependencies (required by kaleido v1 for static image export)
    libnss3 \
    libnspr4 \
    libatk1.0-0t64 \
    libatk-bridge2.0-0t64 \
    libcups2t64 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2t64 \
    # Other dependencies
    gettext \
    git \
  && rm -rf /var/lib/apt/lists/*

# Both python and python3 link to python3.12
RUN ln -sf /usr/bin/python3.12 /usr/bin/python3 \
 && ln -sf /usr/bin/python3.12 /usr/bin/python

# running as www-data
RUN mkdir -p /app /var/www && chown www-data: /app /var/www
USER www-data

# because package.json scripts.postinstall tries to be smart
COPY --chown=www-data --from=npmbuilder /app/node_modules /app/static/npm_components

COPY --chown=www-data governanceplatform /app/governanceplatform
COPY --chown=www-data incidents /app/incidents
COPY --chown=www-data securityobjectives /app/securityobjectives
COPY --chown=www-data reporting /app/reporting
COPY --chown=www-data locale /app/locale
COPY --chown=www-data static /app/static
COPY --chown=www-data templates /app/templates

COPY --chown=www-data pyproject.toml /app/pyproject.toml
COPY --chown=www-data README.md /app/README.md
COPY --chown=www-data README.md /app/LICENSE
COPY --chown=www-data manage.py /app/manage.py

RUN python -m pip install \
    --user \
    --break-system-packages \
    --no-cache-dir \
    .

RUN plotly_get_chrome -y

COPY celery_worker.py celery_beat.py docker/docker-init.sh /app/

RUN mkdir -p /app/tmp

ENTRYPOINT [ "/app/docker-init.sh" ]

ENV APP_PORT="8888" \
    APP_BIND_ADDRESS="0.0.0.0" \
    APP_WORKERS="4"

EXPOSE $APP_PORT
