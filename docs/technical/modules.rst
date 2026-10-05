Modules
=======

SERIMA is a Django application made of a core and three modules:

- **Governance platform** (``governanceplatform``): users, authentication, regulators, observers, operators,
  sectors and regulations, the administration console, and access to the modules.
- **Incident notification** (``incidents``): operators notify incidents to their regulators through
  configurable workflows of reports; regulators review them, and observers receive the incidents
  their forwarding rules select.
- **Security objectives** (``securityobjectives``): operators declare how they meet a regulator's
  framework of security objectives, and regulators review the declarations.
- **Reporting** (``reporting``): regulators build report projects, import MONARC risk analyses,
  and generate DOCX and PDF reports for operators.

Incident notification is available to every regulator, operator and observer.
Security objectives and reporting are gated by the platform administrator in two steps:
a module must be enabled for the user's role and, for regulator accounts, for their regulator.
See :doc:`/getting-started/roles-and-permissions` and :ref:`functionalities`.
