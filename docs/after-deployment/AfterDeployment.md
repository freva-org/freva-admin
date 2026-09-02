# Activation scripts and module files for users
The core deployment will create activation scripts for various shell flavours.
The following activation scripts are located in the `<root_dir>/freva` folder:
* *activate_sh*: To be sourced by shell flavours like shell, bash, zsh etc.
* *activate_csh*: To be sourced by c-shell flavours like csh, tcsh
* *activate_fish*: To be source by fish
* *loadfreva.module*: Modules file
The source scripts can either be copied where they are automatically sourced
or users can be instructed to use the source command for their shell. If
`modules` is available on the host system you can copy the *loadfreva.modules*
file into the `MODULEPATH` location.


# Persisent micro service data:
If you chose Quadlet or conda based deployment of the micro-services
you will have access to a
[systemd unit](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/7/html/system_administrators_guide/chap-managing_services_with_systemd)
of the created service. In general the services can be accessed by
`<project_name>-<service_name>.service` If for example the `project_name`
key was set to `clex-ces` then the following services are created:

- database: `clex-ces-db.service`, `clex-ces-vault.service`
- freva-rest: `clex-ces-freva-rest.service` `clex-ces-mongo.service`
- web ui: `clex-ces-web.service` `clex-ces-web-cache.service` `clex-ces-web-proxy.service`
- data-loader: `freva-caching.service` `data-loader@scheduler.service` `data-loader@worker.service`

The data-loader services for zarr streaming are optional. The
`clex-ces-web-proxy.service` unit is present when the reverse proxy is enabled.

To get an overview over how things are started and controlled you can use
the `list-units` and `cat` directives to find and inspect the service in
question. For example to see how the `web` services is stated you can use
the following commands:

```console
systemctl list-units "*web*"
systemctl cat clex-ces-web.service
```

:::{note}
If you have set up the services as an unprivileged user you need
to access the services with help of the ``--user`` flag for example:

```console
systemctl --user restart clex-ces-web.service
```
:::

## Access of service data on the host machine

### Environment variables
All services are configured via environment variables. Conda environment files
are located in `<data_path>/<project_name>/<service>.env`. Rootful Quadlet
environment files are generated in `/etc/freva/<project>/env`. Rootless files
are generated in `~/.config/freva/<project>/env`. They have mode `0600`
because they can contain secrets.

Each Quadlet container also reads `<container>.local.env` after its generated
file. The deployment creates the local file once and does not overwrite it.

#### Web maintenance mode

If the web-app is not available due to upstream service or disk failure a
maintenance mode can be enabled. This can be realised by setting the

- `FREVA_MAINTENANCE_MODE=1`

in `<project>-web-proxy.local.env` and
restarting the proxy via `systemd`. The nginx reverse proxy then displays a
message that the system is currently unavailable. The application containers
can remain running. Once the services are fully available
again the entry can be set back to `FREVA_MAINTENANCE_MODE=0` and the web
proxy can be restarted with
`systemctl restart <project_name>-web-proxy.service`.


### Conda-forge base deployments
The data of the services, like the database or databrowser cores
should be persistent. The default location for all the service data
is `/opt/freva` or whatever folder was set as `data_path` variable.
The following logic applies:

- `<data_path>/<project_name>/services/<project_name>/<service_name>/`

for example:

- `/opt/freva/clex-ces/services/db/`

The conda environments are stored in:

- `<data_path>/<project_name>/conda`

for example:

- `/opt/freva/clex-ces/conda`

### Quadlet deployment
Persistent data for rootful Quadlet deployments is stored in normal host
directories below `/var/lib/freva/<project>/<service>`. Rootless deployments
use `~/.local/state/freva/<project>/<service>`. These paths can be backed up
with standard filesystem tools without inspecting Podman storage.

The Quadlet source files are located in `/etc/containers/systemd` for rootful
deployments and `~/.config/containers/systemd` for rootless deployments. Their
generated services are managed with `systemctl` or `systemctl --user`.

See [Operating a Quadlet deployment](../deployment/Quadlet) for drop-ins,
environment overrides, SELinux labels, and storage path overrides.


## Simple backup scripts:
Services with persistent data - `db`, `mongo` and `solr` offer a very simple
backup script.

Depending on the chosen deployment method this backup is either executed directly on the
host machine (conda-forge based deployment) or in a container.

If you have `anacron` installed on your host machine then a cron script to
automatically backup databases and solr cores is applied nightly.
By default the script keeps the last 7 backups.
For conda-forge base deployments the backup data can be found in:

```bash
<data_path>/<project_name>/services/<service>/backup
```
For rootful Quadlet deployments, place backups below:

```bash
/var/lib/freva/<project_name>/<service>/backup
```

Rootless deployments use the corresponding path below
`~/.local/state/freva`.

This is only a rudimentary backup solution, ideally you should transfer those
backups regularly to a different location. You can also disable this
rudimentary backup strategy by deleting the backup scripts in `/etc/cron.daily`
and replace it by a more sophisticated backup mechanism.


:::{important}
If you have set up the services as an unprivileged user you can
access the backup scripts using the `crontab` command.
:::


(the-web-ui-admin-panel)=
## The web UI admin Panel

The web user interface is managed by django which offers a powerful admin
panel to manage users, user history and add additional links as so called
flat pages. More information on the django admin panel can be found
[online](https://www.tutorialspoint.com/django/django_admin_interface.htm).
To access the admin panel you will first have to login as user `freva-admin`
using the *master* password you've created during deployment. Once logged in
as freva-admin you should navigate to `/admin` of your homepage. For example
`https://www.clex.nci.org.au/admin` assuming the web page url is
`https://www.clex.nci.org.au`. Here you can transfer admin rights to other
users, like your user name. Or create
[new flat-pages](https://docs.djangoproject.com/en/4.0/ref/contrib/flatpages/).
Flat-pages are useful to create additional project specific information that
can be displayed on the website. This information can be links to plugin
documentation or legal notes (see below).


## Adding privacy notes and terms of conditions to the Web UI
For some incitations it might be necessary to add legal statements on privacy
and terms of usage. Those statements can be added as flat-pages in the django
*admin* panel. All flat-pages starting with the url **/legal** for example
`/legal/privacy/` will be added as a link to the footer of home page. Examples
of the content of such flat-pages can be found in the [Appendix](LegalNotes).
