.PHONY: install test lint format run demo

install:
	python -m pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check .
	ruff format --check .
	mypy src/watchtower

format:
	ruff check --fix .
	ruff format .

run:
	watchtower serve --no-notifications

demo:
	watchtower demo
