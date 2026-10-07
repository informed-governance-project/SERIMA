Administration
==============

The administration console is where the platform, the regulators and the operators are set up and their accounts managed.
What you can do in it depends on your role:

- **Platform Admin**: sets up the platform itself, its regulators, regulations, modules and observers
  (see :doc:`platform-admin/index`).
- **Regulator Admin**: sets up their regulator, its accounts, sectors and operators, and the configuration
  of the modules (see :doc:`regulator-admin/index`).
- **Regulator User**: creates the operators their regulator supervises and the accounts of those operators
  (see :doc:`regulator-user/index`).
- **Operator Admin**: manages the accounts of their operator (see :doc:`operator-admin/index`).
- **Observer Admin**: manages the details and accounts of their observer. This guide does not cover it yet.

.. note::

   Operator users, incident users and observer users have no access to the console: the **Settings** link
   is not shown to them. What each role can do is summarised in :doc:`/getting-started/roles-and-permissions`.

Click **Settings** in the header of the platform to open the console on its home page, **Site administration**,
and **Return to user interface** at the top right to go back to the platform. The other links at the top right
manage your **Account security** (two-factor authentication) and your password, log you out and choose the language
of the console. A platform administrator has no user interface: the console opens directly after logging in.

The home page lists the sections of the console you can use. Each item of a section shows **View** when you can only
read it, and **Add** and **Change** when you can edit it. The lists and forms work the same way everywhere,
as described in :doc:`platform-admin/governance`.

.. toctree::
   :maxdepth: 2
   :hidden:

   platform-admin/index
   regulator-admin/index
   regulator-user/index
   operator-admin/index
