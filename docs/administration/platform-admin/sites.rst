.. _platform-sites:

Sites
-----

**Sites** holds the address of the platform. The platform uses it to build the links of the emails it sends,
such as the link to choose a password, and to name the platform in authenticator apps when users set up
two-factor authentication.

1. Click **Sites**, then the only site in the list.
2. Enter the address of the platform, without ``https://``, in **Domain name**, and the name of the platform in **Display name**.
3. Click **Save**.

.. figure:: /_static/images/administration/platform-admin/sites-01.png
   :alt: Change site form with the Domain name and Display name fields
   :target: ../../_static/images/administration/platform-admin/sites-01.png

.. important::

   The site is created with the address ``example.com``: until you change it, the links in the emails
   do not lead to your platform.

With Docker, the ``MAIN_SITE`` and ``MAIN_SITE_NAME`` variables set both fields at startup (see :doc:`/technical/docker`).
