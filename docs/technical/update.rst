Updating the application
========================

Manual installation
-------------------

The update script updates the application and the theme in one go:

.. code-block:: bash

    $ cd SERIMA/
    $ ./contrib/update.sh {APP_TAG} {THEME_TAG}

Replace ``{APP_TAG}`` and ``{THEME_TAG}`` with the Git tag or branch to deploy for the application and the theme;
both default to ``main``. Use matching versions of the two (see :doc:`installation`).

The script runs the same steps as this manual update:

.. code-block:: bash

    $ cd SERIMA/
    $ git fetch origin --tags
    $ git checkout {APP_TAG}
    $ npm ci
    $ poetry install --only main
    $ poetry run python manage.py collectstatic --noinput
    $ poetry run python manage.py migrate
    $ poetry run python manage.py compilemessages
    $ poetry run python manage.py update_group_permissions
    $ cd theme/
    $ git fetch origin --tags
    $ git checkout {THEME_TAG}

Then restart the web server and the background workers, so that they all run the new code:

.. code-block:: bash

    $ sudo systemctl restart apache2.service
    $ sudo systemctl restart serima-celery-worker serima-celery-beat

Use the names of your own services if you set them up differently.


Docker
------

Set the new versions, remove the theme volume and recreate the containers, as described in :doc:`docker`.
