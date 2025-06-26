# Installing freva-deployment
This section gives an overview over how to install the deployment software for
freva.

The main work will be done by [ansible](https://docs.ansible.com/ansible/latest/index.html),
hence some level of familiarity with ansible is advantageous but not necessary.
Since we are using ansible we can use this deployment routine from any workstation
computer (like a Mac-book). You do not need to run the deployment on the
machines where things get installed. The only requirement is
you can establish ssh connections to the servers via openSSH.

:::{note}
In most cases openSSH clients should be available on your local machine.
Windows users may refer to the [openSSH install page](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_install_firstuse?tabs=gui)
for setting up openSSH on windows.
:::

There are different ways to install the deployment software:

## 1. Using pre-built binaries.
You can download the pre-built binaries for your specific OS and architecture
from the [release page](release:{{version}}).

### Available Binaries

- **Linux**
  - [amd64](exe:linux-x64.tar.gz)
  - [arm64](exe:linux-arm64.tar.gz)
  - [armv7](exe:linux-armv7.tar.gz)
  - [ppc64le](exe:linux-ppc64le.tar.gz)
  - [s390x](exe:linux-s390x.tar.gz)
  - [i386](exe:linux-i386.tar.gz)


- **macOS**
  - [arm64](exe:osx-arm64.tar.gz)

After downloading version {{version}} file for your operating system and
architecture, extract the binaries to a meaningful location such as
`~/.local/deploy-freva`:

```console
tar xzf deploy-freva-v{{version}}-linux-x64.tar.gz -C ~/.local
ln -s ~/.local/deploy-freva/deploy-freva ~/.local/bin/
```

If you have `~/.local/bin` in you `PATH` variable you can use the `deploy-freva`
command.


## 2. Installation via pip.
If you're using Linux, OsX or a Windows subsystem for Linux (WSL) you can
use *pip* to install the deployment software:

```console
python3 -m pip install -U freva-deployment
```

This command installs ansible and all required python packages.

:::{warning}
On *CentOS* python SELinux libraries need to be installed.
You will need to install libselinux for your CentOS version.

```console
python3 -m pip install libselinux-python3
```
:::

## 3. Using docker

A pre-built docker image is available to run the deployment

```console
docker run -it -v /path/to/config:/opt/freva-deployment:z ghcr.io/freva-org/freva-deployment
```
The `-it` flags are important in order to interact with the program. To use
and save existing configurations you can mount the directories of the config
files into the container.


## Commands after installation:
The deployment software consists of *three* different sub-commands:
- `deploy-freva`: Main deployment command via text user interface (tui).
- `deploy-freva cmd`: Run already configured deployment.
- `deploy-freva migrate`: Command line interface to manage project migration from
   old freva systems to new ones.

### Main text user interface command
{{ cli_tui }}

### Command for running pre defined configs
{{ cli_cmd }}

:::{tip}
Installing all services can take a considerable amount of time.
If you wish to install only a specific microservice, the `deploy-freva cmd`
subcommand provides the `--tag` flag to select which tasks should be executed.
:::


### Command for migrating old freva instances
{{ cli_mig }}
