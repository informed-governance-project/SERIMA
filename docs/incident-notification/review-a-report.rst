Review a report
---------------

As a regulator, you receive the reports operators submit for the regulations you are in charge of, and review each of them:
you either accept it, or ask the operator for more information or corrections.
Regulator users see the incidents of the sectors assigned to them (see :doc:`/getting-started/roles-and-permissions`).

Find the report to review
~~~~~~~~~~~~~~~~~~~~~~~~~

The incidents notified to you are listed on the :doc:`dashboard`. A report waiting for your review
has the status **Under review** or **Late submission** (see :ref:`report-statuses`).

.. figure:: /_static/images/incident-notification/workflow-regulator-01.png
   :alt: Incident list with an incident whose report is waiting for review outlined
   :target: ../_static/images/incident-notification/workflow-regulator-01.png

Besides the features described in :doc:`dashboard`, the **Actions** column gives you a **Contacts** icon:
it opens the contact details of the person who notified the incident, should you need to reach them directly.

.. figure:: /_static/images/incident-notification/workflow-regulator-02.png
   :alt: Contacts pop-up with the details of the person who notified the incident
   :target: ../_static/images/incident-notification/workflow-regulator-02.png

Review the report
~~~~~~~~~~~~~~~~~

1. Click the name of the report in the **Report** column.

   .. figure:: /_static/images/incident-notification/workflow-regulator-03.png
      :alt: Preliminary Incident Report link outlined in the Report column
      :target: ../_static/images/incident-notification/workflow-regulator-03.png

2. Go through the forms of the report with **Next**. They show the operator's answers, which you cannot change.
   When the operator has submitted several versions, the steps whose answers changed since the previous version are marked in orange,
   and each changed answer is outlined, with a **View previous version** button.

   .. figure:: /_static/images/incident-notification/workflow-regulator-04.png
      :alt: Report step with a changed answer outlined in orange and the Regulation step marked as changed
      :target: ../_static/images/incident-notification/workflow-regulator-04.png

   Click **View previous version** to see the answer of the previous version:

   .. figure:: /_static/images/incident-notification/workflow-regulator-05.png
      :alt: Previous version pop-up with the earlier answer
      :target: ../_static/images/incident-notification/workflow-regulator-05.png

3. The last form, **Comment/Explanation**, is where you give your review.
   Write your comment in the text field at the top, then select the **Report status** below it:

   - **Passed** if you accept the report.
   - **Revision required** if you need more information or corrections.

   .. figure:: /_static/images/incident-notification/workflow-regulator-06.png
      :alt: Comment/Explanation form with the empty comment field and the Report status drop-down open
      :target: ../_static/images/incident-notification/workflow-regulator-06.png

   The operator sees your comment next to the report. When you ask for a revision, explain in it what is missing
   or needs to be corrected, as in the example below:

   .. figure:: /_static/images/incident-notification/workflow-regulator-07.png
      :alt: Comment/Explanation form with a comment explaining the revision and Revision required selected
      :target: ../_static/images/incident-notification/workflow-regulator-07.png

4. Click **Submit** to save your review.

   .. tip::

      You can leave the report without submitting: click **Close**. Nothing is saved, and the report stays **Under review**.

After the review
~~~~~~~~~~~~~~~~

The platform takes you back to the dashboard, where the report now shows its new status:
green for **Passed**, red for **Revision required**.

.. figure:: /_static/images/incident-notification/workflow-regulator-08.png
   :alt: Tooltip saying the report has passed the review
   :target: ../_static/images/incident-notification/workflow-regulator-08.png

If your regulator has set one up, the operator receives an email telling them the status of the report has changed
(regulator administrators set up these emails, see :ref:`incident-emails`).
After a **Revision required**, the operator submits a new version of the report, which comes back to you for review
(see :ref:`update-a-report`).

.. note::

   A review applies to the version of the report you opened. Each new version the operator submits
   is **Under review** again and needs a review of its own.

Incident settings
~~~~~~~~~~~~~~~~~

Besides the **Access Log**, the **More options** menu of each incident lets you change two of its settings.
The labels show the change the option makes:

- **Set to significant impact** / **Set to no significant impact**: marks whether the incident has a significant impact,
  shown in the **Status** column of the :doc:`dashboard`.
- **Set to Inactive** / **Set to Active**: closes the incident, or reopens it.

