.. freva-deployment documentation master file, created by
   sphinx-quickstart on Tue Mar  1 16:19:20 2022.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

The freva admin documentation!
==============================

.. image:: architecture/_static/freva_flowchart-new.png
   :width: 320
   :align: center



Freva, the free evaluation system framework, is a data search and analysis
platform developed by the atmospheric science community for the atmospheric
science community. With help of Freva researchers can:

- quickly and intuitively search for data stored at typical data centers that
  host many datasets.
- create a common interface for user defined data analysis tools.
- apply data analysis tools in a reproducible manner.

Data analysis is realised by user developed data analysis plugins. These plugins
are code agnostic, meaning that users don't have to rewrite the core of their
plugins to make them work with Freva. All that Freva does is providing a user
interface for the plugins.

Currently Freva comes in three different flavours:

- a python module that allows the usage of Freva in python environments, like
  jupyter notebooks
- a command line interface (cli) that allows using Freva from the command
  lines and shell scripts.
- a web user interface (web-ui)


This documentation gives an overview over the installation process of Freva
as well as it's configuration, maintenance and administration. It
mainly covers the deployment process and the usage of a dedicated deployment
software that was tailored to make the installation process of Freva somewhat
more simple.

Because Freva is a software that is meant to run on HPC type distributed systems
this documentation first gives an overview of various deployment strategies.
After this section a basic configuration that is necessary to make the different
components of Freva work with each other is introduced. This is followed by a
documentation on how to install the Freva deployment software. After this section
basic deployment setup and servicing Freva will be introduced.

.. tip::

    Please check :ref:`whatsnew` for any update announcements. Consult the
    :doc:`FAQ section <faq>` for fixing known issues.




.. toctree::
   :maxdepth: 2

   architecture/index

.. toctree::
   :maxdepth: 2

   deployment/index
.. toctree::
   :maxdepth: 2

   after-deployment/index

.. toctree::
   :maxdepth: 1

   faq
   whatsnew
   contributing
