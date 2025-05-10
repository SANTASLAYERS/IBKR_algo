.PHONY: lint run-dev test test-unit test-subscription

lint:
	/home/pangasa/.local/bin/mypy src api_client tests
	/home/pangasa/.local/bin/ruff check src api_client tests
	/home/pangasa/.local/bin/black --check src api_client tests

format:
	/home/pangasa/.local/bin/black src api_client tests

run-dev:
	python3 main.py

test:
	python3 -m pytest

test-unit:
	python3 -m pytest tests/test_subscription_manager.py -v

test-subscription:
	python3 -m pytest tests/test_persistent_subscription.py -v

test-heartbeat:
	python3 -m pytest tests/test_heartbeat.py -v