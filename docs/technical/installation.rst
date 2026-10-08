Installation
============

There are two ways to install SERIMA:

- **Docker**: the official images bundle the application and its system dependencies. See :doc:`docker`.
- **Manual installation** on a GNU/Linux server, described below.

The rest of this page covers the manual installation. The configuration, the first platform administrator
and the background workers apply to both.


System packages
---------------

On Ubuntu 26.04 LTS, the same packages as the official Docker image:

.. code-block:: bash

    $ sudo apt install \
        git curl gettext postfix postgresql redis-server \
        python3.14 python3-venv \
        nodejs npm \
        libreoffice-writer python3-uno \
        fonts-liberation fonts-crosextra-carlito fonts-crosextra-caladea \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libharfbuzz-subset0 \
        libffi-dev libjpeg-dev libopenjp2-7-dev \
        libnss3 libnspr4 libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 libdrm2 \
        libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2t64

What each group is for:

- ``git``, ``curl``, ``gettext``, ``postfix``, ``postgresql``, ``redis-server``: getting the code,
  compiling the translations, sending emails, the database and the broker of the background workers;
- ``python3.14``, ``python3-venv``: the interpreter, and the ``venv`` module the Poetry installer needs;
- ``nodejs``, ``npm``: the front-end assets. Check that they are version 24 and 11 (``node --version``,
  ``npm --version``); install them from NodeSource if your distribution provides older ones;
- ``libreoffice-writer``, ``python3-uno`` and the fonts: the reporting module uses LibreOffice to update
  the table of contents of the generated DOCX reports and to convert them to PDF;
  the fonts keep the documents' layout faithful;
- the ``libpango``/``libharfbuzz`` libraries and ``libffi-dev``, ``libjpeg-dev``, ``libopenjp2-7-dev``:
  PDF rendering with WeasyPrint and its image support;
- the remaining libraries (``libnss3`` to ``libasound2t64``): the Chrome that Kaleido drives to render
  the report charts, installed in the next section.

The ``t64`` package names are those of Ubuntu 24.04 and later; on older distributions, drop the suffix.


Poetry
------

.. code-block:: bash

    $ curl -sSL https://install.python-poetry.org | python3 -

Then add Poetry to your ``PATH``, at the end of ``~/.bashrc``:

.. code-block:: bash

    export PATH="$HOME/.local/bin:$PATH"


PostgreSQL
----------

Create a database user and a database owned by it:

.. code-block:: bash

    $ sudo -u postgres createuser <username>
    $ sudo -u postgres createdb --owner=<username> <database>
    $ sudo -u postgres psql -c "ALTER USER <username> WITH ENCRYPTED PASSWORD '<password>';"


SERIMA
------

.. code-block:: bash

    $ git clone https://github.com/informed-governance-project/SERIMA.git
    $ cd SERIMA
    $ git clone https://github.com/informed-governance-project/default-theme.git theme
    $ npm ci
    $ cp governanceplatform/config_dev.py governanceplatform/config.py   # then edit it, see below
    $ poetry install --only main
    $ poetry run plotly_get_chrome -y
    $ poetry run python manage.py migrate
    $ poetry run python manage.py update_group_permissions
    $ poetry run python manage.py collectstatic
    $ poetry run python manage.py compilemessages

``plotly_get_chrome`` downloads the Chrome that Kaleido uses to render the report charts, for the current user:
run it as the user the Celery worker runs as.
``update_group_permissions`` creates the user groups (roles) and their permissions; run it again after every update.


Theme
`````

The interface (templates, styles, icons and their translations) lives in a separate Git repository,
cloned into the ``theme`` folder. That folder is ignored by the main repository: update it from inside it.
Two themes are available:

- https://github.com/informed-governance-project/default-theme — the default theme;
- https://github.com/informed-governance-project/serimabe-theme — the theme of the Belgian instance (IBPT).

Check out a theme version that matches the application version: a tag of the same release,
or the matching branch (``main`` with ``main``, ``dev`` with ``dev``).


.. _configuration:

Configuration
`````````````

All settings live in ``governanceplatform/config.py``, which is not part of the repository.
Start from ``governanceplatform/config_dev.py`` and set at least:

