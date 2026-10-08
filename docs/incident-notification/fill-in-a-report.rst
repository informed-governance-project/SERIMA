Fill in a report
----------------

An incident is made of one or several **reports**, such as a **Preliminary Incident Report** followed by a **Final Incident Report**.
The reports, their questions and their deadlines are set by the regulator for each regulation and sector.
Each report goes through the same cycle:

1. You fill in the report and submit it.
2. The regulator reviews it, and either accepts it (**Passed**) or asks for changes (**Revision required**).
3. If changes are needed, you submit a new version of the report, which the regulator reviews again.

This chapter describes your side of that cycle. Creating the incident itself is described in :doc:`report-an-incident`,
and the regulator's review in :doc:`review-a-report`.

.. _report-statuses:

Report statuses
~~~~~~~~~~~~~~~

Each report in the **Report** column of the :doc:`dashboard` shows its status with a colour and an icon,
explained in the **Icon guide**. Hover the mouse over a report to see its tooltip.

.. list-table::
   :header-rows: 1
   :widths: 18 27 30 25

   * - Status
     - Tooltip
     - Meaning
     - What to do
   * - Unsubmitted
     - The report has not been submitted yet.
     - The report is waiting for you, and its deadline has not passed.
     - Fill in and submit the report.
   * - Submission overdue
     - The submission of the report is overdue.
     - The deadline of the report has passed and it has not been submitted.
     - Submit the report as soon as possible.
   * - Under review
     - The report is currently under review.
     - You submitted the report in time, and the regulator has not reviewed it yet.
     - Nothing, unless you have new information: you can then submit a new version.
   * - Late submission
     - The report is currently under review.
     - You submitted the report after its deadline, and the regulator has not reviewed it yet.
     - Nothing, unless you have new information: you can then submit a new version.
   * - Revision required
     - The report has failed the review.
     - The regulator needs more information or corrections.
     - Read the review comment, then submit a new version of the report.
   * - Passed
     - The report has passed the review.
     - The regulator accepted the report.
     - Go on with the next report of the incident, if there is one.

Open a report
~~~~~~~~~~~~~

The reports of an incident are listed in the **Report** column of the :doc:`dashboard`.
A report that has not been submitted yet is shown as a red **not submitted yet** button: click it to start filling in the report.
When the notification of an incident creates a single incident, its first report opens straight away.

.. note::

   The reports must be submitted in order. The first report is available straight away;
   each of the following ones becomes available once the previous one has been submitted.
   When an incident is closed, none of its reports can be opened for editing any more.

Fill in the report
~~~~~~~~~~~~~~~~~~

The report opens as a series of forms, shown as steps at the top of the screen.
Click **Next** to move to the following form, **Previous** or the name of an earlier step to go back.

.. important::

   Reports are not the same for every incident. Each regulator sets up its reports to meet the requirements
   of the regulation they serve, so the categories and questions you see depend on the regulation, the regulator
   and the sectors of the incident, and can differ from one report to the next.
   The regulator also decides which questions are mandatory, and which ones appear only when you give
   a particular answer to an earlier question of the same category.
   The screenshots in this chapter are examples: your reports can contain other categories and questions.

1. **Incident Timeline**: The time zone of the incident, and the dates and times at which it was detected,
   started and was resolved, as far as you know them yet.

   .. figure:: /_static/images/incident-notification/workflow-operator-01.png
      :alt: Incident Timeline form of a Preliminary Incident Report
      :target: ../_static/images/incident-notification/workflow-operator-01.png

2. **Questions**: One form for each category of questions the regulator has set up for this report,
   for example the regulations and services concerned, or general information about the incident
   (its impact, the number of people affected, its duration and the geographical area concerned).

   .. figure:: /_static/images/incident-notification/workflow-operator-02.png
      :alt: Question form with two options selected
      :target: ../_static/images/incident-notification/workflow-operator-02.png

   .. figure:: /_static/images/incident-notification/workflow-operator-03.png
      :alt: General notification information form filled in
      :target: ../_static/images/incident-notification/workflow-operator-03.png

3. **Impacts**: When the report asks for it, select the impacts the incident had.

On the last form, click **Submit** to send the report to the regulator.

.. note::

   Nothing is saved until you click **Submit**. If you leave the report before that, your answers are lost.

After submitting
~~~~~~~~~~~~~~~~

Once submitted, the report is listed in the **Report** column with the status **Under review**,
or **Late submission** if it was submitted after its deadline. If the regulator has set one up, a confirmation email is sent.

.. figure:: /_static/images/incident-notification/workflow-operator-04.png
   :alt: Incident list with a report under review outlined
   :target: ../_static/images/incident-notification/workflow-operator-04.png

Each submission is kept as a separate version. Click the **Version control** icon beside the report to see them,
with their date and status:

.. figure:: /_static/images/incident-notification/workflow-operator-05.png
   :alt: Version control pop-up listing one version under review
   :target: ../_static/images/incident-notification/workflow-operator-05.png

.. important::

   Every report has a deadline set by the regulator. If a report is not submitted in time,
   its status becomes **Submission overdue**: submit it as soon as possible.

The review result
~~~~~~~~~~~~~~~~~

When the regulator has reviewed the report, its colour and icon in the **Report** column change.
Hover the mouse over the report to see its status.

If the report is accepted, it is shown in green with the status **The report has passed the review**.

.. figure:: /_static/images/incident-notification/workflow-operator-06.png
   :alt: Incident list with a passed report outlined
   :target: ../_static/images/incident-notification/workflow-operator-06.png

.. figure:: /_static/images/incident-notification/workflow-operator-07.png
   :alt: Tooltip saying the report has passed the review
   :target: ../_static/images/incident-notification/workflow-operator-07.png

The regulator can add a comment to the review. When there is one, click the **Review comment** icon (speech bubble) beside the report to read it.

.. figure:: /_static/images/incident-notification/workflow-operator-08.png
   :alt: Review comment pop-up with the regulator's comment
   :target: ../_static/images/incident-notification/workflow-operator-08.png


.. _update-a-report:

Update a report
~~~~~~~~~~~~~~~

To answer a request for changes, or to add information that has become available, click the name of the report
in the **Report** column. The report opens with your previous answers: change them and click **Submit**.
This submits a new version, which the regulator reviews again; the earlier versions remain available in **Version control**.

.. note::

   A report can be updated until the next report of the incident has been submitted.
