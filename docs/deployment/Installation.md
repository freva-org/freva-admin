# Installation

No Freva deployment package needs to be installed. Clone or vendor this
repository and install the upstream tools needed for the selected target.

## Host deployment

The Ansible controller needs Git, `ansible-core`, and the collections required
by your institution inventory. Managed Linux hosts need Python 3 and systemd.
Quadlet hosts additionally need Podman with Quadlet support and cgroup version
2.

```console
git clone https://github.com/freva-org/freva-admin.git
cd freva-admin
ansible-playbook --version
podman info --format '{{.Host.CgroupsVersion}}'
```

Rootful deployments need privilege escalation. Rootless deployments should log
in directly as the service user. Do not use `become_user` to simulate rootless
Quadlet because the generated user units belong to the login user's systemd
manager.

## Kubernetes deployment

Install a Helm 3 release supported by your cluster and a compatible `kubectl`.
The chart currently declares Kubernetes 1.27 or newer.

```console
helm lint charts/freva
helm template freva charts/freva --namespace freva
```

Helm does not need access to the Ansible inventory.

## Documentation tools

Building this documentation uses Python-based Sphinx tooling, but that is a
documentation build dependency and not a Freva deployment CLI.
