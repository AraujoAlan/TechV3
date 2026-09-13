import sqlite3
import uuid
from datetime import UTC, datetime

from app.contracts.errors import AlertUnavailable
from app.contracts.models import AlertRecord, AlertRequest


class SqliteAlertService:
    def __init__(self, connection: sqlite3.Connection): self.connection = connection

    def record_simulated_alert(self, request: AlertRequest) -> AlertRecord:
        try:
            existing = self.connection.execute("SELECT * FROM alerts WHERE idempotency_key = ?", (request.idempotency_key,)).fetchone()
            if existing:
                return AlertRecord(alert_id=existing[0], idempotency_key=existing[6], created_at=datetime.fromisoformat(existing[7]), status=existing[8])
            created_at = datetime.now(UTC)
            alert_id = str(uuid.uuid4())
            self.connection.execute("INSERT INTO alerts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (alert_id, request.audit_id, request.patient_id, request.rule_code, request.rule_version, request.reason, request.idempotency_key, created_at.isoformat(), "simulated_recorded"))
            self.connection.commit()
            return AlertRecord(alert_id=alert_id, idempotency_key=request.idempotency_key, created_at=created_at, status="simulated_recorded")
        except sqlite3.Error as error:
            raise AlertUnavailable("Persistência de alerta indisponível") from error
