# Contributing

We welcome contributions from the community! Before you start contributing,
please follow these steps to set up your development environment.
Make sure you have the following prerequisites installed:

- Python (>=3.x)
- Git
- Make

```console
git clone https://github.com/freva-org/freva-admin.git
cd freva-admin.git
make
```

The deployment routine is supposed to interact with the user - this can
can be asking for user names or passwords. To avoid such interaction you can
set the following environment variables.

- `MASTER_PASSWD`: the admin/root password for all services (db, web etc)
- `EMAIL_USER`: the user name for email server login credentials
- `EMAIL_PASSWD`: the password for email server login credentials
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

:::{note}
*Before* running the script you will have to install [qemu](https://www.qemu.org/docs/master/).
The script has only been tested on Linux systems.
:::

You can then make use of the pre configured inventory file in
`assets/share/freva/deployment/config/inventory.toml`. In order to deploy
freva on the newly created VM you will have to instruct ansible to use
ssh port 2222 instead of 22.

The following command will install freva along all with it's components to
the local VM:

```console
deploy-freva-cmd  assets/share/freva/deployment/config/inventory.toml --gen-keys --ssh-port 2222
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

This will check the current version of the `main` branch and  trigger
a GitHub continuous integration pipeline to create a new release. The procedure
performs a couple of checks, if theses checks fail please make sure to address
the issues.
