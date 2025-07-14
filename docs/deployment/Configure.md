# Configuring and running the deployment
A complete Freva instance will need the following services:

- freva-rest api
- mongoDB server
- MySQL server
- Redis server (optional)
- Data-loader server(s) (optional)
- Web ui app (optional)
- Nginx reverse proxy for connecting to the web ui app (optional)
- Freva client - core - library

:::{tip}
Please consult the [Frequently Asked Questions](faq) guide to see how you can fix known issues.
:::

## Container or Conda-Forge Deployment

Starting with version ``2505.0.0`` of the deployment software, you can choose
how the services are deployed. Two options are supported:

- Container-based deployment using Docker or Podman
- Conda-Forge-based deployment using open-source packages

Unlike Anaconda, the conda-forge channel provides fully open-source packages,
avoiding potential licensing conflicts.


:::{danger}
Versions prior to ``2505.0.0`` supported only Docker/Podman container deployments.

If you're upgrading from a version older than ``2505.0.0`` and wish to switch
to a Conda-based setup, you must first run the deployment software once using
the ``deployment_method=podman`` (or ``docker``) option. This ensures that all
persistent service data is migrated before  switching to the Conda environment.
:::

## Inspecting and adjusting the config
With help of the `deploy-freva config` you can inspect and adjust configuration
values.

{{ cli_config }}

