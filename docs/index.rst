Freva administration
====================

This repository provides native Ansible and Helm deployment examples for
Freva administrators. It does not install a dedicated deployment CLI.

Use Ansible inventories for Linux hosts, Helm values for Kubernetes, and the
local Ansible renderer for development Compose bundles. Real institution
configuration should live in an institution-owned repository.

.. toctree::
   :maxdepth: 2

   deployment/index
   architecture/index
   after-deployment/index

.. toctree::
   :maxdepth: 1

   faq
   contributing
   whatsnew
