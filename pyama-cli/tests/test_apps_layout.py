from pyama_cli import app as package_app
from pyama_cli.apps import app as apps_app
from pyama_cli.apps import modeling, processing, statistics, visualization
from pyama_cli.main import app as main_app


def test_cli_entrypoints_share_the_same_app() -> None:
    assert package_app is apps_app
    assert main_app is apps_app


def test_cli_domain_modules_register_expected_commands() -> None:
    assert hasattr(processing, "register_commands")
    assert hasattr(statistics, "register_commands")
    assert hasattr(modeling, "register_commands")
    assert hasattr(visualization, "register_commands")
