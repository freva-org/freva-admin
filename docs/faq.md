(faq)=
# Frequently Asked Questions (FAQ)

Welcome to the FAQ section of the freva admin documentation.
Here you'll find answers to common questions, troubleshooting tips,
and practical guidance related to setting up, configuring, and
running the Freva framework.

Whether you're deploying services with Quadlet, Conda, or Kubernetes, this page
helps resolve typical installation and operation issues.

This section is actively maintained and expands over time as new questions
arise from users and developers. If your question isn't covered yet,
feel free to open an issue or contribute a new entry.

## Topics covered

- Service initialization problems
- Database and storage configuration
- Container runtime compatibility
- Secrets and environment variable handling
- Version pinning and updates
- Integration with monitoring and orchestration tools

---
## Why was no service generated for my `.container` file?

Run the Podman systemd generator in diagnostic mode and inspect its output:

```console
/usr/lib/systemd/system-generators/podman-system-generator --dryrun
```

For rootless services, add `--user`. Quadlet requires cgroup version 2, which
can be checked with `podman info --format '{{.Host.CgroupsVersion}}'`.


## 📦 Where are logs and persistent data stored?
Depending whether you've chosen a `conda-forge` or Quadlet based
deployment approach your logs data data will be located in different locations:

- `conda-forge`:
    All data will be stored in `<data_dir>/<project_name>/services/<service>`
- `quadlet`:
    Rootful data is stored in
    `/var/lib/freva/<project_name>/<service>`. Rootless data is stored in
    `~/.local/state/freva/<project_name>/<service>`.


## 💥 Can't inject secrets into vault.
If secret injection fails but the `<project_name>-vault` is up and running you can
check the logs. In most cases there will be a version mismatch of the a older deployed
version and the current vault version. To overcome this stop the service and delete
the data:

For `conda-forge` based deployments:
```console
rm -r <data_dir>/<project_name>/services/vault
```
Or for Quadlet:
```console
systemctl stop <project_name>-vault.service
rm -r /var/lib/freva/<project_name>/vault/data
```
