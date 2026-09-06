# Contributing

Changes should preserve the direct Ansible and Helm interfaces. Do not add a
wrapper CLI for configuration, secret generation, or command execution.

Install the upstream development tools, then run:

```console
make check
```

At minimum, a change should pass:

- `ansible-playbook --syntax-check`
- `ansible-galaxy collection build`
- local Compose rendering and YAML parsing
- `helm lint` and `helm template`
- Sphinx documentation with warnings treated as errors
- `git diff --check`

New role variables belong in `defaults/main.yml` and need documentation in the
example inventory. Secrets must have stable names and should never be generated
implicitly during a normal deployment. New Python code is appropriate only for
an application component or a narrowly scoped maintenance tool. Such code must
use complete type annotations, avoid `Any` when a precise type is possible, and
use NumPy-style docstrings for public functions and classes.

Keep institution host names, credentials, storage paths, and cluster settings
out of this public repository.
