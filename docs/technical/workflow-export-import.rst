Copying an incident notification workflow
=========================================

Two management commands copy the whole configuration of an incident notification workflow, either inside one
instance or from one instance to another, for example from a test platform to production:

- ``export_sector_regulation`` writes the configuration of one workflow to a JSON file.
- ``import_sector_regulation`` loads that file into another workflow, which must exist and be blank.

They are run on the server by the person who maintains the instance, as there is no button for them
in the administration. In the code and in the command names, a workflow is a *sector regulation* and an
incident report is a *workflow*.

What the file contains
----------------------

The export holds configuration only, never incidents or operator data:

- the workflow: its names in every language, **Active**, **Incident detection date required**, its sectors,
  and its opening, closing and status-change emails;
- its incident reports, with their position, deadline and reminder emails;
- each report's questions in their categories, with their position, the **Mandatory** and **Conditional** flags,
  the predefined answers and the conditional questions;
- every email the workflow and its reports use (email templates);
- every impact of the workflow's legal basis, and the sectors those impacts refer to;
- the sectors involved, along with their parent sectors.

The file also lists the workflow's legal basis and regulator, along with the regulator's address and
notification email, so that you know where it came from. The import does not read them: the destination
workflow keeps its own legal basis and regulator.

Finding a workflow's ID
-----------------------

Both commands take the database ID of a workflow. In the administration, open the workflow under
**Incident notification workflows**: the ID is the number in the page address,
``/admin/incidents/sectorregulation/<ID>/change/``.

Export
------

.. code-block:: console

    $ poetry run python manage.py export_sector_regulation <ID>
    $ poetry run python manage.py export_sector_regulation <ID> -o my-workflow.json --force

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Option
     - Effect
   * - ``-o``, ``--output <path>``
     - Where to write the file. Default: ``sector_regulation_<ID>.json`` in the current directory.
       The directory must already exist.
   * - ``--force``
     - Overwrite the output file if it already exists. Without it, the command stops.

Import
------

.. code-block:: console

    $ poetry run python manage.py import_sector_regulation <file.json> <ID>
    $ poetry run python manage.py import_sector_regulation <file.json> <ID> --create-all

Prepare the destination first: in the administration, create the workflow with **Add incident notification
workflow**, choosing its legal basis and regulator, and add no incident report to it. The import refuses a
workflow that already has a report.

The import then replaces the workflow's names, its **Incident detection date required** setting, its
three emails and its sectors with those from the file, and adds the reports.
Every object it creates belongs to the workflow's regulator.

The destination is always left **inactive**, whatever the file says. Check the result in the administration,
then activate the workflow as described in :doc:`/administration/regulator-admin/incident-notification`.

.. note::

   The import runs in a single transaction. If anything goes wrong, it stops with
   ``Import failed; no changes were saved:`` followed by the reason, and the database is left as it was.

Reuse or create
~~~~~~~~~~~~~~~

The import has two modes, which cannot be combined:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Mode
     - Behaviour
   * - ``--reuse`` (default)
     - Reuse every object whose configuration already exists in the database, and create only those that
       differ. Use it to copy a workflow without duplicating its emails, reports and questions.
   * - ``--create-all``
     - Create every object, even when an identical one exists, to get a copy that can be edited
       without affecting the original.

.. warning::

   A reused object is shared. A report, question or email reused by ``--reuse`` is the same object in the
   original workflow and in the new one: changing it in the administration changes it in both.
   Use ``--create-all`` if the copy is meant to diverge.

When ``--reuse`` finds a match
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

An object is reused only when its whole configuration matches; otherwise a new one is created.
Translations must match in every language: a language present on one side only is a difference.

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Object
     - Reused when an existing one has
   * - Email
     - the same name, and the same subject and content.
   * - Category
     - the same label.
   * - Question
     - the same reference, type, label and tooltip, and exactly the same predefined answers
       (text and position).
   * - Report
     - the same name, **Impact needed** flag, submission email, label and description, and exactly the same
       questions: same question, category, position of the category, position of the question,
       **Mandatory** and **Conditional** flags. Deleted questions are ignored.
   * - Category option and question option
     - the report they belong to is reused. A report that is created gets its own.
   * - Conditional question
     - the same question, answer and next question, which in practice means its report is reused.
   * - Impact
     - the same label and headline, the destination's legal basis and no other, and the same sectors.

A report matches as a whole or not at all, and it depends on the objects it uses: a single differing
question, or a submission email that had to be created, is enough for the report to be created again,
along with all of its questions.

A question or report that is created while one with the same reference or name exists gets a suffix,
since references and names are unique: ``_import_2`` for a question reference, ``(import 2)`` appended to
a report name, then ``3``, ``4``… This also happens in ``--reuse`` mode, when a question with the same
reference exists but differs.

In ``--create-all`` mode, every object is created and suffixed wherever its reference or name is taken.

Whatever the mode
~~~~~~~~~~~~~~~~~

- **Sectors** are matched on their acronym, even with ``--create-all``. An existing sector is reused as it is;
  a missing one is created with its parent and its names from the file.
- The links between the workflow and its reports, and the reminder emails, belong to the destination, so
  they are always created.

Reading the output
~~~~~~~~~~~~~~~~~~

.. code-block:: text

    Imported configuration into SectorRegulation <ID>
      Reports                0 created,   2 reused, 2 linked
      Emails                 0 created,   4 reused, 1 reminder created
      Categories             0 created,   4 reused
      Category options       0 created,   6 reused
      Questions              0 created,  21 reused
      Predefined answers     0 created,  82 reused
      Question options       0 created,  30 reused
      Conditional questions  0 created,   3 reused
      Impacts                0 created, 156 reused
      Sectors                0 created,  13 reused, 8 linked

- **created**: new rows written to the database.
- **reused**: existing rows attached to the destination.
- **linked**: reports and sectors attached to the destination workflow.
- **reminder(s) created**: reminder emails of the reports, always created.

With ``--reuse``, all zeros in the **created** column means that the whole configuration already existed and
nothing was duplicated.

Moving a workflow between instances
-----------------------------------

Export on the source instance, copy the file to the destination server, and import it there.
With Docker, run the commands in the ``web`` container and copy the file in and out with ``docker compose cp``:

.. code-block:: console

    $ docker compose exec web python manage.py export_sector_regulation <ID> -o /tmp/workflow.json
    $ docker compose cp web:/tmp/workflow.json .

    $ docker compose cp workflow.json web:/tmp/workflow.json
    $ docker compose exec web python manage.py import_sector_regulation /tmp/workflow.json <ID>

Files exported by earlier versions, whose email content was Markdown, can still be imported: the content is
converted to HTML on the way in.

Common errors
-------------

``SectorRegulation <ID> does not exist.``
    No workflow has that ID. Check it in the administration.

``<file> already exists. Use --force to overwrite it.``
    The export would overwrite a file. Choose another ``-o`` path or add ``--force``.

``SectorRegulation <ID> is not blank: it already has reports.``
    Choose a destination without incident reports, or create a new one.

``Sector with acronym 'XYZ' does not exist.``
    The file uses a sector that is neither in the database nor in the file.

``Sector acronym 'XYZ' is ambiguous.``
    Two sectors in the database share that acronym. Fix the data before importing.

``Unsupported configuration format.`` or ``Unsupported format version …``
    The file was not produced by ``export_sector_regulation``, or by a newer version of SERIMA than the one
    importing it.
