Updating the application
========================

All you have to do is:

.. code-block:: bash

    $ cd SERIMA/
    $ ./contrib/update.sh {APP_TAG} {THEME_TAG}

Replace `{APP_TAG}` and `{THEME_TAG}` with the Git tag or branch you want to deploy for the application and theme respectively. If omitted, both default to `master`.

Or manually:

.. code-block:: bash

    $ cd SERIMA/
    $ git pull origin master --tags
    $ npm ci
    $ poetry install
    $ poetry run python manage.py collectstatic
    $ poetry run python manage.py migrate
    $ poetry run python manage.py compilemessages
    $ poetry run python manage.py update_group_permissions


Finally, restart Apache:

.. code-block:: bash

    $ sudo systemctl restart apache2.service
