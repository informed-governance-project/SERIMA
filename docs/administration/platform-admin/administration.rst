Logs
----

The **Administration** section of the console holds the **Log entries**. As a platform administrator, you see:

- the actions of the platform administrators: additions, modifications and deletions in the console, logins and logouts;
- every export of incidents or of security objectives declarations, whoever made it.

The actions of the regulators are not listed here: their regulator administrators see them in their own log
(see :doc:`/administration/regulator-admin/administration`).

Find a log entry
~~~~~~~~~~~~~~~~

Click **Log entries**. The list shows the most recent entries first, in four columns:

- **Action time**: when the action was made.
- **User**: the account that made it.
- **Content type**: the kind of object concerned, such as **Governance | User** for an account.
- **Activity**: **Addition**, **Modification**, **Deletion**, **Login**, **Logout** or **Export**.

.. figure:: /_static/images/administration/platform-admin/administration-01.png
   :alt: Log entries list with the Filter panel and the column headers outlined
   :target: ../../_static/images/administration/platform-admin/administration-01.png

To narrow the list down:

- Enter a word in the search field: it looks up the name of the object concerned and the description of the change.
- Click a year, then a month and a day, above the list, to see the entries of that period only.
- Use the **Filter** panel on the right, **By Users** or **By Activity**. Click **Show counts** to see how many entries each choice holds.

Click a column header to sort the list by that column; click it again to reverse the order.

View a log entry
~~~~~~~~~~~~~~~~

Click the date in the **Action time** column to open the **View log entry** page. Besides the columns of the list,
it shows the **Object id** and **Object repr** (the name) of the object concerned, and the **Change message**,
which describes the change. For an export, the change message gives the number of incidents or declarations exported,
the regulation and the filters used.

.. figure:: /_static/images/administration/platform-admin/administration-02.png
   :alt: View log entry page of a login, with its user, time, content type, object and activity
   :target: ../../_static/images/administration/platform-admin/administration-02.png

Log entries cannot be changed. Click **Close** to return to the list.

.. note::

   Log entries are kept for ``LOG_RETENTION_TIME_IN_DAY`` days (365 by default), then deleted by a scheduled task
   (see :doc:`/technical/installation`).

.. tip::

   Each incident export also sends every platform administrator an email, **New incident mass export**,
   so you do not need to watch the log to know that one was made.
