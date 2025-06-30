# Example deployment configuration

This section contains two working versions of a full deployment configuration.
These configuration files have also been installed along with the deployment.
You can find them in the data files under `share/freva/deployment/config` of your
python environment, for example:
 - `/usr/share/freva/deployment/config` for system wide installations.
 - `$CONDA_PREFIX/share/freva/deployment/config` for conda based installations.
 - `~/.local/share/freva/deployment/config` for user based installations.

 ## Typical deployment
 The `inventory.toml` file contains a typical setup for freva. The services
 are installed with root privileges on remote machines. The core is installed
 under a normal user on a login node of a HPC system.

 {{toml_config}}
