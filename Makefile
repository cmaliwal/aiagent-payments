# Makefile for AI Agent Payments SDK

.PHONY: test lint format isort lint-all clean

install:
	pip install -r requirements.txt
	pip install isort

lint:
	flake8 .

lint-all:
	flake8 .
	isort --check .

isort:
	isort .

format:
	isort .
	black .

test:
	pytest tests/ -v

example:
	python examples/basic_usage.py

clean:
	rm -rf __pycache__ .pytest_cache *.pyc *.pyo *.egg-info 