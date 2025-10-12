.PHONY: dev start lint test tailwind backup restore export-sales install migrate seed

VENV?=.venv
PYTHON?=$(VENV)/bin/python
PIP?=$(VENV)/bin/pip
UVICORN?=$(VENV)/bin/uvicorn

$(VENV):
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

install: $(VENV)

migrate: install
	alembic upgrade head

seed: install migrate
	$(PYTHON) -m app.cli seed --if-empty

dev: install migrate
	export PYTHONPATH=$(PWD) && $(UVICORN) app.main:app --reload --host $${UVICORN_HOST:-127.0.0.1} --port $${UVICORN_PORT:-8000}

start: install migrate seed
	export PYTHONPATH=$(PWD) && $(UVICORN) app.main:app --host $${UVICORN_HOST:-127.0.0.1} --port $${UVICORN_PORT:-8000}

lint: install
	$(PYTHON) -m black app tests
	$(PYTHON) -m isort app tests
	$(PYTHON) -m flake8 app tests

test: install migrate
	export PYTHONPATH=$(PWD) && $(PYTHON) -m pytest

tailwind:
	./bin/tailwindcss -i app/static/css/input.css -o app/static/css/tailwind.css

backup: install
	export PYTHONPATH=$(PWD) && $(PYTHON) -m app.cli backup --output backups/manual-`date +%Y%m%d-%H%M`.zip

restore: install
	export PYTHONPATH=$(PWD) && $(PYTHON) -m app.cli restore $(FILE)

export-sales: install
	export PYTHONPATH=$(PWD) && $(PYTHON) -m app.cli export-sales --activity=$(ACTIVITY) --from=$(FROM) --to=$(TO) --format=$(FORMAT)
