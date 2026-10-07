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
