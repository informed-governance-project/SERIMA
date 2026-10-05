:orphan:

..
   Start page of the PDF only (latex_documents in conf.py); the website starts at index.rst.
   The PDF places each document where its toctree is, so the presentation comes first,
   then the guides, then the contact and license. Nothing above the toctrees may be a
   section, or every guide would become a subsection of it.

SERIMA
======

.. rubric:: Presentation

.. include:: _include/presentation.rst.inc

.. toctree::
   :maxdepth: 2

   getting-started/index
   incident-notification/index
   security-objectives/index
   reporting/index
   administration/index
   technical/index

.. include:: _include/contact-license.rst.inc
