Governance
----------

The **Governance** section of the console is where you create the operators and their accounts.
For a regulator user, it lists:

- **Operators**, which you can add and change, see `Operators`_ and `Operator accounts`_;
- **Users**, where you can add accounts and change those of the operators, see `Users`_.

The lists, forms and the icons beside the drop-downs work as described in
:doc:`/administration/platform-admin/governance`.

.. _regulator-user-operators:

Operators
~~~~~~~~~

The **Operators** list shows the **Acronym**, **Name**, **Address**, **Country**, **Email address** and **Phone number**
of each operator. Operators are shared by every regulator of the platform, so the list holds them all.

.. figure:: /_static/images/administration/regulator-user/governance-01.png
   :alt: Operators list with Operators selected in the sidebar and the column headers outlined
   :target: ../../_static/images/administration/regulator-user/governance-01.png

To create an operator, click **Add Operator** and fill in its **Contact information**, **Configuration information**,
**Entity categories** and **Sectors**, as described in :ref:`regulator-operators`. Then add its first operator
administrator in the **Contacts for company** section at the bottom of the form (see `Operator accounts`_),
and click **Save**.

.. figure:: /_static/images/administration/regulator-user/governance-02.png
   :alt: Change Operator form with its contact information, acronym, entity categories, sectors and the Contacts for company section outlined
   :target: ../../_static/images/administration/regulator-user/governance-02.png

Click an operator in the list to change it the same way.

.. note::

   You cannot delete an operator.

.. _regulator-user-contacts:

Operator accounts
~~~~~~~~~~~~~~~~~

The **Contacts for company** section at the bottom of the form of an operator lists its accounts, one row each.

.. figure:: /_static/images/administration/regulator-user/governance-03.png
   :alt: Contacts for company section with the row of an operator administrator, the plus icon beside the User drop-down and the Add another Contact for company link outlined
   :target: ../../_static/images/administration/regulator-user/governance-03.png

Each row has:

- **User**: the account. The drop-down lists the active accounts that belong to no regulator and no observer:
  the operator administrators and users of every operator, and the incident users.
- **Is administrator**: ticked for an operator administrator, unticked for an operator user.
  Changing it switches the role of the account and logs it out.
- **Approved**: whether the account is linked to the operator. The platform sets it when you save,
  and it is read-only once the operator has an administrator (see `Incident user accounts`_).
- **Delete?**: removes the account from the operator.

Add an account
""""""""""""""

1. Click **Add another Contact for company**.
2. Select the account in the **User** drop-down, or click the plus icon beside it to create the account in a pop-up,
   with its **First name**, **Last name**, **Email address** and **Phone number**.
3. Tick **Is administrator** to make it an operator administrator.
4. Click **Save**.

A new account has no password yet. Its owner chooses one with **Password forgotten?** on the login page
(see :doc:`/getting-started/login`), then sets up two-factor authentication at the first login
(see :doc:`/getting-started/enable-2fa`).

.. important::

   An operator must always have an administrator: the form is not saved otherwise. While an operator has
   no administrator yet, its first account must be one, so create a new operator with its administrator only,
   save it, then add its other accounts.

Incident user accounts
""""""""""""""""""""""

An incident user account you add to an operator that already has an administrator is not linked straight away.
Unless the account already belongs to another operator, the platform emails a suggestion to link it
to the operator's email address and to its administrators. An operator administrator approves or rejects the link (see :doc:`/administration/operator-admin`).
Until then, the account keeps the incident user role, and it cannot be made an administrator.

When the operator has no administrator yet, the account is linked as soon as you save.

Remove an account
"""""""""""""""""

Tick **Delete?** on the row of the account and click **Save**. The account is logged out and loses access
to the operator. An account left without any operator is deactivated.

.. _regulator-user-users:

Users
~~~~~

The **Users** list shows your own account, the other regulator users of your regulator, and the accounts of the
operators and the incident users. To narrow it down, choose an operator in **By Operators** or a role in **By Roles**
in the **Filter** panel, or search for a name.

The list shows the contact details of each account, its **Companies** (operators), its **Roles**,
whether the email address is verified and two-factor authentication is activated, and when the account was created.

.. figure:: /_static/images/administration/regulator-user/governance-04.png
   :alt: Users list of a regulator user with the column headers and the Filter panel outlined
   :target: ../../_static/images/administration/regulator-user/governance-04.png

Create an account
"""""""""""""""""

Click **Add User**, enter the **First name**, **Last name**, **Email address** and **Phone number** of the account,
and click **Save**. The account is created as an operator user attached to no operator: add it to its operator
in the **Contacts for company** section of the operator (see `Operator accounts`_).

Change an account
"""""""""""""""""

Click a name to open the account. For an operator or incident user account, you can change its contact details
and untick **Active** to deactivate it: its owner can no longer log in. Its **Roles**, **Date joined**,
**Email verified** and **2FA Activated** are read-only, and its operators are changed in the form of the operator.

.. figure:: /_static/images/administration/regulator-user/governance-05.png
   :alt: Change User form of an operator user with the Active box and the Reset 2FA token button outlined
   :target: ../../_static/images/administration/regulator-user/governance-05.png

You can also change the contact details of your own account. The other accounts of your regulator open read-only:
the regulator administrator manages them (see :ref:`regulator-accounts`).

.. note::

   You cannot delete an account. Untick **Active** instead.

Reset two-factor authentication
"""""""""""""""""""""""""""""""

You can reset the two-factor authentication of the operator and incident user accounts, with the **Reset 2FA token**
button or the **Reset 2FA** action, as described in :ref:`platform-users`. You cannot reset it for regulator accounts,
nor for your own: use **Account security** at the top of the console.
