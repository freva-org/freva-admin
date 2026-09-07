.PHONY: ansible check compose docs helm vault

check: ansible compose helm vault docs
	git diff --check

ansible:
	ansible-playbook -i inventories/example/hosts.yml playbooks/deploy.yml --syntax-check
	ansible-playbook -i localhost, tests/ansible/check-mode-core.yml --check
	ansible-lint playbooks roles tests/ansible
	ansible-galaxy collection build . --force --output-path build

compose:
	ansible-playbook -i localhost, playbooks/compose.yml -e @examples/compose/vars.yml
	python3 -c 'import pathlib, yaml; yaml.safe_load(pathlib.Path("build/compose.yml").read_text())'
	! rg -n 'freva-nginx|web-reverse-proxy' build/compose.yml

helm:
	helm lint charts/freva --values charts/freva/ci/test-values.yaml
	mkdir -p build
	helm template freva charts/freva --namespace freva --values charts/freva/ci/test-values.yaml > build/helm.yml
	! rg -n 'freva-nginx|name: proxy|kind: Ingress|kind: Gateway' build/helm.yml

vault:
	python3 -m py_compile vault/runserver.py
	mypy --config-file vault/mypy.ini vault/runserver.py

docs:
	sphinx-build -W --keep-going -b html docs docs/_build/html
