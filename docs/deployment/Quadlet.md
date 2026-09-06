# Podman Quadlet

Quadlet is the supported production container path on Linux hosts. Ansible
writes declarative `.container` and `.network` sources, then systemd's Quadlet
generator creates the services. Docker is not required or invoked.

## Persistent paths

Rootful installations use:

| Purpose | Default |
| --- | --- |
| Persistent service state | `/var/lib/freva/<project>/<service>` |
| Generated configuration | `/etc/freva/<project>/<service>` |
| Generated environment | `/etc/freva/<project>/env` |
| Quadlet sources | `/etc/containers/systemd` |

The root paths are controlled by `freva_rootful_state_root` and
`freva_rootful_config_root`. Keep persistent state out of `/tmp`, `/run`, and
other ephemeral filesystems.

Rootless installations use
`~/.local/state/freva/<project>` and `~/.config/freva/<project>`. Run Ansible as
the service user and enable lingering when services must survive logout:

```console
sudo loginctl enable-linger freva
systemctl --user daemon-reload
systemctl --user status freva-web.service
```

## Operator drop-ins

Every rendered container loads a generated environment file followed by an
operator-owned `.local.env` file. Ansible creates the latter once with mode
`0600` and does not overwrite it.

Quadlet source drop-ins are also supported. For a source named
`freva-web.container`, add a file such as:

```ini
# /etc/containers/systemd/freva-web.container.d/50-local.conf
[Service]
MemoryMax=8G

[Container]
Environment=HTTP_PROXY=http://proxy.example.org:3128
```

Apply a structural drop-in with:

```console
sudo systemctl daemon-reload
sudo systemctl restart freva-web.service
```

Keep institution-managed drop-ins in the private inventory repository and copy
them with a small site role or playbook. The public roles deliberately do not
delete files in the `.container.d` and `.network.d` directories.

Set `freva_rootful_state_root` in the site inventory when the whole installation
must use a different state root. This keeps directory creation, ownership,
mounts, and SELinux labels consistent. A service-specific drop-in can add an
institution mount without changing the generated source:

```ini
# /etc/containers/systemd/freva-data-loader.container.d/30-archive.conf
[Container]
Volume=/srv/archive:/data/archive:ro,z
```

Create and label `/srv/archive` in the site playbook before reloading systemd.
The additional mount does not replace the service's generated state mounts.

## SELinux

For a rootful installation, the roles register the configured state and config
roots as `container_file_t` using `semanage fcontext`, then run `restorecon`.
This makes the label persistent across relabel operations. The target host must
provide `semanage`, commonly through `policycoreutils-python-utils` or the
distribution equivalent.

Volume specifications still use `:z` or `:Z` where container sharing semantics
require them. Inspect local policy before adding site storage outside the Freva
roots.

## Diagnostics

```console
podman info --format '{{.Host.CgroupsVersion}}'
/usr/lib/systemd/system-generators/podman-system-generator --dryrun
systemctl status freva-web.service
journalctl -u freva-web.service
```

Use `--user` for generator and systemd commands in a rootless deployment.
