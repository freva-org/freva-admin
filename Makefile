.PHONY: ansible check compose docs helm vault

check: ansible compose helm vault docs
	git diff --check

ansible:
	ansible-playbook -i inventories/example/hosts.yml playbooks/deploy.yml --syntax-check
	ansible-lint playbooks roles
	ansible-galaxy collection build . --force --output-path build

compose:
	ansible-playbook -i localhost, playbooks/compose.yml -e @examples/compose/vars.yml
	python3 -c 'import pathlib, yaml; yaml.safe_load(pathlib.Path("build/compose.yml").read_text())'

helm:
	helm lint charts/freva --values charts/freva/ci/test-values.yaml
	helm template freva charts/freva --namespace freva --values charts/freva/ci/test-values.yaml > /dev/null

vault:
	python3 -m py_compile vault/runserver.py
	mypy --config-file vault/mypy.ini vault/runserver.py

docs:
	sphinx-build -W --keep-going -b html docs docs/_build/html
