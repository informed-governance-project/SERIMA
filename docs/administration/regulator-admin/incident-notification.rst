Incident notification configuration
-----------------------------------

The **Incident notification** section of the console holds everything operators go through when they notify
an incident to your regulator: the reports they fill in, their questions and deadlines, and the emails
the platform sends along the way. It lists **Conditional questions**, **Emails**, **Impact**,
**Incident notification workflows**, **Incident reports**, **Questions** and **Reminder emails**.

How the pieces fit together
~~~~~~~~~~~~~~~~~~~~~~~~~~~

- An **incident notification workflow** is the procedure for one regulation (legal basis), one regulator and a group
  of sectors. When an operator notifies an incident, the platform creates one incident for each active workflow
  that matches the legal bases, regulators and sectors selected (see :doc:`/incident-notification/report-an-incident`).
- A workflow is a sequence of **incident reports**, such as a preliminary report followed by a final report.
  The workflow sets the order of the reports and the deadline of each one.
- A report is a questionnaire. Its **questions** are grouped into categories, each shown to the operator as one form
  (see :doc:`/incident-notification/fill-in-a-report`). A question can be mandatory, and it can be displayed
  only after a given answer to another question (**conditional questions**).
- A report can also ask the operator to select the **impacts** of the incident, defined per regulation and sector.
- **Emails** are the templates the platform sends when an incident is created, when a report is submitted,
  when the status of a report changes and when an incident is closed. **Reminder emails** chase the reports
  that have not been submitted.

Since each item refers to the previous ones, set them up in this order:

1. `Emails`_
2. `Questions`_
3. `Incident reports`_, with their questionnaire
4. `Conditional questions`_
5. `Impacts`_
6. `Incident notification workflows`_
7. `Reminder emails`_

The lists, forms, language tabs and the icons beside the drop-downs work as described in
:doc:`/administration/platform-admin/governance`.

.. important::

   You can change or delete only the objects your regulator created. Questions answered in an incident,
   and workflows that already have incidents, become read-only: their page opens as **View** instead of
   **Change**, with the message **Modification and deletion actions are not allowed**.

.. _incident-emails:

Emails
~~~~~~

The **Emails** list holds the email templates of the module, with their **Name**, **Subject** and **Content**.
Use the **By Email type** filter to see which templates are used as opening, closing, status update or reminder emails.

.. figure:: /_static/images/incident-notification/configuration-01.png
   :alt: Emails list with the Emails entry of the sidebar and the column headers outlined
   :target: ../../_static/images/incident-notification/configuration-01.png

An email template has:

- a **Name**, which identifies it in the drop-downs of the reports and workflows. Operators never see it.
- a **Subject** and a **Content**, which can be translated. The content is written in Markdown:
  the **HTML preview** below it shows how it is formatted, once saved.

.. figure:: /_static/images/incident-notification/configuration-02.png
   :alt: Change Email form with the language tabs, the Name, Subject and Content fields and the Available placeholders button outlined
   :target: ../../_static/images/incident-notification/configuration-02.png

Placeholders
""""""""""""

Click **Available placeholders** to list the placeholders you can type in the subject or the content.
Each one is replaced by its value when the email is sent.

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Placeholder
     - Replaced by
   * - ``#PUBLIC_URL#``
     - The address of the platform.
   * - ``#INCIDENT_ID#``
     - The reference of the incident.
   * - ``#INCIDENT_NOTIFICATION_DATE#``
     - The date the incident was notified.
   * - ``#INCIDENT_DETECTION_DATE#``
     - The date the incident was detected, as given in the latest report, or at the notification before any report.
   * - ``#INCIDENT_STARTING_DATE#``
     - The date the incident started, as given in the latest report. Empty before the first report.
   * - ``#INCIDENT_STATUS#``
     - The status of the incident: ongoing or closed.
   * - ``#REPORT_NAME#``
     - The report the email is about. In the opening and closing emails, the latest report submitted.
   * - ``#REPORT_REVIEW_STATUS#``
     - The status of that report, as shown on the dashboard (see :ref:`report-statuses`).
   * - ``#REPORT_COMMENT_ADDED#``
     - "New comment added" when the regulator left a review comment on that report, otherwise nothing.
   * - ``#DEADLINE#``
     - The deadline of the next report to submit. Empty when there is none.

Languages
"""""""""

One email is sent in all languages: the content in the default language of the platform comes first,
followed by each translation that differs from it. The subject is sent in the default language.

.. note::

   A template is used wherever it is selected. Changing it changes the emails of every workflow and report
   that uses it, including for the incidents in progress.

Who receives the emails
"""""""""""""""""""""""

