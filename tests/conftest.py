import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-smoke",
        action="store_true",
        default=False,
        help="run smoke tests",
    )
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="run integration tests",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    run_smoke = config.getoption("--run-smoke")
    run_integration = config.getoption("--run-integration")

    skip_smoke = pytest.mark.skip(reason="need --run-smoke option to run")
    skip_integration = pytest.mark.skip(reason="need --run-integration option to run")
    for item in items:
        if "smoke" in item.keywords and not run_smoke:
            item.add_marker(skip_smoke)
        if "integration" in item.keywords and not run_integration:
            item.add_marker(skip_integration)
