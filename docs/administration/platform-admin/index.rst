Platform Admin
--------------

The platform administrator sets up the platform for the regulators and observers that use it:
it creates the regulators and observers with their first administrators, the regulations, the operator categories,
and decides which modules are available.
Everything else, such as the incident notification workflows or the operators, is configured by the regulators
(see :doc:`/administration/regulator-admin/index`).

A platform administrator works only in the administration console. After logging in, you land on its home page,
**Site administration**; the homepage and the modules of the platform are not available to you,
and opening them takes you back to the console.
The header shows your account and its role, and the links at the top right let you manage your **Account security** (two-factor authentication), change your password,
log out and choose the language of the console.

.. figure:: /_static/images/administration/platform-admin/index-01.png
   :alt: Site administration page of a platform administrator with its Administration, Governance and Sites sections and the Recent actions panel outlined
   :target: ../../_static/images/administration/platform-admin/index-01.png

The console has three sections and a panel:

- **Administration**: the **Log entries**, see :doc:`administration`.
- **Governance**: the regulators, regulations, functionalities, entity categories, observers and users, and the settings
  of the server, see :doc:`governance`.
- **Sites**: the address and name of the platform, see `Sites`_ below.
- **Recent actions**: your own latest actions, logins included, each with a link to the object concerned.

The first platform administrator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The first platform administrator is created on the server, during the installation, with the ``createsuperuser``
command (see :doc:`/technical/installation`) or, with Docker, the ``SUPERUSER_EMAIL`` and ``SUPERUSER_PASSWORD``
variables (see :doc:`/technical/docker`).

.. note::

   Despite its name, ``createsuperuser`` creates a platform administrator, not a Django superuser:
   superusers cannot use the platform at all.

This first account then creates the other platform administrators from the console (see :ref:`platform-users`).

Set up the platform
~~~~~~~~~~~~~~~~~~~

After the installation, set up the platform in this order, since each step uses what the previous ones created:

1. Set the address and name of the platform in `Sites`_.
2. Create each regulator with its first regulator administrator (see :ref:`platform-regulators`).
3. Create the regulations and assign each to the regulators in charge of it (see :ref:`platform-regulations`).
4. Open the optional modules to the roles and regulators that will use them (see :ref:`functionalities`).
5. Create the entity categories that classify the operators (see :ref:`platform-entity-categories`).
6. Create each observer with its first observer administrator, and the rules deciding which incidents it receives
   (see :ref:`platform-observers`).

The regulator administrators then configure their regulations, workflows and operators,
as described in :doc:`/administration/regulator-admin/index`.

.. _platform-sites:

Sites
~~~~~

**Sites** holds the address of the platform. The platform uses it to build the links of the emails it sends,
such as the link to choose a password, and to name the platform in authenticator apps when users set up
two-factor authentication.

1. Click **Sites**, then the only site in the list.
2. Enter the address of the platform, without ``https://``, in **Domain name**, and the name of the platform in **Display name**.
3. Click **Save**.

.. figure:: /_static/images/administration/platform-admin/index-02.png
   :alt: Change site form with the Domain name and Display name fields
   :target: ../../_static/images/administration/platform-admin/index-02.png

.. important::

   The site is created with the address ``example.com``: until you change it, the links in the emails
   do not lead to your platform.

With Docker, the ``MAIN_SITE`` and ``MAIN_SITE_NAME`` variables set both fields at startup (see :doc:`/technical/docker`).

.. toctree::
   :maxdepth: 2
   :hidden:

   administration
   governance
