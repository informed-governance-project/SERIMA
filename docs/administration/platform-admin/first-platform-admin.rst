The first platform administrator
--------------------------------

The first platform administrator is created on the server, during the installation, with the ``createsuperuser``
command (see :doc:`/technical/installation`) or, with Docker, the ``SUPERUSER_EMAIL`` and ``SUPERUSER_PASSWORD``
variables (see :doc:`/technical/docker`).

.. note::

   Despite its name, ``createsuperuser`` creates a platform administrator, not a Django superuser:
   superusers cannot use the platform at all.

This first account then creates the other platform administrators from the console (see :ref:`platform-users`).
