(faq)=
# Frequently Asked Questions (FAQ)

Welcome to the FAQ section of the freva admin documentation.
Here you'll find answers to common questions, troubleshooting tips,
and practical guidance related to setting up, configuring, and
running the Freva framework.

Whether you're deploying services with Docker, Podman, or Conda environments, this page is here to help resolve typical issues and clarify common concerns encountered during the installation and operation phases.

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
## 🐳 Why is `docker compose` failing with "command not found"?
If you're using Docker but `docker compose` fails, it's likely that the
Docker Compose plugin isn't installed.
Modern Docker uses `docker compose` (with a space),
not `docker-compose` (hyphen).

- On Debian/Ubuntu:
  ```console
  sudo apt install docker-compose-plugin
  ```
- On RHEL/AlmaLinux
   ```console
   sudo dnf install docker-compose-plugin
   ```
If you're using Podman, ensure podman-compose is installed and available
in your $PATH.


## 📦 Where are logs and volumes stored?
Depending whether you've chosen `conda-forge` based or a `docker/podman` based
deployment approach your logs data data will be located in different locations:

- `conda-forge`:
    All data will be stored in `<data_dir>/<project_name>/services/<service>`
- `podman/conda`:
    The data will be located in container volumes managed by the container engine
    checkout
    ```console
    docker volume ls
    docker volume inspect <project_name>-<service>_data
    ```
    Or using `podman` if the service was deployed with podman.


## 💥 Can't inject secrets into vault.
If secret injection fails but the `<project_name>-vault` is up and running you can
check the logs. In most cases there will be a version mismatch of the a older deployed
version and the current vault version. To overcome this stop the service and delete
the data:

For `conda-forge` based deployments:
```console
rm -r <data_dir>/<project_name>/services/vault
```
Or for `podman/docker`:
```console
docker volume rm -f <project_name>-vault_data
```
