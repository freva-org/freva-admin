# Freva Helm chart

This chart is the supported Kubernetes deployment interface. Keep cluster
credentials, site-specific values, and secrets in the institution repository.
The public chart contains only reusable workloads and defaults.

Create a namespace and an externally managed Secret, then install the chart:

```console
helm upgrade --install freva ./charts/freva \
  --namespace freva \
  --create-namespace \
  --values values-ncar.yaml
```

Production values should set `secrets.existingSecret`. The referenced Secret
must provide the keys listed by `helm show notes ./charts/freva`. Setting
`secrets.create=true` is intended for disposable development clusters only.

Site storage is added with each component's `existingClaim` setting or with
the `extraVolumes` and `extraVolumeMounts` lists on the REST, data-loader, and
web workloads. This keeps NCAR-specific storage drivers and paths outside the
generic chart.