The emails of an incident are sent to the person who notified it, to the operator's address and administrators,
to your regulator's address for incident notification, to your regulator administrators, and to the regulator users
in charge of the sectors of the incident. The opening and submission emails also go to the observers that receive
the incident (see :ref:`platform-observers`).

Questions
~~~~~~~~~

The **Questions** list holds the questions you can use in your reports, with their **Reference**, **Label**,
**Question Type** and **Answers**. A question can be used in several reports.

.. figure:: /_static/images/incident-notification/configuration-03.png
   :alt: Questions list with the Questions entry of the sidebar and the column headers outlined
   :target: ../../_static/images/incident-notification/configuration-03.png

A question has:

- a **Question Type**, described below.
- a **Reference**, unique on the platform. It is shown in square brackets before the question in the drop-downs
  of the questionnaire, so that you can tell similar questions apart.
- a **Label**, the question the operator reads, and an optional **Tooltip**, shown when the operator hovers over the answer field.
- **Predefined answers**, for the choice types: click **Add another Predefined answer** for each answer,
  and set their order with **Position**.

.. figure:: /_static/images/incident-notification/configuration-04.png
   :alt: Change Question form with its type, reference, label and tooltip, and the predefined answers outlined
   :target: ../../_static/images/incident-notification/configuration-04.png

.. figure:: /_static/images/incident-notification/configuration-05.png
   :alt: Question Type drop-down open with the eight types
   :target: ../../_static/images/incident-notification/configuration-05.png

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Question Type
     - The operator answers with
   * - Freetext
     - A text field.
   * - Multiple Choice
     - Check boxes: one or more of the predefined answers.
   * - Single Option Choice
     - Radio buttons: one of the predefined answers.
   * - Multiple Choice + Free Text
     - Check boxes, plus an **Add details** text field.
   * - Single Choice + Free Text
     - Radio buttons, plus an **Add details** text field.
   * - Country list
     - A drop-down list of countries, several of which can be selected.
   * - Region list
     - A drop-down list of the regions set up on the platform, several of which can be selected.
   * - Date picker
     - A date and time, which cannot be in the future.

To create a variant of an existing question, tick it in the list and run **Duplicate selected items**:
the copy gets the same answers, and "(copy)" is added to its reference and label.

.. note::

   Once a question has been answered in an incident, it becomes read-only. To change it, duplicate it,
   change the copy and use the copy in your reports.

Incident reports
~~~~~~~~~~~~~~~~

The **Incident reports** list shows the **Name**, **Label** and **Description** of each report,
whether **Impacts disclosure required** is ticked, and its **Submission email**.

.. figure:: /_static/images/incident-notification/configuration-06.png
   :alt: Incident reports list with the Incident reports entry of the sidebar and the column headers outlined
   :target: ../../_static/images/incident-notification/configuration-06.png

Create a report
"""""""""""""""

1. Click **Add incident report** and fill in the **General** section:

   - **Name**: identifies the report in the console. It must be unique on the platform, so include your regulator
     and regulation in it.
   - **Label** and **Description**: what operators and regulator users see.
   - **Impacts disclosure required**: adds a last form where the operator selects the impacts of the incident
     (see `Impacts`_). It is shown only when impacts exist for the regulation and sectors of the incident.

2. In **Notification Email**, select the **Submission email**, sent each time this report is submitted,
   unless the incident is closed.

   .. figure:: /_static/images/incident-notification/configuration-07.png
      :alt: Change Incident report form with its General and Notification Email sections
      :target: ../../_static/images/incident-notification/configuration-07.png

3. Build the **Questionnaire**, as described below, and click **Save**.

To start from an existing report, open it, change its name and click **Save as new**: the copy has the same questionnaire.

The questionnaire
"""""""""""""""""

Click **Add another Question** for each question of the report, and fill in its row:

- **Question**: the question, picked from your `Questions`_ by their label, with their reference in square brackets.
- **Mandatory**: the operator must answer the question to go on.
- **Conditional display**: the question is hidden until the operator selects a given answer to another question
  (see `Conditional questions`_).
- **Position**: the order of the question within its category.
- **Category option**: the category of the question. Each category is a form of the report, under the title of the category.
  The drop-down lists the categories already used in this report. To add one, click the plus icon beside it:
  in the pop-up, select the **Question category**, or create it with the plus icon, and give its **Position**,
  the order of this form in the report.

