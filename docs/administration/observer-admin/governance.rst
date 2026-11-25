Governance
----------

The **Governance** section of the console is where you manage your observer and its accounts.
For an observer administrator, it lists:

- **Observers**, where you change your observer, how it receives incidents and who administers it,
  see `Your observer`_, `Notification mode`_ and `Observer accounts`_;
- **Observer connectors**, where you connect your observer to your own systems, see `Connectors`_;
- **Users**, where you add and change the accounts of your observer, see `Users`_.

The lists and forms work as described in :doc:`/administration/platform-admin/governance`.

.. _observer-admin-observer:

Your observer
~~~~~~~~~~~~~

The **Observers** list shows only your observer, with its **Name**, **Full name** and **Description**.

.. figure:: /_static/images/administration/observer-admin/governance-01.png
   :alt: Observers list with Observers selected in the sidebar and the column headers outlined
   :target: ../../_static/images/administration/observer-admin/governance-01.png

Click its name to open it. You can change:

- its **Name**, **Full name** and **Description**, in each language of the platform: click a language tab,
  fill in the fields and save before switching to another tab;
- its **Country** and **Address**;
- its **E-mail address for incident notification**, the shared address that receives the emails the platform sends
  about the incidents your observer receives;
- its **Notification mode**, see `Notification mode`_.

Then click **Save**.

.. figure:: /_static/images/administration/observer-admin/governance-02.png
   :alt: Change Observer form with the language tabs, the E-mail address for incident notification and the Notification mode fields outlined
   :target: ../../_static/images/administration/observer-admin/governance-02.png

.. _observer-admin-notification-mode:

Notification mode
~~~~~~~~~~~~~~~~~

The **Notification mode** of your observer decides where the platform sends the incidents your observer receives:

- **Default (e-mail when no active connector)**: by email while your observer has no active connector,
  and only through the connectors once one is active;
- **E-mail and connectors**: by email, and through every active connector;
- **Connectors only (never e-mail)**: only through the active connectors, never by email.

The emails go to the **E-mail address for incident notification** and to every account of your observer.

.. warning::

   With **Connectors only (never e-mail)** and no active connector, your observer receives nothing.

.. _observer-admin-connectors:

Connectors
~~~~~~~~~~

A connector sends the incidents your observer receives to one of your own systems. The types you can choose are
the ones the platform administrator made available to your observer:

- **RT (Request Tracker)**: opens a ticket in a queue of an RT instance. Enter the **URL** of the instance, such as
  ``https://rt.example.com``, the **Queue** that receives the tickets, and the **Token** of an RT account allowed
  to create tickets in it. The first notification about an incident opens a ticket, and the following ones are added
  to that ticket as replies.
- **Webhook (HTTPS API)**: posts the incident as JSON to the **URL** of your API. Each request is signed with the
  **HMAC secret** you enter, in the ``X-Serima-Signature`` header, with the time it was sent in ``X-Serima-Timestamp``.
  Without a secret, nothing is sent and the notification fails. See :ref:`receiving webhook notifications <observer-admin-webhook-receiving>`.
- **GPG-encrypted JSON (e-mail)**: emails the incident as JSON, encrypted with the **GPG public key** you paste
  (ASCII-armored), to the **E-mail address for incident notification** of your observer.

In the JSON, the incident and each of its reports carry a ``public_id``: a random identifier that stays the same in
every notification about them and is unique across SERIMA platforms. Use it, rather than the incident reference, to
match a notification with an incident or report your system already holds.

.. _observer-admin-webhook-receiving:

**Receiving webhook notifications.** HTTPS protects the incident only on its way to your server. The JSON is not
encrypted: it holds the incident's contacts (names, emails, telephone numbers) and every answer of its reports, and
any part of your infrastructure that terminates HTTPS or records requests, such as a reverse proxy, an API gateway or
an access log, can read it. If that is not acceptable, use the **GPG-encrypted JSON** connector instead.

Choose a long random **HMAC secret** (at least 32 characters) and check every request before trusting it:

1. Compute the HMAC-SHA256 of the ``X-Serima-Timestamp`` value, a dot, and the raw request body, keyed with the
   secret, and compare it with ``X-Serima-Signature`` (after ``sha256=``) in constant time.
2. Reject the request when the timestamp is more than five minutes away from your clock, so that a captured request
   cannot be replayed later.

.. code-block:: python

   import hashlib, hmac, time


   def is_valid(secret: bytes, timestamp: str, signature: str, body: bytes) -> bool:
       expected = hmac.new(
           secret, timestamp.encode() + b"." + body, hashlib.sha256
       ).hexdigest()
       return (
           hmac.compare_digest(f"sha256={expected}", signature)
           and abs(time.time() - int(timestamp)) <= 300
       )

A request that times out is sent again, so the same notification can arrive twice. **Test connection** sends the
signed body ``{"event": "ping"}``; real notifications carry an ``incident`` object instead.

The **Observer connectors** list shows the **Name**, **Observer**, **Type** and **Active** state of each connector
of your observer. The form of your observer also lists them at the bottom, with a link to each.

To add a connector:

