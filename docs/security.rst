Security Model
==============

First, an overview of the security policy.

Security policy
---------------

Supported Versions
``````````````````

Last stable version of this software always provides security updates.
There will be no security patches for other releases (tagged or not).

Reporting a Vulnerability
`````````````````````````

If you think you have found a potential security issue, do not open
directly a public GitHub issue. Please email us. You can contact
opensource@nc3.lu

You can also specify how you would like to be credited for your finding
(commit message or release notes for the new release). We will
respect your privacy and will only publicize your involvement if you
grant us permission.


Source code
-----------

CodeQL is used to discover vulnerabilities across the **codebase**.

Tools such as *pyupgrade*, *pip-audit*, *GitHub Dependabot* and
secret scanning are used to check for vulnerabilities in project
**dependencies**. Each commit is checked on GitHub. The same kind of tests
are performed locally thanks to `pre-commit <https://pre-commit.com>`_.

Code **quality** is verified with tools such as *black*, *flake8* and *mypy*.

Public security issues are listed
`here <https://github.com/informed-governance-project/SERIMA/issues?q=is%3Aissue+label%3Asecurity+>`_.


Audit on the source code
------------------------



Authentication
--------------

Two factor authentication is available and mandatory for the admin access.
