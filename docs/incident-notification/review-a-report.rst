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