.. figure:: /_static/images/incident-notification/workflow-regulator-09.png
   :alt: More options menu with the Access Log, significant impact and incident status options
   :target: ../_static/images/incident-notification/workflow-regulator-09.png

.. important::

   Once you close an incident, the operator can no longer submit or update any of its reports.
   Close it only when no further report is expected; you can reopen it with **Set to Active**.

.. _incident-export:

Export incidents
~~~~~~~~~~~~~~~~

Regulator administrators can export the incidents notified to their regulator, with the answers of one of their reports,
to a spreadsheet. The **Export** link appears in the top-right corner of the module once a platform administrator
has ticked **Can export incidents** on your account (see :ref:`platform-regulators`). Regulator users cannot export
incidents, even with the box ticked. Observers export the incidents their observer receives in the same way,
when the platform administrator has ticked the box on their account (see :ref:`platform-observers`).

.. figure:: /_static/images/incident-notification/workflow-regulator-10.png
   :alt: Header of the incident notification module with the Export link outlined
   :target: ../_static/images/incident-notification/workflow-regulator-10.png

1. Click **Export**.
2. In the **Export incidents** pop-up, select:

   - **Regulation**: the regulation of the incidents.
   - **Workflow**: the notification procedure of that regulation. Only the procedures of the selected regulation are listed.
   - **Report**: the report whose answers you want, among the reports of the selected procedure.
   - **From** and **To**: the period in which the incidents were notified. The calendars cover the last two years.
   - **File format**: **Excel (.xlsx)** or **CSV (.csv)**.

   .. figure:: /_static/images/incident-notification/workflow-regulator-11.png
      :alt: Export incidents pop-up with the Regulation, Workflow, Report, From, To and File format fields
      :target: ../_static/images/incident-notification/workflow-regulator-11.png

3. Click **Export**. The file, ``export.xlsx`` or ``export.csv``, downloads straight away.

The file has one row per incident notified in the period under the selected procedure, from the most recent,
and holds the latest submitted version of the selected report. Incidents for which that report has not been submitted
are left out. Each row gives:

- the operator, the incident reference, the notification, detection, start and resolution dates, the regulation,
  whether the impact is significant, the incident status, and the contact and technical contact details;
- the report, its status and the date of its version;
- one column per affected sector, one per answer of the report, and the impacts selected for each sector.

The headers of the incident and report columns are in English, whatever the language of the platform.
If no incident matches your choices, the pop-up closes with the message **No incidents available for export.**

.. note::

   Each export is recorded in the log entries of the administration console (activity **Export**), with the number
   of incidents exported, the regulation, the procedure, the report and the period
   (see :doc:`/administration/regulator-admin/administration`). Every platform administrator also receives an email,
   **New incident mass export**, naming the regulation.

.. _regulator-own-incidents:

My reported incidents
~~~~~~~~~~~~~~~~~~~~~

A regulator can also be the victim of an incident, and notify it like an operator. Regulator administrators and
regulator users do this in a second view of the module: click **My reported incidents** in the top-right corner.
Click **Overview** to return to the incidents notified to you.

.. figure:: /_static/images/incident-notification/workflow-regulator-12.png
   :alt: My reported incidents view with the My reported incidents link and the Notify an incident button outlined
   :target: ../_static/images/incident-notification/workflow-regulator-12.png

The view lists the incidents notified by the accounts of your regulator, and works like an operator's dashboard
(see :doc:`dashboard`): it shows the **Regulator** each incident was notified to instead of the operator columns,
and the **Report** column lets you fill in the reports.

- To notify an incident, click **Notify an incident** and follow :doc:`report-an-incident`.
  The **Legal Entity Name** is your regulator, and the incident is recorded under its name.

  .. figure:: /_static/images/incident-notification/workflow-regulator-13.png
     :alt: Contact form of a new notification with the Legal Entity Name filled in with the regulator outlined
     :target: ../_static/images/incident-notification/workflow-regulator-13.png

- To submit or update its reports, follow :doc:`fill-in-a-report`. You fill in the reports yourself, as an operator does:
  there is no **Comment/Explanation** form for you there.
- As long as none of its reports is submitted, an incident can be deleted with the **Delete** icon in the **Actions** column.

The regulator you select in the **Regulators** form reviews your reports, as described above, on its **Overview**.
It may be your own regulator: the incident then appears in both views, and you review it from the **Overview**.

.. important::

   Open your own incidents from **My reported incidents**. From the **Overview**, an incident your regulator
   notified opens in review mode, with read-only answers.
