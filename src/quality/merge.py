import json
import sqlite3
import uuid
from datetime import UTC, datetime


def merge(connection: sqlite3.Connection, source_lead_id: str, target_lead_id: str, reason: str, confidence: float) -> str:
    if source_lead_id == target_lead_id or not reason.strip() or not 0 <= confidence <= 1:
        raise ValueError("invalid merge decision")
    source = connection.execute("SELECT dedup_key, payload FROM leads WHERE lead_id = ?", (source_lead_id,)).fetchone()
    target = connection.execute("SELECT dedup_key, payload FROM leads WHERE lead_id = ?", (target_lead_id,)).fetchone()
    if source is None or target is None:
        raise ValueError("lead not found")
    merge_id = uuid.uuid4().hex
    connection.execute("UPDATE campaign_leads SET lead_dedup_key = ? WHERE lead_dedup_key = ?", (target[0], source[0]))
    connection.execute("DELETE FROM leads WHERE lead_id = ?", (source_lead_id,))
    connection.execute("INSERT INTO lead_merge_audit(merge_id, source_lead_id, target_lead_id, reason, confidence, created_at, source_key, target_key, source_payload) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (merge_id, source_lead_id, target_lead_id, reason.strip(), confidence, datetime.now(UTC).isoformat(), source[0], target[0], source[1]))
    return merge_id


def undo(connection: sqlite3.Connection, merge_id: str) -> None:
    row = connection.execute("SELECT source_lead_id, target_lead_id, source_key, target_key, source_payload, status FROM lead_merge_audit WHERE merge_id = ?", (merge_id,)).fetchone()
    if row is None or row[5] != "active":
        raise ValueError("active merge not found")
    if connection.execute("SELECT 1 FROM leads WHERE lead_id = ?", (row[0],)).fetchone():
        raise ValueError("source lead already exists")
    connection.execute("INSERT INTO leads(dedup_key, payload, lead_id) VALUES (?, ?, ?)", (row[2], row[4], row[0]))
    connection.execute("UPDATE campaign_leads SET lead_dedup_key = ? WHERE lead_dedup_key = ?", (row[2], row[3]))
    connection.execute("UPDATE lead_merge_audit SET status = 'undone', undone_at = ? WHERE merge_id = ?", (datetime.now(UTC).isoformat(), merge_id))
