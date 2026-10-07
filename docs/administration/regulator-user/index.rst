Regulator User
--------------

A regulator user reviews, in the modules of the platform, the incidents and security objectives declarations
of the sectors assigned to it (see :doc:`/getting-started/roles-and-permissions`). In the administration console,
it creates the operators its regulator supervises and their accounts, starting with their first operator administrator.
The regulator itself, its accounts, the sectors and the incident notification workflows are set up by the regulator
administrator (see :doc:`/administration/regulator-admin/index`).

Click **Settings** in the header of the platform to open the console on its home page, **Site administration**.
Click **Return to user interface** at the top right to go back to the platform. The other links at the top right
manage your **Account security** (two-factor authentication) and your password, log you out and choose the language
of the console.

.. figure:: /_static/images/administration/regulator-user/index-01.png
   :alt: Site administration page of a regulator user with the Governance section, the Recent actions panel and the Return to user interface link outlined
   :target: ../../_static/images/administration/regulator-user/index-01.png

The console has one section and a panel:

- **Governance**: the **Operators** and their accounts, and the **Users**, see :doc:`governance`.
- **Recent actions**: your own latest actions, logins included. Each one, except deletions,
  links to the object concerned.

Each item of a section shows **View** when you can only read it, and **Add** and **Change** when you can edit it.
**Users** shows **View**, as you can change only some of the accounts it lists (see :ref:`regulator-user-users`).
The lists and forms work as described in :doc:`/administration/platform-admin/governance`.

.. note::

   The console holds no log entries and none of the configuration of the modules for a regulator user:
   the regulator administrator manages them.

.. tip::

   To set up a new operator:

   1. Create the account of its first operator administrator, if it does not exist yet (see :ref:`regulator-user-users`).
   2. Create the operator with that account as its administrator (see :ref:`regulator-user-operators`).
   3. The operator administrator then creates the other accounts of the operator
      (see :doc:`/administration/operator-admin`), or you add them to the operator yourself
      (see :ref:`regulator-user-contacts`).

.. toctree::
   :maxdepth: 2
   :hidden:

   governance
