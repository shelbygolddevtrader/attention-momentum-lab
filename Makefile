setup:
	./scripts/bootstrap_mac.sh

test:
	.venv/bin/pytest

check:
	.venv/bin/python -m aml.cli check-account

demo:
	.venv/bin/python -m aml.cli demo --symbol GME --date 2024-05-13
