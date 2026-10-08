import json

import typer

from .config import Settings
from .errors import ApifyError, SearchAttemptPersistenceError
from .results import RunStatus
from .service import SearchLeadsService
from .storage import LeadStore

app = typer.Typer(help="Collect, score, and export local business leads.")
campaign_app = typer.Typer(help="Create and inspect lead campaigns.", no_args_is_help=True)
jobs_app = typer.Typer(help="Submit and control local jobs.", no_args_is_help=True)
app.add_typer(campaign_app, name="campaign")
app.add_typer(jobs_app, name="jobs")


@app.command("worker")
def worker_once(
    once: bool = typer.Option(True, "--once/--loop", help="Process one job or keep polling."),
    worker_id: str = typer.Option("local-worker", "--worker-id"),
    db: str | None = typer.Option(None, "--db"),
) -> None:
    import sqlite3
    from .execution.handlers import places_handler
    from .execution.worker import JobWorker
    from .migrations import migrate
    settings = Settings(database_path=db or Settings().database_path)
    with sqlite3.connect(settings.database_path) as connection:
        migrate(connection)
        processed = JobWorker(connection, worker_id).run_once(places_handler(SearchLeadsService(settings)))
    if processed is None:
        typer.echo("No queued job")
    else:
        typer.echo(f"Processed job '{processed.job_id}' ({processed.state})")


@app.command()
def search(
    query: str,
    location: str,
    source: str = typer.Option("places", help="places"),
    limit: int = typer.Option(20, min=1),
    campaign: str | None = typer.Option(None, "--campaign", help="Campaign ID"),
    db: str | None = None,
) -> None:
    settings = Settings(database_path=db or Settings().database_path)
    service = SearchLeadsService(settings)
    try:
        result = service.search(query, location, source, limit, campaign)
        selected = (
            service.store.get_campaign(campaign)
            if campaign
            else service.store.default_campaign()
        )
    except SearchAttemptPersistenceError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    except (ValueError, ApifyError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    if result.status in {RunStatus.FAILED, RunStatus.ABORTED, RunStatus.TIMED_OUT}:
        message = (
            " ".join(result.warnings)
            or f"search ended with status {result.status.value}"
        )
        typer.echo(f"Search failed: {message}", err=True)
        raise typer.Exit(code=1)
    typer.echo(
        f"Saved {len(result.leads)} leads ({result.status.value}) "
        f"to campaign '{selected.campaign_id}' ({selected.name})"
    )


@jobs_app.command("submit")
def jobs_submit(
    query: str,
    location: str,
    source: str = typer.Option("places", "--source"),
    limit: int = typer.Option(20, min=1),
    campaign: str | None = typer.Option(None, "--campaign"),
    idempotency_key: str = typer.Option(..., "--idempotency-key"),
    db: str | None = typer.Option(None, "--db"),
) -> None:
    from .execution.service import JobService
    settings = Settings()
    request = {"query": query, "location": location, "source": source, "limit": limit, "campaign_id": campaign}
    job = JobService(db or settings.database_path).submit(request, idempotency_key)
    typer.echo(f"Submitted job '{job.job_id}' ({job.state})")


@jobs_app.command("status")
def jobs_status(job_id: str, db: str | None = typer.Option(None, "--db")) -> None:
    from .execution.service import JobService
    job = JobService(db or Settings().database_path).get(job_id)
    if job is None:
        raise typer.BadParameter(f"job not found: {job_id}")
    typer.echo(f"ID: {job.job_id}")
    typer.echo(f"State: {job.state}")
    typer.echo(f"Progress: {json.dumps(job.progress, ensure_ascii=False)}")
    if job.error_code:
        typer.echo(f"Error: {job.error_code}")


@jobs_app.command("cancel")
def jobs_cancel(job_id: str, db: str | None = typer.Option(None, "--db")) -> None:
    from .execution.service import JobService
    job = JobService(db or Settings().database_path).cancel(job_id)
    if job is None:
        raise typer.BadParameter(f"job not found: {job_id}")
    typer.echo(f"Job '{job.job_id}' is {job.state}")


@campaign_app.command("create")
def campaign_create(
    name: str,
    description: str | None = typer.Option(None, "--description"),
    campaign_id: str | None = typer.Option(None, "--id"),
    db: str | None = typer.Option(None, "--db"),
) -> None:
    settings = Settings()
    try:
        campaign = LeadStore(db or settings.database_path).create_campaign(
            name, description, campaign_id
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Created campaign '{campaign.campaign_id}' ({campaign.name})")


@campaign_app.command("list")
def campaign_list(db: str | None = typer.Option(None, "--db")) -> None:
    settings = Settings()
    store = LeadStore(db or settings.database_path)
    for campaign in store.campaigns():
        stats = store.campaign_stats(campaign.campaign_id)
        default_marker = " [default]" if campaign.is_default else ""
        typer.echo(
            f"{campaign.campaign_id}\t{campaign.name}{default_marker}\t"
            f"Leads: {stats.lead_count}\tRuns: {stats.run_count}"
        )


@campaign_app.command("show")
def campaign_show(
    campaign_id: str,
    db: str | None = typer.Option(None, "--db"),
) -> None:
    settings = Settings()
    store = LeadStore(db or settings.database_path)
    campaign = store.get_campaign(campaign_id)
    if campaign is None:
        raise typer.BadParameter(f"campaign not found: {campaign_id}")
    stats = store.campaign_stats(campaign_id)
    typer.echo(f"ID: {campaign.campaign_id}")
    typer.echo(f"Name: {campaign.name}")
    typer.echo(f"Description: {campaign.description or '-'}")
    typer.echo(f"Created: {campaign.created_at.isoformat()}")
    typer.echo(f"Default: {'yes' if campaign.is_default else 'no'}")
    typer.echo(f"Leads: {stats.lead_count}")
    typer.echo(f"Runs: {stats.run_count}")


@app.command()
def export(
    path: str,
    format: str = typer.Option("json", "--format"),
    campaign: str | None = typer.Option(None, "--campaign", help="Campaign ID"),
    db: str | None = None,
    min_completeness: float | None = typer.Option(None, "--min-completeness", min=0, max=100),
    has_phone: bool = typer.Option(False, "--has-phone"),
    has_website: bool = typer.Option(False, "--has-website"),
) -> None:
    settings = Settings()
    try:
        LeadStore(db or settings.database_path).export(
            path, format, campaign_id=campaign, min_completeness=min_completeness,
            has_phone=has_phone, has_website=has_website,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Exported {path}")


if __name__ == "__main__":
    app()