1. Click **Add Observer connector**, choose its **Type**, give it a **Name**, keep **Active** on and click **Save**.
2. The form opens again with the fields of that type: fill them in and click **Save and continue editing**.
3. Click **Test connection**. The result is shown beside the button.

.. note::

   The URL of an RT instance or a webhook must use HTTPS and point to a public address. Once saved, the token or
   secret is masked: to replace it, enter the new one; to remove it, clear the field and save.

To stop using a connector without deleting it, turn off **Active** and save. When the platform administrator
withdraws a type from your observer, its connectors of that type are turned off.

.. important::

   A notification a connector cannot deliver is retried up to five times over about half an hour, then given up.
   It is not sent by email instead: choose **E-mail and connectors** as the notification mode to keep
   receiving the emails as well.

Once a webhook or GPG-encrypted JSON connector has delivered an incident, the **Access Log** of the incident
records it with the action **TRANSMIT**: one entry for each report the incident holds, with the connector's name as
user and your observer as entity. An RT connector only forwards the notification email, so it is not recorded, nor
is a delivery that failed.

.. _observer-admin-accounts:

Observer accounts
~~~~~~~~~~~~~~~~~

The **Observer users** section at the bottom of the form of your observer lists its accounts, one row each.

.. figure:: /_static/images/administration/observer-admin/governance-04.png
   :alt: Observer users section with the Is administrator and Can export incidents columns and the Add another Observer user link outlined
   :target: ../../_static/images/administration/observer-admin/governance-04.png

Each row has:

- **User**: the account. The drop-down lists the active accounts of your observer and the active observer administrator accounts
  linked to no observer.
- **Is administrator**: keep it on: every member of an observer's staff is an observer administrator.
  Changing it switches the role of the account and logs it out.
- **Can export incidents**: whether the account can export the incidents your observer receives, read-only:
  the platform administrator sets it (see :ref:`incident-export`).
- the bin icon at the right of the row: removes the account from your observer. The row is covered with
  **This item will be deleted.**, and **Click to cancel** keeps it; the account is removed when you click **Save**.
  It is logged out, and can no longer use the platform;
  an observer administrator left without any observer to administer is also deactivated.

To make an existing account of your observer an observer administrator, turn on **Is administrator** on its row
and click **Save**. To add a row, click **Add another Observer user** and choose the account.

.. warning::

   Your own row is in the list too. Turning off **Is administrator** or clicking its bin icon removes your access
   to the console as soon as you save.

.. _observer-admin-users:

Users
~~~~~

The **Users** list shows the accounts of your observer, your own included. For each account, it shows
the contact details, its **Observer** and **Roles**, whether the email address is verified and two-factor authentication
is activated, when the account was created, and its **Account actions**. To narrow the list down, search for a name
or an email address, or use **By Roles** under **Filters**, above the list.

.. figure:: /_static/images/administration/observer-admin/governance-05.png
   :alt: Users list of an observer administrator with the column headers and the Filters button outlined
   :target: ../../_static/images/administration/observer-admin/governance-05.png

Create an account
"""""""""""""""""

1. Click **Add User**.
2. Enter the **First name**, **Last name**, **Email address** and **Phone number** of the account.
3. Click **Save**.

.. figure:: /_static/images/administration/observer-admin/governance-06.png
   :alt: Add User form with its contact information fields outlined
   :target: ../../_static/images/administration/observer-admin/governance-06.png

The account is linked to your observer straight away, but without the administrator role.

.. important::

   Every member of an observer's staff is an observer administrator: after creating the account, turn on
   **Is administrator** on its row in `Observer accounts`_ and click **Save**.

The account has no password yet: its owner chooses one with **Password forgotten?** on the login page
(see :doc:`/getting-started/login`), then sets up two-factor authentication at the first login
(see :doc:`/getting-started/enable-2fa`).

.. note::

   The email address must not belong to an existing account: the form shows
   **An account with this email address already exists.**

Change an account
"""""""""""""""""

Click a name to open the account. You can change its **First name**, **Last name**, **Email address**
and **Phone number**, then click **Save**. The **Additional information** is read-only: the **Observer** and **Roles**
of the account, when it joined, and whether its email address is verified and two-factor authentication activated.

.. figure:: /_static/images/administration/observer-admin/governance-07.png
   :alt: Change User form of an observer administrator with the Contact information and Additional information sections outlined
   :target: ../../_static/images/administration/observer-admin/governance-07.png

Reset two-factor authentication
"""""""""""""""""""""""""""""""

When someone has lost access to their authentication app, click **Reset 2FA token** on their row of the list,
or beside **2FA Activated** on their account, then **Confirm** in the **Attention** dialog. To reset several accounts
at once, tick them, choose **Reset 2FA** in the **Action** drop-down and click **Run**. At their next login,
they set up two-factor authentication again (see :doc:`/getting-started/enable-2fa`).
You cannot reset your own: use **Account security** in the menu under your name, at the top right of the console.

Remove an account
"""""""""""""""""

To withdraw someone's access, remove their account from your observer in `Observer accounts`_.

.. warning::

   The **Delete** button of an account deletes it for good, rather than removing it from your observer.
   It is refused for an account with log entries, which it has as soon as it has changed something in the console
   or exported incidents.
