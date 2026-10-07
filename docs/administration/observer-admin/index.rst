Observer Admin
--------------

An observer is an organisation that receives, read-only, the incidents forwarded by the platform according to
the rules set by the platform administrator (see :ref:`platform-observers`). An observer administrator reads
those incidents in the incident notification module of the platform, and exports them when the platform administrator
allows it (see :doc:`/getting-started/roles-and-permissions`). In the administration console, they keep the details
of their observer up to date, connect it to an RT ticketing system, and create the other accounts of the observer.
The observer itself, the incidents it receives and its first administrator are set up by the platform administrator.

Open the console with **Settings** in the header of the platform (see :doc:`/administration/index`).

.. figure:: /_static/images/administration/observer-admin/index-01.png
   :alt: Site administration page of an observer administrator with the Governance section, the Recent actions panel and the Return to user interface link outlined
   :target: ../../_static/images/administration/observer-admin/index-01.png

The console has one section and a panel:

- **Governance**: your observer in **Observers** and its accounts in **Users**, see :doc:`governance`.
- **Recent actions**: your own latest actions, in the console and when you export incidents.

**Observers** shows only **View**, yet the form of your observer opens editable (see :ref:`observer-admin-observer`).
You cannot create or delete an observer.

.. note::

   The incident rules of your observer, which decide the incidents it receives, are not shown to you:
   the platform administrator manages them (see :ref:`platform-observers`).

.. tip::

   To give a colleague access to the platform, create their account in **Users** (see :ref:`observer-admin-users`),
   then make it an observer administrator (see :ref:`observer-admin-accounts`).
   They then choose a password and set up two-factor authentication themselves.

.. toctree::
   :maxdepth: 2
   :hidden:

   governance
