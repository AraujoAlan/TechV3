import json
import sqlite3
import uuid
from datetime import UTC, datetime

from app.contracts.errors import RepositoryUnavailable


class SqliteAuditLogger:
    def __init__(self, connection: sqlite3.Connection): self.connection = connection

    def record_event(self, *, audit_id: str, event: str, node: str, details: dict[str, str | int | float | bool | None], idempotency_key: str) -> None:
        try:
            self.connection.execute("INSERT OR IGNORE INTO audit_events VALUES (?, ?, ?, ?, ?, ?, ?)", (str(uuid.uuid4()), audit_id, node, event, json.dumps(details, sort_keys=True), idempotency_key, datetime.now(UTC).isoformat()))
            self.connection.commit()
        except sqlite3.Error as error:
            raise RepositoryUnavailable("Auditoria indisponível") from error