- ``SECRET_KEY`` and ``HASH_KEY`` — **your own** keys, see below;
- ``DEBUG`` — ``False`` in production;
- ``PUBLIC_URL``, ``ALLOWED_HOSTS`` and, behind a reverse proxy, ``CSRF_TRUSTED_ORIGINS``;
- ``SITE_NAME`` and ``REGULATOR_CONTACT``;
- ``DATABASES``;
- ``EMAIL_HOST``, ``EMAIL_PORT``, ``EMAIL_SENDER``, and ``EMAIL_FOR_CONTACT`` / ``EMAIL_CONTACT_FROM`` for the contact form;
- ``CELERY_BROKER_URL`` and ``CELERY_RESULT_BACKEND`` — the Redis server;
- ``COOKIEBANNER``;
- ``MAX_PRELIMINARY_NOTIFICATION_PER_DAY_PER_USER``;
- ``LANGUAGES``, ``PARLER_LANGUAGES`` and ``PARLER_DEFAULT_LANGUAGE_CODE``.

``API_ENABLED`` must be present but has no effect: SERIMA has no API yet.

These settings are optional; the application applies a default when they are missing:

- ``PATH_FOR_REPORTING_PDF`` — where generated reports and import/export files are written;
- ``KALEIDO_CONCURRENCY_PER_WORKER`` — how many charts a Celery worker renders at once (default 1);
- ``INCIDENT_RETENTION_TIME_IN_DAY`` and ``SECURITY_OBJECTIVE_RETENTION_TIME_IN_DAY`` — how long incidents
  and security objectives declarations are kept (default 1825 days, five years);
- ``LOG_RETENTION_TIME_IN_DAY`` — how long log entries are kept;
- ``DAY_BEFORE_DELETING_INC_USER_WITHOUT_INCIDENT`` — after how many days without logging in an incident user
  account that never reported an incident is deleted (default 90);
- ``TERMS_ACCEPTANCE_TIME_IN_DAYS`` — after how many days users must accept the terms of service again (default 365);
- ``SESSION_COOKIE_AGE`` — after how many seconds of inactivity users are logged out;
- ``RT_SECRET_KEY`` — the key encrypting observers' RT tokens (defaults to ``HASH_KEY``).

When ``DEBUG`` is ``True``, emails are not sent but written to the ``sent_emails`` folder at the root of the project.

Generate the Fernet key (``HASH_KEY``):

.. code-block:: bash

    $ python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'

And the Django secret key (``SECRET_KEY``):

.. code-block:: bash

    $ python3 -c 'import secrets; print(secrets.token_hex())'


Create the first platform administrator
---------------------------------------

.. code-block:: bash

    $ poetry run python manage.py createsuperuser

Despite its name, in SERIMA this command creates a platform administrator, not a Django superuser
(superusers cannot use the platform). This account then creates the regulators, their first administrators
and the rest of the set-up, as described in :doc:`/administration/platform-admin/index`.

Its first task is to set the domain name and display name of the platform in **Sites**
(see :ref:`platform-sites`): until then, the links in the emails, such as password recovery,
do not lead to your platform, and authenticator apps do not show its name.


Background workers
------------------

Two Celery processes must run alongside the web application, both connected to Redis:

- the **worker**, which generates the reports and the security objectives exports and imports,
  and runs the scheduled tasks;
- **beat**, which triggers the scheduled tasks.

.. code-block:: bash

    $ poetry run celery -A celery_worker worker --loglevel=info
    $ poetry run celery -A celery_beat beat --loglevel=info

Run them as services, for instance with systemd:

.. code-block:: ini

    # /etc/systemd/system/serima-celery-worker.service
    [Unit]
    Description=SERIMA Celery worker
    After=network.target redis-server.service postgresql.service

    [Service]
    User=<user>
    WorkingDirectory=/home/<user>/SERIMA
    ExecStart=/home/<user>/.local/bin/poetry run celery -A celery_worker worker --loglevel=info
    Restart=always

    [Install]
    WantedBy=multi-user.target

Create ``serima-celery-beat.service`` the same way, with ``celery -A celery_beat beat``,
then enable both with ``sudo systemctl enable --now serima-celery-worker serima-celery-beat``.

