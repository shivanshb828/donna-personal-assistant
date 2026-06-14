import pytest

# Auto-mode so every async test runs without needing @pytest.mark.asyncio explicitly.
pytest_plugins = ("pytest_asyncio",)


def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: mark test as async")
