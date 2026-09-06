# Kubernetes with Helm

The Helm chart under `charts/freva` replaces the generated Kubernetes Jinja
manifests. It contains reusable workloads, services, PVC declarations, and an
optional ingress. It does not contain a cluster credential or institution
secret.

Create a site values file in the institution repository:

```yaml
secrets:
  existingSecret: freva-production-secrets

ingress:
  enabled: true
  className: nginx
  hosts:
    - host: freva.example.org
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: freva-production-tls
      hosts:
        - freva.example.org

dataLoader:
  extraVolumes:
    - name: archive
      persistentVolumeClaim:
        claimName: institution-archive
  extraVolumeMounts:
    - name: archive
      mountPath: /data
      readOnly: true
```

Render and review the complete release before applying it:

```console
helm lint charts/freva --values values-site.yml
helm template freva charts/freva \
  --namespace freva \
  --values values-site.yml > rendered.yaml
helm upgrade --install freva charts/freva \
  --namespace freva \
  --create-namespace \
  --values values-site.yml
```

NCAR can migrate the current generated manifests by moving its storage,
ingress, resource, and security settings into an NCAR-owned values file. The
generic chart should remain here so fixes are shared with other installations.

Production deployments should set `secrets.existingSecret`. Chart-managed
secret values are intended only for disposable test clusters.
