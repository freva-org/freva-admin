The freva-deployment software
#############################

The `freva-deployment` software is used to deploy Freva in different computing environments.
The general strategy is to split the deployment into different steps, these are :
- Deploy a MySQL DB server
- Deploy a HashiCorp Vault service for storing and retrieving passwords and
other sensitive data  (this step get automatically activated once the MySQL DB service is set)
- Deploy the `Freva-Rest Server <https://github.com/freva-org/freva-nextgen>`_
The Freva Rest deployment consists of three mandatory and two optional parts:

  - The actual databrowser rest API
  - Apache solr search backend
  - Mongodb to store search statistics
  - Redis server acting as broker (optional)
  - Data-Loader server that provisions data (netCDF, grb, HDF5 etc) via zarr streams over http (optional)

- Deploy command line interface and python library (`freva <https://github.com/freva-org/freva>`_)
- Deploy web front end (`freva_web <https://github.com/freva-org/freva-web>`_)
  The web front end deployment is sub divided into three parts:

  - Deployment of the django web application
  - Deployment of a redis instance acting as database cache
  - Deployment as a apache httpd service as a reverse proxy server for connections from the client to the django web application.


TLDR; Quickstart Guide
----------------------

If you just want to try out **Freva** or experiment with the ``freva-deployment``
tooling, you can install it via ``pip``:

.. code-block:: console

    python -m pip install freva-deployment

To deploy a self-contained version of Freva on your local machine, use the
``deploy-freva cmd`` command with the ``--local`` flag:

.. code-block:: console

    deploy-freva cmd --local

To customise the configuration, generate a new config file and modify it using
the ``deploy-freva config`` subcommands:

.. code-block:: console

    deploy-freva cmd config get -r > freva.toml
    deploy-freva cmd config set project_name clex -c freva.toml
    deploy-freva cmd -c freva.toml --local -g

.. toctree::
   :maxdepth: 2

   Installation
   Configure
   TuiHowto
   webui
   Config