If you want to set config that aren't simply string, bool, int or float
you must follow [toml syntax](https://toml.io/en/)

:::{tip}
To create a new config from the config template you can use the
`deploy-freva config get -r` command and pipe the output into a file:

```console
deploy-freva config get -r > my-new-config.toml
```
:::


## Creating a Compose file ready to go

If you are fine with setting up *all* services on one machine and using
*docker-compose* or *podman-compose* you can create a complete compose file
that contains all the services with help of the compose sub command:

{{cli_compose }}

You can edit and copy the resulting *compose* file and
*systemd service unit* to the target machine, and start it.
This will bring up all micro services necessary to start the freva components.

:::{note}
The `compose` sub command will not log on to any remote machines nor
set up anything else than a docker compose file and if chosen, a systemd
unit file to start the compose service. If you want to use freva core
library with data analysis plugins you will have to install `freva`
from conda-forge:

```console
conda install -c conda-forge freva
```

Once you have installed the core library you will have to adjust the volumes
and ``EVALUATION_SYSTEM_CONFIG_FILE`` environment variable in the ``web-app``
section of your compose file.

:::



## Running the deployment
The command `deploy-freva` opens a text user interface (tui) that will walk
you through the setup of the deployment.
:::{tip}
Navigation is similar to the one of the *nano* text editor.
The shortcuts start with a `^` which indicates `CTRL+`.
:::

Please refer to the [usage of the text user interface section](TuiHowto)
on tui usage instructions.

### Deployment with existing configuration.
Although we recommend you to follow the [deployment tui](TuiHowto) you can also
directly use [toml](http://toml.io) configuration files for setting up the
deployment. Two examples of such deployment configurations can be found
in the [example deployment configuration](Config) section.

If you already have a configuration saved in a toml configuration file you can
issue the `deploy-freva cmd` command:

{{cli_cmd}}

The `--steps` flags can be used if not all services should be deployed.

## Setting the python
Some systems do not have access to python3.4+ (/usr/bin/python3) or git by default.
In such cases you can overwrite the `ansible_python_interpreter` in the inventory
settings of the server section to point ansible to a custom `python3` binary. For example

```
ansible_python_interpreter=/sw/spack-rhel6/miniforge3-4.9.2-3-Linux-x86_64-pwdbqi/bin/python3
```

## Setting up the deployment without root-privileges
Sometimes it can be necessary, either due to security concerns or user rights
restrictions, to set up all services as a un-privileged user. Since version
`v2402.0.0` the deployment routine supports such setup scenarios.

Especially when security is a concern we recommend you to use the `conda` based
deployment instead of `podman` or `docker` for setting up the freva
infrastructure.

Root less installation works essentially just like root based installation. You
only have to either set the `become_user` configuration to a user name that is
different from `root` or leave it blank. In case you leave it blank the login
user will deploy the services. For rootless deployments we always recommend to
use a `conda` based service setup.

Although root-less installation is straight forward it comes with two caveats
that should be kept in mind:

*User based systemd services*: The [systemd](https://systemd.io/) units are not installed system wide but
on user basis, which means that you can access the service using the `--user`
flag: for example:

```console
systemctl status --user freva-web
```

instead of

```console
systemctl status freva-web
```

This also means that in its default configuration systemd will terminate all
running user services as soon as the user terminates a login session.
To avoid this you have to enable 'lingering' states of services for that user:

```console
loginctl enable-linger <USER>
```

This command can only by applied by the root user. Backups are also done as
user instead of system wide basis, you can check the backups after deployment using
the `crontab -l` command.

*No direct access to ports 80 and 443*: The freva web user interface cannot directly be accessed by a web server
listing on port 80 and 443 as those ports are off limits for normal users. If
you choose to deploy the web app as an unprivileged user the apache httpd web
server serving the web app will be running on port 9080 instead of 80 and port
9443 instead of 443. You can either communicate the usage of those  ports to
the users of the system, or **recommended**, set up a simple redirect on
another httpd server that is running on the server where the web app is
deployed. Although this httpd server needs a privileged user it only has to
be configured once. A simple configuration for *apache* httpd looks the following:

```apache
<VirtualHost *:80>
    ServerName my-host
     Redirect permanent / https://www.my-host.org.au:9443
</VirtualHost>

<VirtualHost *:443>
    ServerName my-host
     Redirect permanent / https://www.my-host.org.au:9443
</VirtualHost>
```

This would redirect all traffic from http(s)://www.my-host.org to the
apache httpd container that serves the web app without having the users to
remember the specific ports. Similar configurations are available to other
web server software.


## Version checking
Because the system consists of multiple micro services the software will
perform a version check *before* the deployment to ensure that all versions
fit together. If you for example want to deploy the rest api the system will
also check an update of the freva cli if it finds that the cli library doesn't
fit with the latest version of the rest api. This ensures that all parts of the
system will work together.
:::{tip}
You can disable this version checking by using the
`--skip-version-check` flag. Use this flag with caution.
:::


## Using environment variables
Once the deployment configuration is set up it might be useful to store the
config and all the files that are needed to run the deployment at a central,
yet *secure* location. This can be useful if multiple admins will have to take
turns in (re)-deploying the system and thus the configuration has to be up to
date for those admins. The problem that arises is that the setup might differ
slightly for each person and computer running the deployment. For instance the
`ansible_user` key might differ. For this purpose the deployment supports setting
environment variables. Those environment variables can be used in the configuration
file. Like `ansible_user = $USER`. You can then set up the `USER` variable with
help of the deployment tui. To do so open the main menu (`CTRL+x`) and then
choose the add set variables options (`CTRL+v`). You can then add or edit
variables. In the figure below the `USER` variable is set to a specific user
name. If the deployment encounters an entry using `$USER` variable it will be
replaced by the according value that points to the `$USER` variable.

![Add Variable](_static/Variable.png)

### Relative paths using the $CFD variable
Instead of setting the absolute paths in the configuration files
for example the path to the public certificate files, you should give the
paths *relative* to the configuration file. To indicate that the
freva-deployment machinery should create paths relative to the configuration
you should set all paths starting with the `$CFD` (current file directory)
variable. For example if the configuration file is located in
`/home/user/config/foo/foo.toml` and the public cert file is located in the
same directory as the configuration file then you can set the path to the cert
file in the configuration files via `$CFD/foo.crt`.

This will assure that paths will work from any other machine.

### Stuck in load/save dialogue in the tui?
The load/save forms can be exited by pressing the `<TAB>` key
which will get you to input field at the bottom of the screen. If the input
field has text delete it an press the `<ESC>` key, this will bring you get to
the screen where you started.
