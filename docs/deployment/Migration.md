# Migrate from the Python deployment package

Treat the migration as a configuration transfer, not an in-place software
upgrade. Keep the final 1.x deployment release available until each known site
has moved.

## 1. Record the current installation

Before changing services, record:

- generated Ansible inventory and effective service variables
- all image tags and Conda environment versions
- database, MongoDB, Redis, Vault, OIDC, and web credentials
- certificates and private keys
- persistent directories and container volumes
- host names, ports, ingress, external mounts, and scheduler settings
- backups and a tested restore procedure

Do not generate replacement passwords merely because the configuration format
changed.

## 2. Choose the native target

- Move DWD and FU Berlin style Linux installations to a site-owned Ansible
  inventory. Use Quadlet for container services and keep any required Conda
  roles explicit.
- Move NCAR Kubernetes settings into an NCAR-owned Helm values file and external
  Secret. Keep the generic chart in this repository.
- Keep the Compose renderer only for the development release-candidate server.

## 3. Transfer state

Rootful Quadlet state now defaults to `/var/lib/freva/<project>/<service>`.
The roles can copy known legacy Podman state into the new path without deleting
the source. Docker-managed volumes are not opened by the new deployment. Back
them up with the old runtime and restore the data into the new service path.

Test MySQL and MongoDB backups independently before scheduling the cutover.
Never use a wipe option during a migration rehearsal.

## 4. Rehearse and cut over

Run Ansible in check mode or render Helm output, then deploy into an isolated
test target using copies of production data. Validate data search, REST API,
Vault access, login, web access, and a representative plugin job.

For the final cutover, stop writers, take fresh backups, transfer state, deploy
the pinned release, validate it, and retain the old data until the rollback
window closes.

## Retired features

The custom TOML schema, TUI, `deploy-freva` commands, Docker host deployment,
generated Kubernetes manifests, and six-year-old schema conversion helpers are
not part of the native deployment branch. Historical releases remain the source
for reproducing an old installation while it is being migrated.
