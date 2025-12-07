from tasksgodzilla.cli.client import APIClient
from tasksgodzilla.cli.tui import TuiDashboard


def test_tui_instantiates() -> None:
    client = APIClient(base_url="http://localhost:8011")
    app = TuiDashboard(client)
    assert app.client is client
    assert any(binding.key == "r" for binding in app.BINDINGS)
