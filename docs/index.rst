SERIMA
======


.. only:: html

    .. image:: https://img.shields.io/github/release/informed-governance-project/governance-platform.svg?style=flat-square
        :target: https://github.com/informed-governance-project/SERIMA/releases/latest
        :alt: Latest release

    .. image:: https://img.shields.io/github/license/informed-governance-project/governance-platform.svg?style=flat-square
        :target: https://www.gnu.org/licenses/agpl-3.0.html
        :alt: License

    .. image:: https://img.shields.io/github/stars/informed-governance-project/governance-platform.svg?style=flat-square
        :target: https://github.com/informed-governance-project/SERIMA/stargazers
        :alt: Stars

    .. image:: https://github.com/informed-governance-project/SERIMA/workflows/Python%20application%20tests/badge.svg?style=flat-square
        :target: https://github.com/informed-governance-project/SERIMA/actions?query=workflow%3A%22Python+application+tests%22
        :alt: Workflow

    .. image:: https://readthedocs.org/projects/serima/badge/?version=latest
        :target: https://serima.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status

    .. image:: https://weblate.nc3.lu/widget/serima/svg-badge.svg
        :target: https://weblate.nc3.lu/widget/serima/svg-badge.svg
        :alt: Translation status


.. toctree::
   :caption: User guide
   :maxdepth: 2
   :hidden:

   getting-started/index
   incident-notification/index
   security-objectives/index
   reporting/index
   administration/index

.. toctree::
   :caption: Technical guide
   :maxdepth: 2
   :hidden:

   technical/index

Presentation
------------

SERIMA is developed and maintained by the Luxembourg National Cybersecurity Competence Centre (`NC3 <https://www.nc3.lu>`__)
in the framework of the `Informed Governance Project <https://github.com/informed-governance-project>`_.

It is a governance platform shared by several regulators (competent authorities)
and the operators they supervise. Each regulator configures the regulations it is accountable for,
and the platform offers one module per activity:

- :doc:`incident-notification/index` — operators report incidents to their regulator.
- :doc:`security-objectives/index` — operators declare how they meet their regulator's security objectives.
- :doc:`reporting/index` — regulators build and distribute reports to operators.

This project is developed in partnership with the Institut Luxembourgeois de Régulation (`ILR <https://web.ilr.lu>`_) and the Institut Belge des services Postaux et des Télécommunications (`IBPT <https://www.ibpt.be>`_).

.. figure:: /_static/images/index/home-page.png
   :alt: Screenshot of the list of incidents from the regulator view.
   :target: _static/images/index/home-page.png

   Screenshot of the list of incidents from the regulator view.

Which section do I read?
~~~~~~~~~~~~~~~~~~~~~~~~

- **New to SERIMA:** :doc:`getting-started/index`.
- **Operators and regulators:** the section of the module you work in.
- **Admins:** :doc:`administration/index`, plus the *Configuration* page of each module you configure.
- **Installing or maintaining an instance:** :doc:`technical/index`.

This document is intended for the operators and users of the platform.
If you find errors or omission, please don't hesitate to submit
`an issue <https://github.com/informed-governance-project/SERIMA/issues/new?labels=documentation&template=bug_report.md>`_
or open a pull request with a fix.

Contact
-------

- `NC3 Luxembourg <https://www.nc3.lu>`_ - `info@nc3.lu <info@nc3.lu>`_
- `ILR <https://web.ilr.lu>`_ - `serima@ilr.lu <serima@ilr.lu>`_

License
-------

The Governance Platform is licensed under
`GNU Affero General Public License version 3 <https://www.gnu.org/licenses/agpl-3.0.html>`_.

- Copyright (C) 2023-2026 Juan Rocha <juan.rocha@nc3.lu>
- Copyright (C) 2023-2026 Jérôme Lombardi <jerome.lombardi@nc3.lu>
- Copyright (C) 2023-2026 Cédric Bonhomme <cedric.bonhomme@nc3.lu>
- Copyright (C) 2023-2026 Ruslan Baidan <ruslan.baidan@nc3.lu>
- Copyright (C) 2023-2026 `NC3 Luxembourg <https://www.nc3.lu>`_
