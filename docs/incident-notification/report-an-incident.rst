Report an incident
------------------

To report an incident, open the :doc:`incident notification dashboard <dashboard>`
and click the **Notify an incident** button in the top-right corner of the screen.

The **Report an incident** screen guides you through up to five forms, described below:
`Contact form`_, `Legal bases`_, `Regulators`_, `Sectors`_ and `Detection date`_.
The steps are shown at the top of the screen. Click **Next** to move to the following form, **Previous** or the name of an
earlier step to go back, and **Cancel** to stop without reporting anything.
Fields marked with an asterisk (*) are mandatory.

.. note::

   Nothing is saved until you submit the last form. If you click **Cancel** or leave the page before that,
   no incident is created.

Contact form
~~~~~~~~~~~~

Fill in the contact details, so that the authorities receiving your notification can get back to you.
The form has four parts:

1. **Legal Entity Name**: The organisation reporting the incident. It is filled in with the operator you are working for.
2. **Contact Information**: The person in charge of the incident notification: job title, first name, last name, email and telephone.
   It is filled in with the details of your account; change them if someone else is in charge.
3. **Technical Contact Information**: The person who can answer technical questions about the incident.
   If it is the same person as the contact, turn on the **Is the contact also the technical contact?** switch
   instead of entering the same details again.
4. **References** (optional):

   - **Incident reference**: Your own reference for the incident, such as an internal ticket number or a CERT reference,
     to make it easier to track.
   - **Complaint reference**: The file number of a criminal complaint you have filed with the police about the incident.

.. figure:: /_static/images/incident-notification/report-an-incident-01.png
   :alt: Contact form with the Legal Entity Name and Technical Contact Information sections outlined
   :target: ../_static/images/incident-notification/report-an-incident-01.png

Once you have filled in all mandatory fields, click **Next** to go to the **Legal bases** form.

Legal bases
~~~~~~~~~~~

Select the regulations under which you are notifying the incident. You can select one or several of them.
Only the regulations for which a regulator has set up an incident notification procedure are listed.
After making your selection, click **Next** to go to the **Regulators** form.

.. figure:: /_static/images/incident-notification/report-an-incident-02.png
   :alt: Legal bases form with two regulations selected
   :target: ../_static/images/incident-notification/report-an-incident-02.png

Regulators
~~~~~~~~~~

Under **Send notification to**, select the regulators that must receive your notification.
Only the regulators in charge of the regulations you selected are listed. At least one regulator is required.
After making your selection, click **Next** to continue.

.. figure:: /_static/images/incident-notification/report-an-incident-03.png
   :alt: Regulators form with one regulator selected
   :target: ../_static/images/incident-notification/report-an-incident-03.png

Sectors
~~~~~~~

Select the sectors affected by the incident. The sectors are grouped under their main sector,
and only the sectors covered by the regulations and regulators you selected are listed.

.. figure:: /_static/images/incident-notification/report-an-incident-04.png
   :alt: Sectors form with two sectors selected
   :target: ../_static/images/incident-notification/report-an-incident-04.png

Detection date
~~~~~~~~~~~~~~

Select the time zone of the incident, then enter the date and time at which the incident was detected,
in the format ``yyyy-mm-dd hh:mm``. You can also pick them in the calendar that opens from the calendar icon.

.. figure:: /_static/images/incident-notification/report-an-incident-05.png
   :alt: Detection date form with the time zone and the calendar open
   :target: ../_static/images/incident-notification/report-an-incident-05.png

.. note::

   The **Sectors** and **Detection date** forms appear only when the regulations and regulators you selected need them.
   If they do not, the wizard ends at the previous form.

After the incident is submitted
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Click the button of the last form to submit the notification. The platform then creates the incident
and, if your regulator has set one up, sends an email announcing it.

.. important::

   The platform creates **one incident for each notification procedure** that matches your selection.
   A notification procedure is set up by a regulator for a regulation and a group of sectors,
   so selecting several legal bases, regulators or sectors can create several incidents, each with its own reference and reports.

- If a single incident is created, the platform opens its first report straight away, so that you can fill it in
  (see :doc:`operator`).
- If several incidents are created, the platform takes you back to the dashboard, where each one appears on its own line.
  Open each incident's first report from the **Report** column.

In the example below, the two selected sectors belong to two different notification procedures, so two incidents were created:

.. figure:: /_static/images/incident-notification/report-an-incident-06.png
   :alt: Dashboard listing the two incidents just created, with their sectors outlined
   :target: ../_static/images/incident-notification/report-an-incident-06.png

.. note::

   The number of incidents you can report per day is limited. Once the limit is reached, the platform shows
   **The daily limit of incident reports has been reached. Please try again tomorrow.** and takes you back to the dashboard.
