# Configuration ownership

The repository intentionally has no global Freva deployment configuration
file. Configuration ownership follows the target tool:

| Concern | Linux host | Kubernetes | Local Compose |
| --- | --- | --- | --- |
| Hosts | Ansible inventory | cluster context | localhost |
| Service values | group and host variables | Helm values | Compose values YAML |
| Secrets | Ansible Vault | external Secret | disposable test values |
| TLS | inventory-managed files | TLS Secret | local proxy settings |
| Storage | `/var/lib/freva` and inventory overrides | PVC values | named volumes |
| Local overrides | env and Quadlet drop-ins | site values and overlays | extra values file |

The example inventory is executable documentation, not a universal default.
Copy it to an institution repository and review every value.

Image tags should be updated explicitly and as one tested set. Avoid an
unattended `latest` policy in production. The `latest` values in public examples
mark images whose release version was previously discovered dynamically by the
retired Python package.
