# Operating a Quadlet deployment

Quadlet is the production container deployment method. Ansible writes Podman
Quadlet sources and systemd generates the corresponding services. Docker and
Compose are not used on remote deployment hosts.

## Filesystem layout

Rootful deployments use fixed system paths:

| Purpose | Path |
| --- | --- |
| Persistent state | `/var/lib/freva/<project>/<service>` |
| Generated environment | `/etc/freva/<project>/env/<container>.env` |
| Local environment overrides | `/etc/freva/<project>/env/<container>.local.env` |
| Other service configuration | `/etc/freva/<project>/<service>` |
| Quadlet sources | `/etc/containers/systemd` |
| Quadlet drop-ins | `/etc/containers/systemd/<container>.container.d/*.conf` |

Rootless deployments use the matching XDG locations for the login user:

| Purpose | Path |
| --- | --- |
| Persistent state | `~/.local/state/freva/<project>/<service>` |
| Generated environment | `~/.config/freva/<project>/env/<container>.env` |
| Local environment overrides | `~/.config/freva/<project>/env/<container>.local.env` |
| Other service configuration | `~/.config/freva/<project>/<service>` |
| Quadlet sources | `~/.config/containers/systemd` |
| Quadlet drop-ins | `~/.config/containers/systemd/<container>.container.d/*.conf` |

The TOML `data_path` values are used only by Conda deployments and as a
source for one-time migration. They do not select Quadlet state locations.

## Environment overrides

Deployment rewrites `<container>.env`, which contains values derived from the
TOML configuration. It creates `<container>.local.env` once and never
overwrites it. Quadlet reads the local file last, so values in it take
precedence.

For example, enable the web maintenance page in a rootful deployment:

```console
sudoedit /etc/freva/<project>/env/<project>-web-proxy.local.env
sudo systemctl restart <project>-web-proxy.service
```

Set the following value in the local environment file:

```text
FREVA_MAINTENANCE_MODE=1
```

Use `systemctl --user` and the rootless path for a rootless deployment.

## Quadlet drop-ins

Ansible owns the base `.container` files. Do not edit them because a later
deployment replaces them. Quadlet supports systemd-style drop-ins and the
deployment leaves those files untouched.

The following rootful example pins a locally tested image and adjusts the
restart delay for the database:

```ini
# /etc/containers/systemd/<project>-db.container.d/90-local.conf
[Container]
Image=registry.example.org/freva/mysql:tested
Pull=never

[Service]
RestartSec=15
```

After adding or changing a drop-in, reload systemd and restart the service:

```console
sudo systemctl daemon-reload
sudo systemctl restart <project>-db.service
```

Use the rootless drop-in path and `systemctl --user` for a rootless service.
To inspect the complete generated unit, including drop-ins, run:

```console
systemctl cat <project>-db.service
```

### Moving one service to another filesystem

The fixed `/var/lib/freva` layout is the default. Mounting another filesystem
at that path, or at a service subdirectory, is the simplest override because
the base Quadlet remains unchanged. A Quadlet drop-in can also replace the
bind mounts. Reset the repeated `Volume` key before declaring the complete
replacement list:

```ini
# /etc/containers/systemd/<project>-db.container.d/90-storage.conf
[Container]
Volume=
Volume=/srv/freva/<project>/db/data:/data/db:z
Volume=/srv/freva/<project>/db/logs:/data/logs:z
```

Create the replacement directories with the service ownership before
restarting. On an SELinux host, make the label persistent:

```console
sudo semanage fcontext -a -t container_file_t '/srv/freva/<project>/db(/.*)?'
sudo restorecon -Rv /srv/freva/<project>/db
```

Run the Podman generator in diagnostic mode before restarting if the host has
an older Podman release:

```console
/usr/lib/systemd/system-generators/podman-system-generator --dryrun
```

## SELinux

For rootful deployments, Ansible registers `container_file_t` for the project
state and configuration roots and applies it with `restorecon`. The host must
provide `semanage` when SELinux is enforcing or permissive. On common Fedora
and RHEL systems it is supplied by `policycoreutils-python-utils`.

Bind mounts also use the Podman `:z` option. This is required for rootless
paths and provides a shared label where the web application and proxy use the
same state directory.

## Migration and rollback

When a fixed state directory is empty, deployment looks for the previous
`data_path` directory and the previous Podman named volume. It copies the first
available source into the fixed location and writes a migration marker. It
does not delete the old directory or volume, so it remains available for
rollback.

Docker-managed volumes are outside Podman's storage. Back them up with the old
release and restore them into the appropriate directory under
`/var/lib/freva/<project>` before starting the new service.

## Local development Compose bundle

The `compose` subcommand remains available for development servers that watch
release-candidate images. It renders one local bundle and never installs a
remote runtime or systemd service:

```console
deploy-freva compose -c freva.toml -o ./generated
podman compose -f ./generated/<project>-compose.yml up -d
```

Use Quadlet for deployed production services.
