Web UI for Freva Deployment
===========================

This section describes how to install and configure the automation bootstrap
script for managing Freva deployments via `Prefect <https://docs.prefect.io/v3/get-started>`
and Ansible.

Quick Installation
------------------

To bootstrap the automation stack, run:

.. code-block:: bash

   export FREVA_AUTOMATION_PREFIX_DIR=automation
   curl -sSL https://raw.githubusercontent.com/freva-org/freva-admin/refs/heads/main/automation/automation-setup.py | python

.. note::
   You need **Python ≥ 3.10** available on the system.

The environment variable ``FREVA_AUTOMATION_PREFIX_DIR`` defines the directory where everything (e.g. conda environment, logs, scripts) will be installed.

Systemd Unit
------------

The bootstrap script creates a systemd unit file in the prefix directory:

.. code-block:: ini

   [Unit]
   Description=Automated freva deployments
   After=network.target

   [Service]
   Type=simple
   NoNewPrivileges=true
   SendSIGKILL=no
   KillSignal=SIGTERM
   PermissionsStartOnly=true
   ExecStart=<PREFIX>/conda/bin/python automation-setup.py
   StandardOutput=journal
   StandardError=journal
   Environment="PATH=<PREFIX>/conda/bin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin"
   EnvironmentFile=<PREFIX>/setup.conf
   WorkingDirectory=<PREFIX>/automation
   Restart=on-failure
   # User=<set user for security>
   # Group=<set group for security>

You can customize this unit file and install it to either user or
system scope using ``systemctl --user enable --now`` or ``sudo systemctl enable --now``.

Configuration
-------------

The automation behavior is configured via an
environment file (default: ``<PREFIX>/setup.conf``), supporting the following variables:

.. code-block:: ini

   # Where it the Web Ui deployed
   FREVA_AUTOMATION_PREFIX_DIR=/opt/freva/automation
   # Custom location where hook script are located
   FREVA_AUTOMATION_SCRIPT_DIR=/opt/freva/dkrz-deployments/automation
   # User name that is allowed to log into the reverse proxy web site
   FREVA_AUTOMATION_USERNAME=my-user
   # Password for that user
   FREVA_AUTOMATION_PASSWORD=secret
   # Path to the key/cert pair for the web server (optional)
   FREVA_AUTOMATION_CERT_FILE=/opt/freva/automation/freva-automation.crt
   FREVA_AUTOMATION_KEY_FILE=/opt/freva/automation/freva-automation.key
   # Extra conda packges that should be installed (maybe for hook scripts)
   FREVA_AUTOMATION_EXTRA_PKGS=
   # Port the WebUI is running on (can be 443 or 8443)
   FREVA_AUTOMATION_SERVER_PORT=8443
   # Comma separated deployment configs, can also be set in <FREVA_AUTOMATION_PREFIX_DIR>/automation.toml
   FREVA_DEPLOYMENT_CONFIG=/opt/freva/dkrz-deployments/instances/freva-dev/freva-dev.toml,...
   # Home of the user running the web server
   HOME=/home/myuser
   # Default (fallback) user name that should log into the remote servers
   ANSIBLE_USER=myuser
   # Additional variables can be set and are passed to the deployment hooks.
   VAULT_MASTER_PASS=secret

.. note::
   If no ``FREVA_AUTOMATION_CERT_FILE`` or ``FREVA_AUTOMATION_KEY_FILE`` are provided, a self-signed TLS certificate will be generated automatically.

Deployment Hooks
----------------

The directory defined by ``FREVA_AUTOMATION_SCRIPT_DIR``
can contain arbitrary ``*.sh``
scripts that are executed **before** each deployment starts.

If you want to send back environment variables into the deployment procedure
you can add variables to the ``FREVA_AUTOMATION_ENV_FILE`` variable.

For example, to clone configuration repositories or
inject secrets into the automation environment. For example:

.. code-block:: bash

   #!/usr/bin/env bash
   this_dir=$(dirname $(readlink -f $0))
   cd $this_dir
   echo "Adding env vars to ${FREVA_AUTOMATION_ENV_FILE:-}"
   if [ "${FREVA_AUTOMATION_ENV_FILE:-}" ]; then
       for var in $(ansible-vault view secret-vars.conf --vault-password-file <(echo "${VAULT_MASTER_PASS}")); do
           echo "" >> "${FREVA_AUTOMATION_ENV_FILE}"
           echo "$var" >> "${FREVA_AUTOMATION_ENV_FILE}"
           echo "" >> "${FREVA_AUTOMATION_ENV_FILE}"
       done
   fi

This assumes an existing `vault-encrypted <https://docs.ansible.com/ansible/latest/cli/ansible-vault.html`
file named ``secret-vars.conf``.

Using Prefect
-------------

The automation script sets up a **Prefect orchestration server** behind
a Caddy reverse proxy (with HTTPS). Prefect provides:

- a modern web UI for managing and monitoring deployments
- scheduling via cron or manual triggering
- log viewing and status tracking
- multi-user access

This is especially valuable when **multiple administrators** collaborate on
managing Freva deployments: each admin can trigger or monitor deployments
without logging into individual servers or manually invoking Ansible.

The combination of Prefect and Ansible ensures that:

- deployments are reproducible and versioned
- logs and errors are accessible in one place
- tasks can be scheduled centrally (e.g. nightly testing or auto-updates)

A secure web interface is served on the port
defined by ``FREVA_AUTOMATION_SERVER_PORT`` (default: 8443),
with basic authentication controlled
via ``FREVA_AUTOMATION_USERNAME`` and ``FREVA_AUTOMATION_PASSWORD``.
