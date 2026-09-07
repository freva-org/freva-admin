# Configure an Ansible deployment

Start by copying `inventories/example` into a separate, private configuration
repository. Edit `hosts.yml` to assign each Freva component to a host. A single
host may belong to every group, or services may be distributed across hosts.

Configuration is ordinary YAML under `group_vars` and `host_vars`. Use normal
Ansible precedence to keep shared defaults in `group_vars/all`, service values
in service group files, and exceptional values in host files.

## Secrets

Copy `secrets.yml.example` to `secrets.yml`, replace every placeholder, and
encrypt it. The example `.gitignore` pattern prevents the unencrypted filename
from being added accidentally.

```console
ansible-vault encrypt inventories/my-site/group_vars/all/secrets.yml
ansible-vault view inventories/my-site/group_vars/all/secrets.yml
```

Do not generate new credentials during every deployment. Stable credentials
belong to the site configuration and should be rotated explicitly.

## Host groups

| Group | Role |
| --- | --- |
| `core` | Freva client and shared evaluation configuration |
| `db` | MySQL database |
| `vault` | Freva credential service |
| `redis` | Shared REST and data-loader cache |
| `mongodb_server` | Search statistics database |
| `search_server` | Solr index service |
| `freva_rest` | REST API |
| `data_portal_scheduler` | Optional data-loader scheduler |
| `web` | Django web service and its Redis cache |

Remove a host from a group to omit that component. Also adjust dependent host
names and feature flags, such as `freva_rest_data_loader`.

## Safe first run

```console
ansible-inventory -i inventories/my-site/hosts.yml --graph
ansible-playbook -i inventories/my-site/hosts.yml \
  playbooks/deploy.yml --syntax-check
ansible-playbook -i inventories/my-site/hosts.yml \
  playbooks/deploy.yml --ask-vault-pass --check --diff
```

Review image tags, storage paths, ports, and the reported changes before
removing `--check`. Configure public routing and TLS separately as described in
the institution-managed reverse proxy guide.

The Freva core bootstrap is reported but skipped in check mode. It needs files
created by micromamba and the evaluation-system checkout, which Ansible does
not create during a dry run. The normal deployment performs the complete
bootstrap and removes its temporary workspace afterward.

Read-only host checks still run during a dry run. This includes locating
Podman, checking its cgroup version, resolving user IDs, and detecting SELinux.
Service restarts and post-start health checks are skipped because their units
and containers do not exist until the reported changes are applied.

## Deploy selected components

Omit `--tags` for the initial installation or whenever the complete deployment
should be reconciled. For an update to selected components, pass one or more
comma-separated tags:

```console
ansible-playbook -i inventories/my-site/hosts.yml \
  playbooks/deploy.yml --ask-vault-pass --tags web
ansible-playbook -i inventories/my-site/hosts.yml \
  playbooks/deploy.yml --ask-vault-pass --tags cache,mongodb,freva-rest
```

| Tag | Selected component |
| --- | --- |
| `core` | Freva core library |
| `db` | MySQL database |
| `vault` | Vault service |
| `cache` | Redis cache |
| `data-loader` | Optional data-loader scheduler |
| `mongodb` | MongoDB service |
| `search-server` | Solr search service |
| `freva-rest` | Freva REST API only |
| `freva-rest-stack` | Cache, data loader, MongoDB, Solr, and REST API |
| `pre-web` | Web configuration preparation only |
| `web` | Web preparation and web service |

The deprecated `freva_rest` tag remains an alias for `freva-rest-stack` so
existing institution automation continues to work. Inventory validation uses
the special `always` tag and therefore runs for every selection.
