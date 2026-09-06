# Local Compose bundle

Compose is retained for development and automated release-candidate testing. It
is not used to deploy remote hosts.

Edit or generate a normal YAML values file based on
`examples/compose/vars.yml`, then render the bundle locally:

```console
ansible-playbook -i localhost, playbooks/compose.yml \
  -e @examples/compose/vars.yml \
  -e compose_output="$PWD/build/compose.yml"
podman compose -f build/compose.yml config
podman compose -f build/compose.yml up -d
```

The values file groups image references under `compose.images`, so the
development server can create a small override file containing the latest
release-candidate tags:

```yaml
compose:
  images:
    rest: ghcr.io/freva-org/freva-rest-api:2609.0.0rc1
    web: ghcr.io/freva-org/freva-web:2609.0.0rc1
```

Merge that file through Ansible variable precedence or generate a complete
values file in CI. The renderer itself performs no registry lookup and starts no
containers.

Compose uses named volumes because the bundle is disposable. Production state
belongs in `/var/lib/freva` through Quadlet or in Kubernetes PVCs through Helm.
