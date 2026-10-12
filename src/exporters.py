import csv
import json
from collections.abc import Iterable
from os import PathLike
from pathlib import Path
from typing import Any

from .domain import Lead

LEGACY_EXPORT_FIELDS = (
    "name",
    "address",
    "phone",
    "website",
    "category",
    "source",
    "rating",
    "reviews",
    "score",
    "collected_at",
)
PROVENANCE_EXPORT_FIELDS = ("source_id", "source_url")


def _fields(extended: bool) -> tuple[str, ...]:
    if extended:
        return LEGACY_EXPORT_FIELDS + PROVENANCE_EXPORT_FIELDS
    return LEGACY_EXPORT_FIELDS


def _row(lead: Lead, extended: bool) -> dict[str, Any]:
    data = lead.model_dump(mode="json")
    return {field: data.get(field) for field in _fields(extended)}


def _prepare_target(target: str | PathLike[str]) -> Path:
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def export_json(
    leads: Iterable[Lead],
    target: str | PathLike[str],
    extended: bool = False,
) -> None:
    path = _prepare_target(target)
    with path.open("w", encoding="utf-8") as file:
        file.write("[")
        first = True
        for lead in leads:
            if not first:
                file.write(",")
            encoded = json.dumps(_row(lead, extended), indent=2)
            file.write("\n  ")
            file.write(encoded.replace("\n", "\n  "))
            first = False
        if not first:
            file.write("\n")
        file.write("]")


def _sanitize_csv_value(value: Any) -> Any:
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def export_csv(
    leads: Iterable[Lead],
    target: str | PathLike[str],
    extended: bool = False,
) -> None:
    path = _prepare_target(target)
    fields = _fields(extended)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for lead in leads:
            writer.writerow(
                {key: _sanitize_csv_value(value) for key, value in _row(lead, extended).items()}
            )


def render_leads(leads: Iterable[Lead], format: str = "json") -> bytes:
    """Render downloads without writing provider data to a temporary file."""
    import io
    rows = [_row(lead, False) for lead in leads]
    if format == "json":
        content = "[" + ("\n  " + ",\n  ".join(json.dumps(row, indent=2).replace("\n", "\n  ") for row in rows) + "\n" if rows else "") + "]"
    elif format == "csv":
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=LEGACY_EXPORT_FIELDS)
        writer.writeheader()
        writer.writerows({key: _sanitize_csv_value(value) for key, value in row.items()} for row in rows)
        content = buffer.getvalue()
    else:
        raise ValueError("format must be json or csv")
    return content.encode("utf-8")


def export_instagram_profiles(profiles, target: str, format: str = "json") -> None:
    """Export profiles, never fabricated shared Lead fields."""
    content = render_instagram_profiles(profiles, format)
    _prepare_target(target).write_bytes(content)


def render_instagram_profiles(profiles, format="json"):
    import io
    from .source_contracts import InstagramRecord
    rows = [profile.model_dump(mode="json") for profile in profiles]
    if format == "json":
        return json.dumps(rows, ensure_ascii=False, indent=2).encode("utf-8")
    if format != "csv":
        raise ValueError("format must be json or csv")
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(InstagramRecord.model_fields))
    writer.writeheader()
    for row in rows:
        row["external_links"] = json.dumps(row["external_links"], ensure_ascii=False)
        writer.writerow({key: ("'" + value if isinstance(value, str) and (value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r"))) else value) for key, value in row.items()})
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")
