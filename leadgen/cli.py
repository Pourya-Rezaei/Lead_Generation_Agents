import typer

from .config import Settings
from .registry import DisabledSourceError
from .service import SearchLeadsService
from .storage import LeadStore

app = typer.Typer(help="Collect, score, and export local business leads.")


@app.command()
def search(
    query: str,
    location: str,
    source: str = typer.Option("places", help="places"),
    limit: int = typer.Option(20, min=1),
    db: str | None = None,
) -> None:
    settings = Settings(database_path=db or Settings().database_path)
    try:
        result = SearchLeadsService(settings).search(query, location, source, limit)
    except (ValueError, DisabledSourceError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Saved {len(result.leads)} leads ({result.status.value})")


@app.command()
def export(path: str, format: str = typer.Option("json", "--format"), db: str | None = None) -> None:
    settings = Settings()
    LeadStore(db or settings.database_path).export(path, format)
    typer.echo(f"Exported {path}")


if __name__ == "__main__":
    app()
