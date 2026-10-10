from typer.testing import CliRunner

from src.cli import app


def test_jobs_submit_status_cancel(tmp_path):
    runner = CliRunner()
    db = str(tmp_path / "jobs.db")
    submitted = runner.invoke(app, ["jobs", "submit", "cafe", "Tehran", "--idempotency-key", "k1", "--db", db])
    assert submitted.exit_code == 0, submitted.stdout
    job_id = submitted.stdout.split("'")[1]
    status = runner.invoke(app, ["jobs", "status", job_id, "--db", db])
    assert status.exit_code == 0 and "State: queued" in status.stdout
    cancelled = runner.invoke(app, ["jobs", "cancel", job_id, "--db", db])
    assert cancelled.exit_code == 0 and "cancelled" in cancelled.stdout
