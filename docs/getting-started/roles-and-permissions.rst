Permissions and roles
=====================

Every account has one role. The role decides what you can do, whether the **Settings** link of the header
gives you access to the administration console, and which modules you see.

.. list-table::
   :header-rows: 1
   :widths: 14 22 40 8 16

   * - Role
     - Who has it
     - What they can do
     - Settings
     - Modules
   * - PlatformAdmin
     - The team running the platform
     - Sets up the regulators, observers, regulations, operator categories and modules,
       and manages the other platform administrators. Uses only the administration console.
     - Yes
     - None
   * - RegulatorAdmin
     - Administrators of a regulator
     - Configures the regulations of their regulator (workflows, reports, questions),
       creates regulator administrators and users, and sees everything of their regulator.
     - Yes
     - Incident notification, security objectives, reporting
   * - RegulatorUser
     - Staff of a regulator
     - Reviews what operators send, for the sectors assigned to them (nothing until a sector is assigned),
       and creates operators with their first operator administrator.
     - Yes
     - Incident notification, security objectives, reporting
   * - ObserverAdmin
     - Staff of an observer
     - Reads the incidents forwarded to their organisation, and creates the other accounts of their observer.
     - Yes
     - Incident notification (read-only)
   * - OperatorAdmin
     - Administrators of an operator
     - Creates operator administrators and users, and approves the incident users who ask to join the operator.
     - Yes
     - Incident notification, security objectives
   * - OperatorUser
     - Staff of an operator
     - Notifies incidents and submits security objectives declarations to the regulators supervising the operator.
     - No
     - Incident notification, security objectives
   * - IncidentUser
     - Anyone who creates an account (see :doc:`create-account`)
     - Notifies incidents and sees only the incidents they reported. Once an operator administrator approves
       the account as a member of their operator, those incidents move to that operator.
     - No
     - Incident notification

A **regulator**, also known as competent authority, is a public organisation that supervises one or more regulations.
An **observer** is an organisation that, by law, receives information about incidents to carry out its missions,
read-only; which incidents it receives follows rules set by the platform administrator.
For now, every member of an observer's staff has the ObserverAdmin role.

The security objectives and reporting modules appear only once the platform administrator has enabled them
for your role and, for regulator accounts, for your regulator (see :ref:`functionalities`).
How the platform itself is set up is described in :doc:`/administration/platform-admin/index`.
