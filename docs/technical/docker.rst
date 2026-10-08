Docker
======

The official images contain the application with all its system dependencies
(Python 3.14, LibreOffice, the WeasyPrint libraries and the Chromium used by Kaleido),
so the server only needs Docker and Docker Compose.

Images
------

Both are published on the GitHub container registry, with one tag per release:

- the application: ``ghcr.io/informed-governance-project/serima``;
- the theme: ``ghcr.io/informed-governance-project/default-theme``
  (or ``serimabe-theme``; see :doc:`installation` for the themes).

Deploy the same release of both.


Services
--------

``docker/docker-compose.example.yml`` defines the whole stack:

.. list-table::
   :header-rows: 1
   :widths: 18 82

   * - Service
     - Role
   * - ``web``
     - The application, served by Gunicorn on port 8888. At each start it runs ``collectstatic``,
       ``migrate``, ``compilemessages`` and ``update_group_permissions``.
   * - ``celery-worker``
     - Generates reports and security objectives exports and imports, and runs the scheduled tasks.
   * - ``celery-beat``
     - Triggers the scheduled tasks (see :doc:`installation`).
   * - ``db``
     - PostgreSQL 18.
   * - ``redis``
     - Redis, the broker between the application and the workers.
   * - ``theme``
     - Copies the theme into the shared ``theme`` volume, then stops.

The application containers run as ``www-data`` (uid **33**).


Set up
------

Create a directory for the deployment, with the compose file and the configuration:

.. code-block:: bash

    $ mkdir -p serima/volumes/config && cd serima
    $ curl -o docker-compose.yml https://raw.githubusercontent.com/informed-governance-project/SERIMA/main/docker/docker-compose.example.yml
    $ curl -o volumes/config/config.py https://raw.githubusercontent.com/informed-governance-project/SERIMA/main/governanceplatform/config_dev.py

Edit ``volumes/config/config.py`` as described in :ref:`configuration`. Inside the containers,
read the database and broker settings from the environment that the compose file provides:

.. code-block:: python

    import os

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB", "governanceplatform"),
            "USER": os.getenv("POSTGRES_USER", "governanceplatform"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD"),
            "HOST": os.getenv("POSTGRES_HOST", "db"),
            "PORT": int(os.getenv("POSTGRES_PORT", 5432)),
        },
    }

    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")

``POSTGRES_HOST`` must be the name of the database service, ``db`` in the example compose file.

Volumes owned by the application, such as ``theme`` and a ``logs`` directory if you write log files,
must belong to uid 33.


Start
-----

.. code-block:: bash

    $ SERIMA_VERSION=vX.Y.Z THEME_VERSION=vX.Y.Z SERIMA_ENVIRONMENT=prod POSTGRES_PASSWORD=<password> docker compose up -d

Put the variables in a ``.env`` file next to ``docker-compose.yml`` rather than on the command line.

.. list-table::
   :header-rows: 1
   :widths: 32 14 54

   * - Variable
     - Required
     - Meaning
   * - ``SERIMA_VERSION``
     - Yes
     - Tag of the application image to deploy.
   * - ``THEME_VERSION``
     - Yes
     - Tag of the theme image to deploy.
   * - ``SERIMA_ENVIRONMENT``
     - Yes
     - Name of the environment, used in the container names (``prod``, ``staging``…).
   * - ``POSTGRES_PASSWORD``
     - Yes
     - Password of the database user.
   * - ``SERIMA_IMAGE`` / ``THEME_IMAGE``
     - No
     - Image paths without the tag; default to the official images.
   * - ``POSTGRES_USER`` / ``POSTGRES_DB``
     - No
     - Database user and name; default to ``governanceplatform``.
   * - ``POSTGRES_HOST``
     - No
     - Host of the database; the name of the database service.
   * - ``CELERY_BROKER_URL`` / ``CELERY_RESULT_BACKEND``
     - No
     - Redis databases; default to ``redis://redis:6379/0`` and ``/1``.
   * - ``CELERY_CONCURRENCY``
     - No
     - Tasks a worker runs in parallel (default 3).
   * - ``KALEIDO_CONCURRENCY_PER_WORKER``
     - No
     - Charts a worker renders at once (default 1).
   * - ``APP_PORT``
     - No
     - Port the application is published on (default 8888).
   * - ``APP_BIND_ADDRESS`` / ``APP_WORKERS``
     - No
     - Address Gunicorn binds to (default ``0.0.0.0``) and its number of workers (default 4).
   * - ``SUPERUSER_EMAIL`` / ``SUPERUSER_PASSWORD``
     - No
     - If both are set, creates the first platform administrator at startup, unless that email already exists.
   * - ``MAIN_SITE`` / ``MAIN_SITE_NAME``
     - No
     - If both are set, sets the domain name and display name of the site at startup.

``SUPERUSER_EMAIL`` creates a platform administrator, not a Django superuser, exactly like ``createsuperuser``
(see :doc:`installation`). ``MAIN_SITE`` and ``MAIN_SITE_NAME`` replace the manual **Sites** configuration.

Follow the start with ``docker compose logs -f web``.


Reverse proxy
-------------

Publish the application through a reverse proxy that terminates HTTPS and forwards to port 8888.
Static files are served by the application (WhiteNoise), so the proxy forwards everything:

.. code-block:: apacheconf

    <VirtualHost *:443>
        ServerName incidents.example.org

        ProxyPreserveHost On
        RequestHeader set X-Forwarded-Proto "https"
        ProxyPass / http://localhost:8888/ retry=1
        ProxyPassReverse / http://localhost:8888/

        SSLEngine on
        SSLCertificateFile /etc/letsencrypt/live/incidents.example.org/fullchain.pem
        SSLCertificateKeyFile /etc/letsencrypt/live/incidents.example.org/privkey.pem
    </VirtualHost>

Add the public address to ``ALLOWED_HOSTS`` and ``CSRF_TRUSTED_ORIGINS`` in the configuration.


Startup scripts
---------------

Every ``*.sh`` file in ``/docker-init.d/`` is sourced before the application starts, before ``migrate``
and the other start-up steps. Mount a directory there to adjust anything the deployment needs:

.. code-block:: yaml

    services:
      web:
        volumes:
          - ./volumes/docker-init.d:/docker-init.d


Logging
-------

To log to the container output instead of a ``django.log`` file, use a console handler in ``config.py``;
an example is in the `Docker README <https://github.com/informed-governance-project/SERIMA/blob/main/docker/README.md>`_.


Update
------

1. Set ``SERIMA_VERSION`` and ``THEME_VERSION`` to the new release.
2. Remove the ``theme`` volume, so that the new theme is copied in and ``collectstatic`` runs on it:
   ``docker volume rm <project>_theme``.
3. Recreate the containers: ``docker compose up -d``.

The ``web`` container runs the migrations and ``update_group_permissions`` by itself at start-up.

.. warning::

    Do not use ``docker compose down -v`` to remove the theme volume if PostgreSQL stores its data in a
    named volume: it would delete the database as well. The example compose file keeps the database in a
    host directory (``./volumes/postgres``), which ``down -v`` does not touch.


Build the image yourself
------------------------

From a checkout of the repository:

.. code-block:: bash

    $ make image

or ``docker build -f docker/Dockerfile -t serima:local .``