.. figure:: /_static/images/incident-notification/configuration-08.png
   :alt: Questionnaire section of a report with its column headers outlined
   :target: ../../_static/images/incident-notification/configuration-08.png

To remove a question from the report, tick **Delete?** on its row and click **Save**.

.. important::

   A report can be used in several workflows, and it stays editable after incidents have used it:
   your changes apply to the reports operators fill in from then on, in every workflow that uses the report,
   including for the incidents in progress. The platform keeps the history of the questionnaire, so the reports
   already submitted keep their answers.

.. warning::

   Changing the question, the category or the **Conditional display** of a row that has already been answered
   removes the conditional questions of that row: set them up again afterwards.

A report that has been answered in an incident cannot be deleted.

Conditional questions
~~~~~~~~~~~~~~~~~~~~~

A conditional question is displayed only when the operator selects a given answer to another question of the same form.
For example, the operator is asked how many times the incident recurred only after answering **Yes** to
"Is this a recurring incident?". Each rule links a question, one of its answers, and the question it displays.
The list shows the **Workflow** (the report), **Question**, **Selected answer** and **Next question** of each rule.

.. figure:: /_static/images/incident-notification/configuration-09.png
   :alt: Conditional questions list with the Conditional questions entry of the sidebar and the column headers outlined
   :target: ../../_static/images/incident-notification/configuration-09.png

To create a rule:

1. In the questionnaire of the report, tick **Conditional display** on the question to display, and save the report.
2. Click **Add conditional question** and select the **Report**. Only the reports with a question marked
   **Conditional display** are listed.
3. Select the **Question** that triggers the display, the **Selected answer** that triggers it,
   and the **Next question** to display. Click **Save**.

   .. figure:: /_static/images/incident-notification/configuration-10.png
      :alt: Add Conditional question form with a report, a question, an answer and the next question selected
      :target: ../../_static/images/incident-notification/configuration-10.png

Create one rule for each answer that must display the question. The rules have these limits:

- The triggering question must be of a choice type (Multiple Choice, Single Option Choice, or either of them
  with free text), and not be marked **Conditional display** itself.
- The next question must be marked **Conditional display**, belong to the same category, and not trigger
  another question: conditional questions go one level deep only.

.. note::

   A question marked **Conditional display** without any rule is never shown. A mandatory conditional question
   is required only when it is displayed.

Impacts
~~~~~~~

Impacts describe the consequences an incident can have, such as an outage of a given duration.
When a report has **Impacts disclosure required** ticked, its last form lists the impacts of the regulation and
sectors of the incident, grouped by sector, and the operator selects those that apply.

The **Impact** list shows the **Regulations**, **Sector**, **Sub-sector** and **Headline** of each impact.
Use the **By Sectors** and **By Legal basis** filters, or the search box, to find one.

.. figure:: /_static/images/incident-notification/configuration-11.png
   :alt: Impact list with the Impact entry of the sidebar and the column headers outlined
   :target: ../../_static/images/incident-notification/configuration-11.png

An impact has:

- a **Label**, the description of the impact the operator selects.
- a **Title**, the short name shown in the **Headline** column of the list.
- its **Legal basis**: the regulations it applies to. Only the regulations of your regulator are listed.
- its **Sectors**.

.. figure:: /_static/images/incident-notification/configuration-12.png
   :alt: Change Impacts form with its label, title, legal basis and sectors
   :target: ../../_static/images/incident-notification/configuration-12.png

Impacts stay editable after incidents have used them.

Incident notification workflows
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The **Incident notification workflows** list shows whether each workflow is **Active**, its **Name**,
**Legal basis** and **Regulator**, and whether the **Incident detection date required** is ticked.
It also lists the workflows of the other regulators, which you can open read-only.
The user pages call a workflow a notification procedure.

.. figure:: /_static/images/incident-notification/configuration-13.png
   :alt: Incident notification workflows list with the sidebar entry and the column headers outlined
   :target: ../../_static/images/incident-notification/configuration-13.png

