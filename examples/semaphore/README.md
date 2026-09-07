# Semaphore UI with Quadlet

This example runs a single Semaphore UI container with SQLite. It is intended
for a one-server evaluation. Semaphore listens on the host loopback interface,
leaves TLS and reverse-proxy configuration to the administrator, and persists
its application data below `/var/lib/semaphore`.

The Kerberos configuration is a Quadlet drop-in. The ticket cache is kept under
`/run` because a Kerberos ticket is ephemeral authentication material, not
persistent application data.

## Requirements

- A Podman release that supports `.build` Quadlets
- Quadlet and cgroup version 2
- Network and DNS access from the container to the KDC and managed hosts
- `openssl` on the host for generating the Semaphore encryption key

Check the host before installing the files:

```console
podman info --format '{{.Host.CgroupsVersion}}'
man podman-build.unit
```

## Install the configuration

Copy the example files to their system locations:

```console
sudo install -D -m 0644 Containerfile /etc/semaphore/Containerfile
sudo install -D -m 0600 semaphore.env.example /etc/semaphore/semaphore.env
sudo install -D -m 0644 kerberos.env /etc/semaphore/kerberos.env
sudo install -D -m 0644 ssh_config.example /etc/semaphore/ssh/config
sudo install -D -m 0644 semaphore.build /etc/containers/systemd/semaphore.build
sudo install -D -m 0644 semaphore.container /etc/containers/systemd/semaphore.container
sudo install -D -m 0644 semaphore.container.d/10-kerberos.conf \
  /etc/containers/systemd/semaphore.container.d/10-kerberos.conf
```

Edit `/etc/semaphore/semaphore.env` and `/etc/semaphore/ssh/config` for the
institution. Populate `/etc/semaphore/ssh/known_hosts` from a trusted source.
Do not accept host keys gathered with `ssh-keyscan` without independently
checking their fingerprints.

Copy the host Kerberos configuration instead of relabelling the original file:

```console
sudo install -D -m 0644 /etc/krb5.conf /etc/semaphore/krb5.conf
```

Create the secret files. The admin password file must contain only the initial
Semaphore administrator password. Do not commit either file.

```console
sudo install -d -o root -g root -m 0750 /etc/semaphore/secrets
sudo sh -c 'umask 027; openssl rand -base64 32 > /etc/semaphore/secrets/access-key-encryption'
sudoedit /etc/semaphore/secrets/admin-password
sudo chown root:root /etc/semaphore/secrets/*
sudo chmod 0640 /etc/semaphore/secrets/*
```

The access-key encryption value protects credentials stored by Semaphore. Keep
a secure backup and do not replace it after creating credentials.

## Validate and start

Reloading systemd invokes the Quadlet generator. Inspect generator failures
before starting the service:

```console
sudo systemctl daemon-reload
sudo systemd-analyze --generators=true verify semaphore.service
sudo systemctl start semaphore.service
sudo systemctl status semaphore.service semaphore-build.service
sudo journalctl -u semaphore.service -f
```

The `[Install]` section makes the generated service start during boot. Generated
Quadlet services are not enabled with `systemctl enable`.

Use an SSH tunnel during the evaluation:

```console
ssh -L 3000:127.0.0.1:3000 semaphore-host
```

Then open `http://127.0.0.1:3000` locally.

## Test Kerberos from the container

Obtain a ticket interactively. The password is sent to `kinit` and is not stored
in the Quadlet or Semaphore database:

```console
sudo podman exec -it semaphore kinit USER@REALM
sudo podman exec semaphore klist
sudo podman exec semaphore \
  ssh -o GSSAPIAuthentication=yes USER@service-vm.example.org true
```

Semaphore forwards `KRB5CCNAME` to Ansible task processes, so jobs use the same
credential cache. Run `kinit` again when the ticket expires. For unattended
operation, request a restricted automation principal and keytab instead of
storing a human Kerberos password.

The HPC core inventory should use its own Semaphore login/password credential.
It should connect directly as the core service account and set
`core_ansible_become_user` to an empty string.

## Update Semaphore

Change the pinned upstream image in `/etc/semaphore/Containerfile`, then rebuild
and restart deliberately:

```console
sudo systemctl restart semaphore-build.service
sudo systemctl restart semaphore.service
```

Test database migrations and Ansible compatibility before updating a production
instance.
