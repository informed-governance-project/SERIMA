Governance
----------

The **Governance** section of the console is where you manage your operator and its accounts.
For an operator administrator, it lists:

- **Operators**, which you can change, see `Your operator`_;
- **Users**, where you add and change the accounts of your operator, see `Users`_.

The lists and forms work as described in :doc:`/administration/platform-admin/governance`.

Your operator
~~~~~~~~~~~~~

The **Operators** list shows only the operator you are working for, with its **Acronym**, **Name**, **Address**,
**Country**, **Email address** and **Phone number**.

.. figure:: /_static/images/administration/operator-admin/governance-01.png
   :alt: Operators list with Operators selected in the sidebar and the column headers outlined
   :target: ../../_static/images/administration/operator-admin/governance-01.png

Click its acronym to open it. You can change its **Email address** and **Phone number**, then click **Save**.
Its name, address, country, acronym, entity categories and sectors are read-only: the regulator manages them
(see :ref:`regulator-user-operators`).

.. figure:: /_static/images/administration/operator-admin/governance-02.png
   :alt: Change Operator form with the editable Email address and Phone number fields outlined, the other fields read-only
   :target: ../../_static/images/administration/operator-admin/governance-02.png

.. note::

   You cannot create or delete an operator, and its form has no **Contacts for company** section:
   you manage its accounts in `Users`_.

.. _operator-admin-users:

Users
~~~~~

The **Users** list shows the accounts of your operator, your own included, and the incident user accounts suggested
as members of it. For each account, it shows the contact details, whether the email address is verified and
two-factor authentication is activated, whether the account **Is Administrator** of your operator and is
**Approved** as a member of it, when the account was created, and its **Account actions**.
To narrow the list down, search for a name or an email address.

.. figure:: /_static/images/administration/operator-admin/governance-03.png
   :alt: Users list of an operator administrator with the column headers and the Set Administrator and Reset 2FA token buttons of an operator user outlined
   :target: ../../_static/images/administration/operator-admin/governance-03.png

The **Account actions** of a row are **Set Administrator** or **Unset Administrator** and **Reset 2FA token**,
or **Approve** and **Reject** for a suggested account. Your own row has none. Each button first shows
what it will do in an **Attention** dialog: click **Confirm** to go ahead, or **Cancel**.

Create an account
"""""""""""""""""

1. Click **Add User**.
2. Enter the **First name**, **Last name**, **Email address** and **Phone number** of the account.
3. Tick **Create this user as an administrator** to make it an operator administrator; leave it unticked for an operator user.
4. Click **Save**.

.. figure:: /_static/images/administration/operator-admin/governance-04.png
   :alt: Add User form with the Create this user as an administrator box outlined
   :target: ../../_static/images/administration/operator-admin/governance-04.png

The account is linked to your operator straight away. It has no password yet: its owner chooses one with
**Password forgotten?** on the login page (see :doc:`/getting-started/login`), then sets up two-factor authentication
at the first login (see :doc:`/getting-started/enable-2fa`).

.. note::

   The email address must not belong to an existing account: the form shows
   **An account with this email address already exists.** To add an existing account to your operator,
   ask your regulator (see :ref:`regulator-user-contacts`).

Change an account
"""""""""""""""""

Click a name to open the account. You can change its **First name**, **Last name** and **Phone number**, then click **Save**.
Its **Email address** and the **Additional information** are read-only.

.. figure:: /_static/images/administration/operator-admin/governance-05.png
   :alt: Change User form of an operator user with the Reset 2FA token, Set Administrator and Delete buttons outlined
   :target: ../../_static/images/administration/operator-admin/governance-05.png

The **Reset 2FA token** and **Set Administrator** or **Unset Administrator** buttons sit beside the fields they change,
and work as in the list:

- **Set Administrator** makes the account an operator administrator, and **Unset Administrator** makes it an operator user again.
  The account is logged out either way. You cannot change your own role.
- **Reset 2FA token** removes the authentication app of the account, when its owner has lost access to it.
  At the next login, they set up two-factor authentication again (see :doc:`/getting-started/enable-2fa`).
  To reset your own, use **Account security** at the top of the console.

.. _operator-admin-approve:

Approve an incident user
""""""""""""""""""""""""

An incident user is someone who created their own account to notify incidents (see :doc:`/getting-started/create-account`).
When your regulator adds such an account to your operator (see :ref:`regulator-user-contacts`),
it is suggested as a member of the operator and waits for your approval. Unless the account already belongs
to another operator, the email address of your operator and its administrators receive an email about the suggestion.

The **Users** list then shows **There is a suggestion to link a User Account to your company. Please Approve or Reject
the suggestion.** The row of the account has **Approved** unticked and two buttons:

- **Approve**: the account becomes an operator user of your operator, and the incidents it notified move to your operator.
- **Reject**: the suggestion is removed.

Until you decide, the account opens read-only, with the question **Add this user to Company** followed by the name
of your operator, and the same two buttons.

.. important::

   Check the name and email address of the account before approving it: once approved, its owner works
   for your operator.

Remove an account
"""""""""""""""""

Open the account, click **Delete** and confirm. The account is not deleted: it is removed from your operator
and logged out. An account left without any operator is deactivated.

.. note::

   **Delete** is not shown for an operator administrator whose account has log entries, which it has as soon as
   it has worked in the console or the modules: click **Unset Administrator** first.
   For a suggested account, click **Reject** instead.
