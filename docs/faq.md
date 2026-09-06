# Frequently asked questions

## Do administrators install a Python CLI?

No. Use `ansible-playbook` for hosts and `helm` for Kubernetes. Python is still
needed on Ansible-managed hosts and by the Freva applications themselves, but
there is no Freva deployment command to install.

## Where is persistent Quadlet data?

Rootful state defaults to `/var/lib/freva/<project>/<service>`. Rootless state
defaults to `~/.local/state/freva/<project>/<service>` for the service user.

## Where can I put local changes?

Use `<service>.local.env` for environment changes and
`<service>.container.d/*.conf` for native Quadlet changes. Put repeatable site
versions of those files in the institution inventory repository.

## Why was no service generated for a Quadlet source?

Check cgroup version 2 and run the generator in diagnostic mode:

```console
podman info --format '{{.Host.CgroupsVersion}}'
/usr/lib/systemd/system-generators/podman-system-generator --dryrun
```

Add `--user` for a rootless deployment.

## Should Kubernetes secrets be stored in Helm values?

No for production. Create the Secret with the institution's normal secret
manager and set `secrets.existingSecret` in the site values file.

## Is Compose supported for production?

No. It is a convenient local integration and release-candidate test bundle.
