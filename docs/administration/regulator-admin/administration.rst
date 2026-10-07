Logs
----

The **Administration** section of the console holds two logs, both read-only:

- **Log entries**: the actions made in the platform, see `Log entries`_.
- **Script execution logs**: the runs of the scheduled clean-up tasks, see `Script execution logs`_.

Log entries
~~~~~~~~~~~

As a regulator administrator, you see every log entry except those of the platform administrators:

- the additions, modifications and deletions made in the console;
- the logins and logouts of the regulator accounts;
- the exports of incidents and of security objectives declarations.

Click **Log entries**. The list shows the most recent entries first, in four columns:
**Action time**, **User**, **Content type** (the kind of object concerned, such as **Governance | User** for an account)
and **Activity** (**Addition**, **Modification**, **Deletion**, **Login**, **Logout** or **Export**).

.. figure:: /_static/images/administration/regulator-admin/administration-01.png
   :alt: Log entries list with the Filter panel and the column headers outlined
   :target: ../../_static/images/administration/regulator-admin/administration-01.png

To narrow the list down, use the search field, the dates above the list, or the **Filter** panel, **By Users**
or **By Activity**, as described in :doc:`/administration/platform-admin/administration`.
Click a column header to sort the list by that column; click it again to reverse the order.

Click the date in the **Action time** column to open the **View log entry** page. Besides the columns of the list,
it shows the **Object id** and **Object repr** (the name) of the object concerned, and the **Change message**,
which describes the change. For an export, the change message gives the number of incidents or declarations exported,
the regulation and the filters used. Click **Close** to return to the list.

.. figure:: /_static/images/administration/regulator-admin/administration-02.png
   :alt: View log entry page of a login, with its user, time, content type, object and activity
   :target: ../../_static/images/administration/regulator-admin/administration-02.png

.. note::

   Log entries are kept for ``LOG_RETENTION_TIME_IN_DAY`` days (365 by default), then deleted by a scheduled task
   (see :doc:`/technical/installation`).

Script execution logs
~~~~~~~~~~~~~~~~~~~~~

The scheduled tasks of the platform delete old data every day. Each run adds a line to the **Script execution logs**,
which gives in **Object representation** the number of objects the task deleted, for instance
*System:Incident script deletion 3 incident(s) deleted*. The tasks delete:

- the incidents older than ``INCIDENT_RETENTION_TIME_IN_DAY``;
- the security objectives declarations older than ``SECURITY_OBJECTIVE_RETENTION_TIME_IN_DAY``;
- the log entries older than ``LOG_RETENTION_TIME_IN_DAY``;
- the incident user accounts that were never activated, once their set-password link has expired;
- the incident user accounts that never reported an incident, after a period without logging in.

The list shows the **Timestamp**, **Action** and **Object representation** of each run, and its
**Additional information**. Search it by object representation; click a column header to sort it.

The tasks and their settings are described in :doc:`/technical/installation`.

.. note::

   The tasks run for the whole platform, so the lines concern every regulator, not only yours.