Create a workflow
"""""""""""""""""

1. Click **Add incident notification workflow** and fill in the **General** section:

   - **Active**: only the active workflows create incidents.
   - **Name**: the name of the workflow.
   - **Incident detection date required**: the operator must give the date the incident was detected when
     notifying it (see :doc:`/incident-notification/report-an-incident`). Tick it when a report deadline is counted
     from the detection date.

2. In **Supervision**, select the **Legal basis** and the **Regulator**. Only the regulations of your regulator
   are listed (see :ref:`platform-regulations`).
3. In **Sectors**, move the sectors the workflow covers to the list on the right.
   A workflow without sectors applies to every incident notified under its legal basis to your regulator.

   .. figure:: /_static/images/incident-notification/configuration-14.png
      :alt: Add Incident notification workflow form with its General, Supervision and Sectors sections filled in
      :target: ../../_static/images/incident-notification/configuration-14.png

4. In **Notification Email**, select the emails of the workflow:

   - **Opening email**: sent when the incident is created.
   - **Closing email**: sent when the incident is closed.
   - **Status update email**: sent when you change the review status of a report
     (see :doc:`/incident-notification/review-a-report`), and when a report reaches its deadline
     without having been submitted.

   .. figure:: /_static/images/incident-notification/configuration-15.png
      :alt: Notification Email section with an opening, closing and status update email selected
      :target: ../../_static/images/incident-notification/configuration-15.png

5. In **Incident reports**, click **Add another Incident report** for each report of the workflow, and fill in its row:

   - **Incident report**: the report (see `Incident reports`_).
   - **Position**: the order of the report in the workflow. Operators submit the reports in this order,
     each one becoming available once the previous one has been submitted.
   - **Deadline in hours** and **Event triggering deadline**: the report is due that many hours after the event:
     **Notification Date** (of the incident), **Detection Date** (of the incident), or **Previous Workflow**
     (the latest submission of the previous report). With **None**, the report has no deadline.

   .. figure:: /_static/images/incident-notification/configuration-16.png
      :alt: Incident reports section with a preliminary report due 24 hours and a final report due 360 hours after the detection date
      :target: ../../_static/images/incident-notification/configuration-16.png

6. Click **Save**.

In the example above, the preliminary report is due 24 hours after the incident was detected,
and the final report 360 hours (15 days) after it. A report not submitted by its deadline shows as
**Submission overdue** on the dashboard, and **Late submission** once submitted (see :ref:`report-statuses`).

Change a workflow in use
""""""""""""""""""""""""

Once an incident has been created with a workflow, the workflow is read-only, so that its incidents keep
the reports and deadlines they started with. To change it:

1. Open the workflow and click **Save as new** to create a copy, with the same sectors, emails and reports.
   Make your changes in the copy and save it.

   .. figure:: /_static/images/incident-notification/configuration-17.png
      :alt: Read-only workflow with the message that modification is not allowed and the Save as new button outlined
      :target: ../../_static/images/incident-notification/configuration-17.png

2. In the list, tick the old workflow, choose **Toggle active status of selected items** in the **Action** drop-down
   and click **Run**. The old workflow no longer creates incidents; its incidents carry on.

   .. figure:: /_static/images/incident-notification/configuration-18.png
      :alt: Action drop-down of the workflows list open on Toggle active status of selected items
      :target: ../../_static/images/incident-notification/configuration-18.png

.. tip::

   The same action deactivates a workflow temporarily, and reactivates it.

Reminder emails
~~~~~~~~~~~~~~~

Reminder emails chase the reports of an incident in progress. The platform checks every hour,
and sends each reminder once, when its delay has elapsed. The list shows the **Regulation**, **Report**,
**Headline**, **Trigger event** and **Delay in hours** of each reminder.

.. figure:: /_static/images/incident-notification/configuration-19.png
   :alt: Reminder emails list with the Reminder emails entry of the sidebar and the column headers outlined
   :target: ../../_static/images/incident-notification/configuration-19.png

A reminder has:

- a **Report**: a report of a workflow, shown as the workflow name followed by the report name.
- an **Email**: the template sent (see `Emails`_), with its own subject.
- a **Trigger event** and a **Delay in hours**:

  - **Incident detection date**: sent that many hours after the incident was detected, if the report has not been
    submitted yet. The incident must have a detection date.
  - **Previous Workflow date**: sent that many hours after the previous report was first submitted,
    if the report has not been submitted yet.
  - **Notification Date of the workflow**: sent that many hours after the report was first submitted.

- an **Email subject**: the name of the reminder in the list. The email sent uses the subject of its template.

.. figure:: /_static/images/incident-notification/configuration-20.png
   :alt: Change Reminder email form with its report, email, trigger event, delay and email subject
   :target: ../../_static/images/incident-notification/configuration-20.png

.. note::

   Reminders are sent only for ongoing incidents: closing an incident stops them.