Celery beat triggers these tasks (times in the server's time zone):

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Task
     - When
     - What it does
   * - ``email_reminder``
     - Every hour
     - Sends the reminders configured on the incident workflows.
   * - ``workflow_update_status``
     - Every hour
     - For ongoing incidents, sends the workflow's "report status changed" email when an unsubmitted report
       reaches the configured delay past its deadline.
   * - ``incident_cleaning``
     - Daily, 20:30
     - Deletes incidents older than ``INCIDENT_RETENTION_TIME_IN_DAY``.
   * - ``log_cleaning``
     - Daily, 21:00
     - Deletes log entries older than ``LOG_RETENTION_TIME_IN_DAY``.
   * - ``unactive_account_cleaning``
     - Daily, 22:00
     - Deletes incident user accounts that were never activated, once their set-password link has expired.
   * - ``clean_incident_user``
     - Daily, 23:00
     - Deletes incident user accounts that never reported an incident, after
       ``DAY_BEFORE_DELETING_INC_USER_WITHOUT_INCIDENT`` days (default 90) without logging in.
   * - ``so_declarations_cleaning``
     - Daily, 23:30
     - Deletes security objectives declarations older than ``SECURITY_OBJECTIVE_RETENTION_TIME_IN_DAY``.

No cron job is needed.


Try it locally
--------------

.. code-block:: bash

    $ poetry run python manage.py runserver 127.0.0.1:8000

The development server is for local testing only; never use it in production.


Production web server
---------------------

Serve the application with Gunicorn behind a reverse proxy, as the Docker image does:

.. code-block:: bash

    $ poetry run gunicorn governanceplatform.wsgi --workers 4 --bind 127.0.0.1:8000

or with Apache and ``mod_wsgi``, described below. For the next steps you need a valid domain name.


Apache with mod_wsgi
````````````````````

.. code-block:: bash

    $ sudo apt install apache2 libapache2-mod-wsgi-py3

``libapache2-mod-wsgi-py3`` is built against the distribution's Python; on Ubuntu 26.04 LTS that is Python 3.14.
On a distribution with an older Python, build ``mod_wsgi`` against Python 3.14 instead (``pip install mod_wsgi``).

Find the virtual environment Poetry created:

.. code-block:: bash

    $ poetry env info --path


Example of VirtualHost configuration files
``````````````````````````````````````````

Reverse proxy, terminating HTTPS:

.. code-block:: apacheconf

    <VirtualHost *:80>
        ServerName incidents.example.org
        RewriteEngine on
        RewriteRule ^ https://%{SERVER_NAME}%{REQUEST_URI} [END,NE,R=permanent]
    </VirtualHost>

    <VirtualHost *:443>
        ServerName incidents.example.org

        RewriteEngine On
        RewriteCond %{REQUEST_METHOD} !^(GET|POST|PUT|PATCH|DELETE|HEAD)
        RewriteRule .* - [R=405,L]

        ProxyPreserveHost On
        ProxyTimeout 1800
        RequestHeader set X-Forwarded-Proto "https"

        SSLEngine on
        SSLCertificateFile /etc/letsencrypt/live/incidents.example.org/fullchain.pem
        SSLCertificateKeyFile /etc/letsencrypt/live/incidents.example.org/privkey.pem

        ProxyPass / http://app.internal.example.org/
        ProxyPassReverse / http://app.internal.example.org/

        CustomLog ${APACHE_LOG_DIR}/incidents_access.log combined
        ErrorLog ${APACHE_LOG_DIR}/incidents_error.log
    </VirtualHost>

To obtain the certificate with Let's Encrypt:

.. code-block:: bash

    $ sudo apt install certbot python3-certbot-apache
    $ sudo certbot certonly --apache -d incidents.example.org
    $ sudo a2enmod ssl rewrite proxy proxy_http headers
    $ sudo systemctl restart apache2.service

The application, with ``mod_wsgi``:

.. code-block:: apacheconf

    <VirtualHost *:80>
        ServerName app.internal.example.org

        WSGIDaemonProcess serima python-home=<virtualenv-path> python-path=/home/<user>/SERIMA
        WSGIProcessGroup serima
        WSGIApplicationGroup %{GLOBAL}
        WSGIScriptAlias / /home/<user>/SERIMA/governanceplatform/wsgi.py

        <Directory /home/<user>/SERIMA/governanceplatform>
            <Files wsgi.py>
                Require all granted
            </Files>
        </Directory>

        LogLevel warn
        CustomLog ${APACHE_LOG_DIR}/serima_access.log combined
        ErrorLog ${APACHE_LOG_DIR}/serima_error.log
    </VirtualHost>

Static files are served by the application (WhiteNoise), so no ``Alias /static`` is needed.
