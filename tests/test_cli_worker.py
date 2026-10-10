from typer.testing import CliRunner

from src.cli import app


def test_worker_once_reports_empty_queue(tmp_path):
    result = CliRunner().invoke(app, ["worker", "--once", "--db", str(tmp_path / "worker.db")])
    assert result.exit_code == 0, result.stdout
    assert "No queued job" in result.stdout
