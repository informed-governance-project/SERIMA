#!/bin/bash


debug="${DEBUG:-false}"
component="${1:-app}"

SUPERUSER_EMAIL="${SUPERUSER_EMAIL:-}"
SUPERUSER_PASSWORD="${SUPERUSER_PASSWORD:-}"
MAIN_SITE="${MAIN_SITE:-}"
MAIN_SITE_NAME="${MAIN_SITE_NAME:-}"
CELERY_CONCURRENCY="${CELERY_CONCURRENCY:-3}"
# Comma-separated queues this worker consumes; empty means all of them.
CELERY_QUEUES="${CELERY_QUEUES:-}"

set -euo pipefail

if [ "$debug" != "false" ]; then
    echo $debug
    pwd
    set -x
fi

docker_init_d=/docker-init.d
if [ -d $docker_init_d -a $docker_init_d/*.sh != "${docker_init_d}/*.sh" ]; then
    for f in $docker_init_d/*.sh; do
        source "$f"
    done
fi


case "$component" in
    app)
        mkdir -p /app/theme/static

        python manage.py collectstatic --noinput > /dev/null
        python manage.py migrate
        python manage.py compilemessages
        python manage.py update_group_permissions

        if [ "$SUPERUSER_EMAIL" -a "$SUPERUSER_PASSWORD" ]; then
            echo >&2 "INFO: setting $SUPERUSER_EMAIL as superuser"
            python manage.py shell --interface python <<END
from governanceplatform import models
if not User.objects.filter(email='${SUPERUSER_EMAIL}'):
    u = User.objects.create_superuser('${SUPERUSER_EMAIL}', '${SUPERUSER_PASSWORD}')
END
        fi

        if [ "$MAIN_SITE" -a "$MAIN_SITE_NAME" ]; then
            echo >&2 "INFO: setting $MAIN_SITE ($MAIN_SITE_NAME) as django_site information"
            python manage.py shell --interface python <<END
from django.contrib.sites.models import Site
site = Site.objects.all()[0]
site.domain = "${MAIN_SITE}"
site.name = "${MAIN_SITE_NAME}"
site.save()
END
        fi

        exec gunicorn governanceplatform.wsgi --workers "$APP_WORKERS" --bind "$APP_BIND_ADDRESS:$APP_PORT"
        ;;
    worker)
        exec celery -A celery_worker worker ${CELERY_QUEUES:+-Q "$CELERY_QUEUES"} --concurrency=$CELERY_CONCURRENCY --loglevel=info
        ;;
    beat)
        exec celery -A celery_beat beat --loglevel=info
        ;;
    *)
        echo >&2 "unknown component in entrypoint $(basename $0)"
        exit 1
        ;;
esac
