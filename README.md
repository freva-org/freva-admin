# Freva deployment

This repository contains reusable deployment examples for Freva. There is no
Freva-specific installer or Python command line interface. Administrators use
the tools they already operate:

| Target | Supported interface | Site-owned configuration |
| --- | --- | --- |
| Linux hosts | `ansible-playbook` | inventory, group variables, Vault files |
| Kubernetes | `helm` | values files, Secrets, ConfigMaps |
| Local integration | `ansible-playbook` plus Compose | development values |

Podman Quadlet is the production container path on Linux hosts. Docker is not
used by the host deployment. The Compose renderer remains available for local
integration and release-candidate testing.

## Repository layout

- `playbooks/deploy.yml` deploys host services with Quadlet or Conda.
- `roles/` contains the reusable Ansible roles.
- `inventories/example/` documents an all-in-one host installation.
- `charts/freva/` is the generic Kubernetes Helm chart.
- `playbooks/compose.yml` renders the development Compose bundle locally.
- `docs/` contains the administrator and migration guides.

An institution should keep its real inventory, encrypted secrets, certificates,
host names, and storage settings in a separate repository. For example, NCAR
can keep only its chart values and Kubernetes Secret integration in the NCAR
repository while consuming the chart from this repository.

## Host quick start

Install Ansible on the administrator workstation and copy the example inventory:

```console
cp -a inventories/example inventories/my-site
cp inventories/my-site/group_vars/all/secrets.yml.example \
  inventories/my-site/group_vars/all/secrets.yml
ansible-vault encrypt inventories/my-site/group_vars/all/secrets.yml
```

Replace the documentation host, certificate placeholders, image tags, and site
settings. Inspect the effective inventory before deploying:

```console
ansible-inventory -i inventories/my-site/hosts.yml --graph
ansible-playbook -i inventories/my-site/hosts.yml \
  playbooks/deploy.yml --syntax-check
ansible-playbook -i inventories/my-site/hosts.yml \
  playbooks/deploy.yml --ask-vault-pass --check --diff
ansible-playbook -i inventories/my-site/hosts.yml \
  playbooks/deploy.yml --ask-vault-pass
```

Rootful Quadlet state is stored under `/var/lib/freva/<project>` and generated
configuration under `/etc/freva/<project>`. The root directories can be changed
with inventory variables. Rootless services use the service user's XDG state
and configuration directories.

Ansible creates two operator-owned override mechanisms:

- `/etc/freva/<project>/env/<service>.local.env` for environment settings
- `/etc/containers/systemd/<service>.container.d/*.conf` for native Quadlet
  drop-ins

These files are not overwritten on later Ansible runs. After changing one, run
`systemctl daemon-reload` when needed and restart the affected service.

On SELinux systems the roles persistently label the configured Freva state and
configuration roots as `container_file_t`, then apply those labels with
`restorecon`. Install the package providing `semanage` before deployment.

## Kubernetes quick start

Create a site values file and an externally managed Secret. The Secret keys are
listed in `charts/freva/templates/NOTES.txt`.

```console
helm lint charts/freva
helm template freva charts/freva \
  --namespace freva \
  --values values-site.yml
helm upgrade --install freva charts/freva \
  --namespace freva \
  --create-namespace \
  --values values-site.yml
```

The chart supports existing PVCs and arbitrary extra volumes and mounts for
institution storage. This allows the public chart to stay generic while the
site repository owns storage classes, paths, ingress, credentials, and release
policy.

## Local Compose renderer

Render a development bundle without contacting a remote host:

```console
ansible-playbook -i localhost, playbooks/compose.yml \
  -e @examples/compose/vars.yml \
  -e compose_output="$PWD/build/compose.yml"
podman compose -f build/compose.yml up -d
```

CI can override individual image values with another YAML file or `-e` values.
The Compose path is not intended for production state management.

## Legacy deployments

The former `freva-deployment` Python package, custom TOML configuration, TUI,
Docker host path, and schema migration helpers are retired on this branch. The
last 1.x release should remain available as a frozen migration reference.
Existing installations should first record their generated Ansible inventory,
service credentials, persistent paths, certificates, and current image tags,
then move those values into a site-owned Ansible inventory or Helm values file.

See the [migration guide](docs/deployment/Migration.md) before changing a live
installation.

## Development

Run the same checks as CI:

```console
make check
```

The check suite validates Ansible syntax, builds the collection, renders the
development Compose file, lints and renders the Helm chart, and builds the
documentation. It also type-checks the Python code used by the Vault
application. There is no Python deployment entrypoint.

Freva deployment is licensed under the BSD 3-Clause license.
