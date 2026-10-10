import json
import sqlite3
import uuid
from datetime import datetime, timezone


def merge(connection: sqlite3.Connection, source_lead_id: str, target_lead_id: str, reason: str, confidence: float) -> str:
    if source_lead_id == target_lead_id or not reason.strip() or not 0 <= confidence <= 1:
        raise ValueError("invalid merge decision")
    if connection.in_transaction:
        connection.commit()
    connection.execute("BEGIN IMMEDIATE")
    try:
        source = connection.execute("SELECT dedup_key, payload FROM leads WHERE lead_id = ?", (source_lead_id,)).fetchone()
        target = connection.execute("SELECT dedup_key, payload FROM leads WHERE lead_id = ?", (target_lead_id,)).fetchone()
        if source is None or target is None:
            raise ValueError("lead not found")
        memberships = [
            {"campaign_id": row[0], "first_seen_at": row[1], "last_seen_at": row[2]}
            for row in connection.execute(
                "SELECT campaign_id, first_seen_at, last_seen_at FROM campaign_leads WHERE lead_id = ?",
                (source_lead_id,),
            )
        ]
        for membership in memberships:
            connection.execute(
                "INSERT INTO campaign_leads(campaign_id, lead_id, first_seen_at, last_seen_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(campaign_id, lead_id) DO UPDATE SET first_seen_at = MIN(first_seen_at, excluded.first_seen_at), last_seen_at = MAX(last_seen_at, excluded.last_seen_at)",
                (membership["campaign_id"], target_lead_id, membership["first_seen_at"], membership["last_seen_at"]),
            )
        connection.execute("DELETE FROM campaign_leads WHERE lead_id = ?", (source_lead_id,))
        merge_id = uuid.uuid4().hex
        connection.execute("DELETE FROM leads WHERE lead_id = ?", (source_lead_id,))
        connection.execute("INSERT INTO lead_merge_audit(merge_id, source_lead_id, target_lead_id, reason, confidence, created_at, source_key, target_key, source_payload, membership_snapshot) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (merge_id, source_lead_id, target_lead_id, reason.strip(), confidence, datetime.now(timezone.utc).isoformat(), source[0], target[0], source[1], json.dumps(memberships, ensure_ascii=False)))
        connection.commit()
        return merge_id
    except Exception:
        connection.rollback()
        raise


def undo(connection: sqlite3.Connection, merge_id: str) -> None:
    if connection.in_transaction:
        connection.commit()
    connection.execute("BEGIN IMMEDIATE")
    try:
        row = connection.execute("SELECT source_lead_id, target_lead_id, source_key, target_key, source_payload, status, membership_snapshot FROM lead_merge_audit WHERE merge_id = ?", (merge_id,)).fetchone()
        if row is None or row[5] != "active":
            raise ValueError("active merge not found")
        if connection.execute("SELECT 1 FROM leads WHERE lead_id = ?", (row[0],)).fetchone():
            raise ValueError("source lead already exists")
        connection.execute("INSERT INTO leads(dedup_key, payload, lead_id) VALUES (?, ?, ?)", (row[2], row[4], row[0]))
        for membership in json.loads(row[6] or "[]"):
            connection.execute(
                "INSERT INTO campaign_leads(campaign_id, lead_id, first_seen_at, last_seen_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(campaign_id, lead_id) DO UPDATE SET first_seen_at = excluded.first_seen_at, last_seen_at = excluded.last_seen_at",
                (membership["campaign_id"], row[0], membership["first_seen_at"], membership["last_seen_at"]),
            )
        connection.execute("UPDATE lead_merge_audit SET status = 'undone', undone_at = ? WHERE merge_id = ?", (datetime.now(timezone.utc).isoformat(), merge_id))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
