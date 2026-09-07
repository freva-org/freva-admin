Deployment guide
================

Choose one production interface:

* Ansible with Podman Quadlet for Linux services
* Ansible with Conda for services that cannot run as containers
* Helm for Kubernetes clusters

Compose is retained only for local integration and release-candidate testing.

.. toctree::
   :maxdepth: 2

   Installation
   Configure
   Quadlet
   ReverseProxy
   Kubernetes
   Compose
   Config
   Migration
