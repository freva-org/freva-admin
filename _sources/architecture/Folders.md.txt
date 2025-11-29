# Basic Freva configuration

Because the framework consists of multiple parts, Freva has to be configured
to work with those different parts. This is especially true for the web ui
and the `evaluation_system` core running on an HPC system. The central
building block of the freva configuration is the `evaluation_system.conf`
configuration file. This file holds information on the server infrastructure,
that is host names for apache solr and mariadb servers, project specific
information like project name and the directory structure.

This part of the documentation will emphasis on the directory structure, which
is important for the interplay of the `evaluation_system` core and the web ui.

The content of the initial `evaluation_system.conf` file looks like the
following:

```ini
[evaluation_system]
# Freva - Free Evaluation System Framework configuration file
# This file contains the necessary configuration information
# which is needed to run Freva
#
# Username(s) - comma separated - of the admins of the project
admins=
#
# An informative project name
project_name=freva
# The url the Freva web ui can be accessed with
project_website=

# Main configuration path of the Freva instance default to the etc dir
# of the python environment
root_dir=
#
# The location of the work directory for is user specific data
base_dir_location=${root_dir}/freva_output
#

#: Type of directory structure that will be used to maintain state:
#:
#:    local   := <home>/<base_dir>...
#:    central := <base_dir_location>/<username>/<base_dir>...
#:
directory_structure_type=central

# The directory name of the <base_dir> (only used if `directory_structure_type`
# is set to central - defaults to `project_name`
base_dir=${project_name}

# Workload manager configuration
# Workload manager system - currently the following workload manager systems are
# available: local (no workload manager), lsf, moab, oar, pbs, sge, slurm
scheduler_system=local
# The directory where temporary job scripts are created
scheduler_input_dir=/tmp/${scheduler_system}_output
# The output directory where stdout/stderr of the jobs are stored
scheduler_output_dir=${base_dir_location}/share/${scheduler_system}_output

# The directory data where preview data (images etc) for the web ui
# is stored.
preview_path=${base_dir_location}/share/preview
# The number of processes used to convert images created by plugins
# for display in the web ui.
number_of_processes=6

#: Path to the directory where users can add an share project specific data
project_data=${base_dir_location}/data/crawl_my_data


#: database path

#: mySQL settings
db.host=

#: Define access to the solr instance
solr.host=
solr.port=8989
solr.core=files

#shellinabox
#shellmachine=None
#shellport=4200

# Workload manager job configuration
# NOTE: The options are workload manager agnostic - except of the
# extra_options flag: which must be in accordance to the utilized
# workload manager.
[scheduler_options]
#partition=
#memory=256GiB
#queue=gpu
#project=ch1187
#walltime=08:00:00
#cpus=12
##Additional options (specific to the workload manager)
#extra_options=--qos=test, --array=20

#[plugin:animator]
#python_path=${evaluation_system:root_dir}/plugins/animator
#module=animator
```

The configuration file is written in [`.ini` format](https://en.wikipedia.org/wiki/INI_file).
The main sections are `evaluation_system` for configuring the behaviour of the
core and `scheduler_options` for configuring the workload manager options.
Plugins are configured via the `plugin:<plugin_name>`.

## Configuring the `evaluation_system` section
The following gives an overview of the most important keys to be configured
in the `evaluation_system` section:

- *admins*: comma separated list of username(s) that are administering the
  instance of the Freva. Admins have more rights in the framework, like
  crawling *all* user data.
- *project_name*: Name of this specific Freva instance, for example `clex-ces`
   which would be the central evaluation system (ces) for the clex project.
- *root_dir*: The `root_dir` is directory that holds additional Freva related
   configuration. By default this folder is the path prefix of the python
   distribution where Freva is installed to. If you're using multiple instances that share
   a common python (anaconda) environment this directory will distinguish the instances.
   For example two projects *project_a* and *project_b* share a Freva installation
   which is installed into `$HOME/anaconda/freva` then *project_b* would get its
   configuration by setting the `root_dir` to `/path/to/project_b` where
   the `evaluation_system.conf` file would be located in
   `/path/to/project_b/freva/evaluation_system.conf` the same applies to
   `project_a`
- *directory_structure_type*: This key specifies where the user output is stored.
  *Two* different types are possible: *local* will store the plugin output in the
  home directory of the user. *central* will store the plugin
  output in a central location with each username as the first child directory.
  For example `/path/to/project/work/<username>`.
- *base_dir_location*: This is the path where the user output for the plugins
  are stored. This key has only an effect if the `directory_structure_type` is
  set to central.
- *scheduler_system*: Plugin jobs can either run interactively or in batch mode,
  for batch mode a number of different workload manager systems are available.
  The following workload managers are implemented: lsf, moab, oar, pbs, sge,
  slurm, local. If local is chosen, the plugin job is directly executed on
  the login node, similar to an interactive job. This means that load
  balancing for local jobs is not available.
- *preview_path*: The path to the directory holding the user content,
   like plots, for display in the web ui. ``💡`` after plugin application, display
   content of the plugin output will be copied to this directory. The default
   location of this directory `<base_dir_location>/share/preview`
- *db.host*: The host name where database and vault are running.
- *solr.host*, *solr.core*, *solr.port*: The apache solr connection information.
  ``💡`` The *solr.core* variable might be subject to removal in the future.
  Therefore it is recommended to set this variable to its default value: *files*.

(eval-conf)=
## Configuring the `scheduler_options` section
All workload managers are configured via the `scheduler_options` section. The
following configuration keys are available:

- *queue*:  Destination queue for each worker job.
- *project*: Accounting string associated with each worker job.
- *walltime*: Walltime for each worker job.
- *cpus*:   Number of cpus to book in each job node.
- *memory*: Amount of memory to request in for each job.
- *extra_options*: Additional workload manager specific options (comma separated).
