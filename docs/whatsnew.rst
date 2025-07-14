.. _whatsnew:

What's new
===========

.. toctree::
   :maxdepth: 0
   :titlesonly:

v2507.3.0
~~~~~~~~~
* Enable sub command that creats a single docker-compose file for deployment


v2507.2.0
~~~~~~~~~
* Do not install freva via pip
* Enable stac

v2507.1.0
~~~~~~~~~
* Bump core, rest-api, web versions
* Enable stac api

v2507.0.0
~~~~~~~~~
* Fix CSRF issues
* Update docs

v2505.0.3
~~~~~~~~~
* Move source code.

v2505.0.0
~~~~~~~~~
* Introduced ``conda-forge`` based deployment.
  Instead of soley relying on deploying the micro-services within
  docker containers. The servers can be set up with help of conda-forge
  environments.
* More flexibility for setting up micro-services.
* Internal playbook restructuring.

v2410.0.3
~~~~~~~~~
* bug-fixes in ci and furnish readthedocs

v2410.0.0
~~~~~~~~~
* Add a routine to reset the mongo root password
* Add mongo user data facet validator

v2408.0.1
~~~~~~~~~
* Some bug-fixes.


v2408.0.0
~~~~~~~~~
* Add zarr-streaming deployment.
* Implement openid-connect for authentication.


v2407.3.0
~~~~~~~~~
* Bumped version of freva_rest to 2407.0.0



v2407.2.2
~~~~~~~~~
* Improve error messages for too small tui terminal windows.
* Small bug fixes in build pipeline.



v2407.2.1
~~~~~~~~~
* Introduce new ``cmd`` sub command to ``deploy-freva`` cli.
* Build pre-built binaries.


v2407.1.0
~~~~~~~~~
* Add flag to skip version checks.
* Improve root less deployment.
* Add healthcheck scripts.



v2407.0.0
~~~~~~~~~
* Improve local dev (debug) deployment mode.
* Improve rootless deployment.

v2406.0.2
~~~~~~~~~
* Bug fixing mariadb



v2406.0.1
~~~~~~~~~
* Keep track of mariadb version

v2406.0.0
~~~~~~~~~
* Add info panel (access via CTRL+f) for further information on config items.
* Bug fix reset mariadb root password script.



v2405.1.1
~~~~~~~~~
* Minor bug fixing.



v2405.1.0
~~~~~~~~~
* Bumped version of freva core to 2406.0.0



v2405.0.0
~~~~~~~~~
* Bumped version of freva_rest to 2403.0.3



v2404.0.0
~~~~~~~~~
* Bumped version of django_evaluation to 2405.0.0




v2403.2.0
~~~~~~~~~
* Bumped version of databrowserAPI to 2403.0.3



v2403.1.0
~~~~~~~~~
* Bumped version of databrowserAPI to 2403.0.2




v2403.0.5
~~~~~~~~~
*  A new procedure to check the correct versions of all micro services has
   been added
*  Unprivileged users (non-root) can now also deploy the system with all
   services.
*  For better testing a setup script that create separate VM to deploy the
   micro services has been added.

v2309.0.0
~~~~~~~~~

* All containers are created with `docker-compose` or `podman-compose` in order to be able to successfully deploy
  the containers you will have to install `docker-compose` or `podman-compose` on
  the host machines running the containers.
* With v2309 comes a new configuration file. If you are using the tui please
  just load your old config file. The code will update this configuration file.
  If you are using the `deploy-freva-cmd` command you will not have to do anything.
  The code automatically update your config file to the new config file. A backup
  with the suffix (`.bck`) will be created.
