# Deployment of the Free Evaluation Framework Freva

[![Documentation Status](https://readthedocs.org/projects/freva-deployment/badge/?version=latest)](https://freva-deployment.readthedocs.io/en/latest/?badge=latest)

The code in this repository is used to deploy freva in different computing
environments. The general strategy is to split the deployment into
4 different steps, these are :
- Deploy MariaDB service via docker
- Deploy a Hashicorp Vault service for storing and retrieving passwords
  and other sensitive data via docker
  (this step get automatically activated once the MariaDB service is set)
- Deploy [Databrowser API](https://github.com/freva-org/freva-netxgen) service via docker
- Deploy command line interface backend ([evaluation_system](https://github.com/freva-org/freva))
- Deploy web front end ([freva_web](https://github.com/freva-org/freva-web))


> ``💡`` A vault server is auto deployed once the mariadb server is deployed.
The vault centrally stores all passwords and other sensitive data.
During the deployment of the vault server a public key is generated which is
used to open the vault. This public key will be saved in the `evaluation_system`
backend root directory. Only if saved this key and the key in the vault match,
secrets can be retrieved. Therefore it might be a good idea to deploy,
the mariadb server (and with it the vault) and the `evaluation_system`
backend together.

On *CentOS* python SELinux libraries need to be installed. If you choose to
install ansible via the `install_ansible` you'll have to use `conda` to
install libselinux for your CentOS version.
For example : `conda install -c conda-forge  libselinux-cos7-x86_64`

# Pre-Requisites

The main work will be done by [ansible](https://docs.ansible.com/ansible/latest/index.html),
hence some level of familiarity with ansible is advantageous but not necessary.
Since we are using ansible we can use this deployment routine from any workstation
computer (like a Mac-book). You do not need to run the deployment on the
machines where things get installed. The only requirement is
you can establish ssh connections to the servers via openSSH.

> ``💡`` In most cases openSSH clients should be available on your local machine.
> Windows users may refer to the
> [openSSH install page](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_install_firstuse?tabs=gui)
> for setting up openSSH on windows.



# Installation
There are different option to install the deployment software.

## 1. Using pre-built binaries.
You can download the pre-built binaries for your specific OS and architecture
from the [release page]((https://github.com/freva-org/freva-deployment/releases).

### Available Binaries

- **Linux**
  - amd64 (`linux-x64`)
  - arm64 (`linux-arm64`)
  - armv7 (`linux-armv7`)
  - ppc64le (`linux-ppc64le`)
  - s390x (`linux-s390x`)
  - i386 (`linux-i386`)

- **Windows**
  - amd64 (`windows-x64`)

- **macOS**
  - amd64 (`macos-x64`)
  - arm64 (`macos-arm64`)

After downloading and extracting the zip file for your operating system and architecture,
you can run the `deploy-freva` command.

```console
Usage: deploy-freva [-h] [-v] [-V] [--cowsay] {cmd,migrate} ...

Run the freva deployment

Positional Arguments:
  {cmd,migrate}
    cmd          Run deployment in batch mode.
    migrate      Utilities to handle migrations from old freva systems.

Options:
  -h, --help     show this help message and exit
  -v, --verbose  Verbosity level (default: 0)
  -V, --version  show program's version number and exit
  --cowsay       Let the cow speak! (default: False)
```

## 2. Installation via pip.
If you're using Linux, OsX or a Windows subsystem for Linux (WSL) you can
use *pip* to install the deployment software:

```console
python3 -m pip install -U freva-deployment
```

This command installs ansible and all required python packages.
> ``💡`` On *CentOS* python SELinux libraries need to be installed.
> You will need to install libselinux for your CentOS version.

```console
python3 -m pip install libselinux-python3
```
## 3. Using docker

A pre-built docker image is available to run the deployment

```console
docker run -it -v /path/to/config:/opt/freva-deployment:z ghcr.io/freva-org/freva-deployment
```
The `-it` flags are important in order to interact with the program. To use
and save existing configurations you can mount the directories of the config
files into the container.


## Sub Commands after installation:
The deployment software consists of *three* different sub-commands:
- `deploy-freva`: Main deployment command via text user interface (tui).
- `deploy-freva cmd`: Run already configured deployment.
- `deploy-freva migrate`: Command line interface to manage project migration from
   old freva systems to new ones.

> ``💡`` You can use the `-l` flag of the `deploy-freva cmd` command
or tick the *local deployment only* box in the setup page of the text user
interface if you only want to try out the deployment on your local machine.
Without having to install anything on remote machines.





## Installing docker-compose/podman-compose and sudo access to the service servers
Because the services of MariaDB, DatabrowserAPI and Apache httpd will be deployed
on docker container images, docker needs to be available on the target servers.
Since version *v2309.0.0* of the deployment the containers are set up
using `docker-compose`. Hence `docker-compose` (or `podman-compose`) has to be
installed on the host systems. Usually installing and running docker
requires *root* privileges. Hence, on the servers that will be running docker
you will need root access. There exists an option to install and run docker
without root, information on a root-less docker option
can be found [on the docker docs](https://docs.docker.com/engine/security/rootless/)
> ``💡`` Some systems use `podman` instead of `docker`. The deployment
routine is able to distinguish and use the right service.

## Version checking
Because the system consists of multiple micro services the software will
perform a version check *before* the deployment to ensure that all versions
fit together. If you for example want to deploy the rest api the system will
also check an update of the freva cli if it finds that the cli library doesn't
fit with the latest version of the rest api. This ensures that all parts of the
system will work together.
> ``💡`` You can disable this version checking by using the
  `--skip-version-check` flag. Use this flag with caution.


# Configuring the deployment
A complete freva instance will need the following services:

- solrservers (hostname of the apache solr server)
- dbservers (hostname of the MariaDB server)
- webservers (hostname that will host the web site)
- backendservers (hostname(s) where the command line interface will be installed)

Two typical server topography could look the following:
| ![](docs/Topography.png) |
|:--:|
| *Two different server structures*. In setup I the services are running on the same host that serve 4 docker containers. The backend is installed on a hpc login node with access to a gpfs/lustre file system. Setup II deploys the MariaDB, Solr services and the website on dedicated servers. The command line interfaces are also deployed on independent servers.|
---

## Setting the python and git path
Some systems do not have access to python3.6+ (/usr/bin/python3) or git by default.
In such cases you can overwrite the `ansible_python_interpreter` in the inventory
settings of the server section to point ansible to a custom `python3` bindary.
For example

```
ansible_python_interpreter=/sw/spack-rhel6/miniforge3-4.9.2-3-Linux-x86_64-pwdbqi/bin/python3
```

The same applies to the path to the git binary:

```
git_path=/sw/spack-levante/git-2.31.1-25ve7r/bin/git
```

# Running the deployment
After successful configuration you can run the deployment.
The command `deploy-freva` opens a text user interface (tui) that will walk
you through the setup of the deployment.
The tui allows to edit, save, load and run a configuration file

> ``💡`` Navigation is similar to the one of the *nano* text editor.
> The shortcuts start with a `^` which indicates `CTRL+`.
> * the pop up menus (e.g. `Exit`) must be navigated pressing `tab` to
> select the options and then `Enter`.
> * the configuration files must be saved as a `.toml` as the tui
> only recognises this extension.
> * to paste with the mouse (\*nix style), double middle click.


## Unique identifiers via a domain flag
Different freva instances are installed across different institutions. Usually
the different freva instances running at an institution are distinguished by
a unique project name associated with each freva instance for example `xces`.
To make the project names unique across institutions (domains) a domain flag
should be set for the deployment. For example all freva instances running at
the German Climate Computing Centre will get the `dkrz` domain flag while freva
instances running at Free Uni Berlin get the `fub` domain flag. This allows for
easy identification of the right freva instance for remote servicing.
Please remember to set the correct domain flag for `deployment`, `servicing` and
`migration` of an old freva system.

## Deployment with existing configuration.
If you already have a configuration saved in a toml base inventory file you can
issue the `deploy-freva cmd` sub-command:

```console
deploy-freva cmd --help                                                                                                                                      (python3_12)
Usage: deploy-freva cmd [-h] [--config CONFIG] [--steps {web,core,db,freva-rest,auto} [{web,core,db,freva-rest,auto} ...]] [--ask-pass] [--ssh-port SSH_PORT] [-v] [-l]
                        [-g] [--skip-version-check] [-V] [--cowsay]

Run deployment in batch mode.

Options:
  -h, --help            show this help message and exit
  --config, -c CONFIG   Path to ansible inventory file. (default: /home/wilfred/.anaconda3/envs/python3_12/share/freva/deployment/inventory.toml)
  --steps, -s {web,core,db,freva-rest,auto} [{web,core,db,freva-rest,auto} ...]
                        The services/code stack to be deployed. Use auto to only deploy outdated services (default: ['db', 'freva-rest', 'web', 'core'])
  --ask-pass            Connect to server via ssh passwd instead of public key. (default: False)
  --ssh-port SSH_PORT   Set the ssh port, in 99.9% of the cases this should be 22 (default: 22)
  -v, --verbose         Verbosity level (default: 0)
  -l, --local           Deploy services on the local machine, debug purpose. (default: False)
  -g, --gen-keys        Generate public and private web certs, use with caution. (default: False)
  --skip-version-check  Skip the version check. Use with caution. (default: False)
  -V, --version         show program's version number and exit
  --cowsay              Let the cow speak! (default: False)
```

The `--steps` flags can be used if not all services should be deployed.

# Known Issues:
Below are possible solutions to some known issues:

### SSH connection fails:

```python
fatal: [host.name]: FAILED! => {"msg": "Using a SSH password instead of a key is not possible because Host Key checking is enabled and sshpass does not support this.  Please add this host's fingerprint to your known_hosts file to manage this host."}
```
- This means that you've never logged on to the server. You can avoid this error message by simply logging on to the server for the first time.

### Playbook complains about refused connections for the solr or db playbook

```python
fatal: [localhost]: FAILED! => {"changed": true, "cmd": "docker run --name \"test_ces_db\" -e MYSQL_ROOT_PASSWORD=\"T3st\" -p \"3306\":3306 -d docker.io/library/mariadb", "delta": "0:00:00.229695", "end": "2021-05-27 16:10:58.553280", "msg": "non-zero return code", "rc": 125, "start": "2021-05-27 16:10:58.323585", "stderr": "docker: Error response from daemon: driver failed programming external connectivity on endpoint test_ces_db (d106bf1fe310a2ae0e012685df5a897874c61870c5241f7a2af2c4ce461794c2): Error starting userland proxy: listen tcp4 0.0.0.0:3306: bind: address already in use.", "stderr_lines": ["docker: Error response from daemon: driver failed programming external connectivity on endpoint test_ces_db (d106bf1fe310a2ae0e012685df5a897874c61870c5241f7a2af2c4ce461794c2): Error starting userland proxy: listen tcp4 0.0.0.0:3306: bind: address already in use."], "stdout": "895ba35cdf5dcf2d4ec86997aedf0637bf4020f2e9d3e5775221966dcfb820a5", "stdout_lines": ["895ba35cdf5dcf2d4ec86997aedf0637bf4020f2e9d3e5775221966dcfb820a5"]}
```
- This means that there is already a service running on this port - in this case a local mariadb service. To avoid this error chose a different port in your `config/inventory` file.

### Playbook cannot create database tables because connections fails

```python
fatal: [localhost]: FAILED! => {"changed": false, "msg": "ERROR 1698 (28000): Access denied for user 'root'@'localhost'\n"}
```
- This is a common problem if you've set the mariadb docker host to be localhost. You can avoid the problem by setting the `db_host` variable to a non localhost type IP like 172.17.0.1. If you're not sure what IP to use try the following command
```
docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' db_docker_name
```
you can figure out the `db_docker_name` using the following command:
```
docker container ls
```

### Git related unit tests in core playbook fail
Git pull and push commands tend to fail if you haven't configured git. In this case change into the /tmp/evaluation_system directory of the host that runs the playbook
then manually trigger the unit tests by

```
FREVA_ENV=/path/to/root_dir make tests
```
You can then check the stderr for messages for git related issues. Usually it helps to configure git before hand:

```bash
git config --global init.defaultBranch main
git config --global user.name your_user
git config --global user.email your@email.com
```


# Advanced: Adjusting the playbook
Playbook templates and be found the in the `playbooks` directory. You can also add new variables to the playbook if they are present in the `config/inventory` file.

# Contributing to freva-deployment

We welcome contributions from the community! Before you start contributing,
please follow these steps to set up your development environment.
Make sure you have the following prerequisites installed:

- Python (>=3.x)
- Git
- Make

```console
git clone https://github.com/freva-org/freva-deployment.git
cd freva-deployment.git
make
```

The deployment routine is supposed to interact with the user - this can
can be asking for user names or passwords. To avoid such interaction you can
set the following environment variables.

- `MASTER_PASSWD`: the admin/root password for all services (db, web etc).
- `EMAIL_USER`: the user name for email server login credentials.
- `EMAIL_PASSWD`: the password for email server login credentials.
- `ANSIBLE_BECOME_PASSWORD`: the password used in any *sudo* command.

These environment variables have only an effect when the deployment is
applied in debug or local mode using the `-l` flag.

## Using a local VM for testing.
A test freva instance can be deployed on a dedicated local virtual machine.
This virtual machine is based on a minimal ubuntu server image and has
docker and podman pre installed. To create the virtual machine simply
run the following script.

```console
cloud-init/start-vm.sh -h
```

```bash
Usage: start-vm.sh [-k|--kill], [-p|--port PORT]
Create a new virtual machine (VM) ready for freva deployment.
Options:
  -k, --kill     Kill the virtual machine
  -p, --port     Set the port of the service that is used to configure the VM default: 8000
```

> ``💡`` *Before* running the script you will have to install [qemu](https://www.qemu.org/docs/master/).
> The script has only been tested on Linux systems.

You can then make use of the pre configured inventory file in
`assets/share/freva/deployment/config/inventory.toml`. In order to deploy
freva on the newly created VM you will have to instruct ansible to use
ssh port 2222 instead of 22.

The following command will install freva along all with it's components to
the local VM:

```console
deploy-freva-cmd  --config assets/share/freva/deployment/config/inventory.toml --gen-keys --ssh-port 2222
```

If you want to tear down the created VM you can either press CTRL+C in the
terminal where you created the VM or use the kill command:

```console
./cloud-init/start-vm.sh -k
```

## Development Workflow

To install the code in development mode use:
```console
make
```

Unit tests, building the documentation, type annotations and code style tests
are done with [tox](https://tox.wiki/en/latest/). To run all tests, linting
in parallel simply execute the following command:

```console
tox -p 3
```
You can also run the each part alone, for example to only check the code style:

```console
tox -e lint
```
available options are ``lint``, ``types``, ``test`` and ``docs``.

Tox runs in a separate python environment to run the tests in the current
environment use:

```console
pytest
```

To reformat and do type checking:
```console
make lint
```
### Creating a new release.

Once the development is finished and you decide that it's time for a new
release of the software use the following command to trigger a release
procedure:

```console
tox -e release
```

This will check the current version of the `main` branch and trigger
a GitHub continuous integration pipeline to create a new release. The procedure
performs a couple of checks, if theses checks fail please make sure to address
the issues.
