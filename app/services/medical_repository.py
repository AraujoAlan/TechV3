import sqlite3
from datetime import datetime
from pathlib import Path

from app.contracts.errors import RepositoryUnavailable
from app.contracts.models import PatientRecord, PendingExam, ProtocolRecord, Source


class MedicalRepositorySqlite:
    """Adaptador local para dados sintéticos; autorização pertence ao grafo."""
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.connection.row_factory = sqlite3.Row

    @classmethod
    def open(cls, path: str | Path) -> "MedicalRepositorySqlite":
        return cls(sqlite3.connect(path))

    def initialize(self) -> None:
        try:
            self.connection.executescript("""
                CREATE TABLE IF NOT EXISTS patients (patient_id TEXT PRIMARY KEY, summary TEXT NOT NULL, version TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS pending_exams (exam_id TEXT PRIMARY KEY, patient_id TEXT NOT NULL, name TEXT NOT NULL, requested_at TEXT, version TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS protocols (condition TEXT PRIMARY KEY, summary TEXT NOT NULL, version TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS alerts (alert_id TEXT PRIMARY KEY, audit_id TEXT NOT NULL, patient_id TEXT, rule_code TEXT NOT NULL, rule_version TEXT NOT NULL, reason TEXT NOT NULL, idempotency_key TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL, status TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS audit_events (event_id TEXT PRIMARY KEY, audit_id TEXT NOT NULL, node TEXT NOT NULL, event TEXT NOT NULL, details TEXT NOT NULL, idempotency_key TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_audit_events_audit_created ON audit_events(audit_id, created_at);
            """)
            self.connection.executemany("INSERT OR IGNORE INTO patients VALUES (?, ?, ?)", [
                ("P-042", "Gestante sintética com hipertensão gestacional e sinais de alarme documentados.", "v1"),
                ("P-101", "Bebê sintético de seis meses em acompanhamento de rotina.", "v1"),
            ])
            self.connection.executemany("INSERT OR IGNORE INTO pending_exams VALUES (?, ?, ?, ?, ?)", [
                ("EX-042-1", "P-042", "Avaliação de pressão grave pendente", "2026-09-01T10:00:00", "v1"),
            ])
            self.connection.executemany("INSERT OR IGNORE INTO protocols VALUES (?, ?, ?)", [
                ("hipertensao-gestacional", "Protocolo sintético: sinais de alarme exigem avaliação humana imediata.", "v1"),
                ("puerperio", "Protocolo sintético de acompanhamento no puerpério.", "v1"),
            ])
            self.connection.commit()
        except sqlite3.Error as error:
            raise RepositoryUnavailable("SQLite indisponível") from error

    def get_patient_record(self, patient_id: str) -> PatientRecord | None:
        try:
            row = self.connection.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,)).fetchone()
        except sqlite3.Error as error:
            raise RepositoryUnavailable("Consulta de prontuário indisponível") from error
        if row is None:
            return None
        source = Source(id=f"record:{row['patient_id']}:{row['version']}", title="Prontuário sintético", snippet=row["summary"], kind="prontuario")
        return PatientRecord(patient_id=row["patient_id"], summary=row["summary"], source=source)

    def get_pending_exams(self, patient_id: str) -> list[PendingExam]:
        try:
            rows = self.connection.execute("SELECT * FROM pending_exams WHERE patient_id = ?", (patient_id,)).fetchall()
        except sqlite3.Error as error:
            raise RepositoryUnavailable("Consulta de exames indisponível") from error
        return [PendingExam(exam_id=row["exam_id"], name=row["name"], requested_at=datetime.fromisoformat(row["requested_at"]) if row["requested_at"] else None, source=Source(id=f"exam:{row['exam_id']}:{row['version']}", title="Exame sintético", snippet=row["name"], kind="exame")) for row in rows]

    def get_protocol(self, condition: str) -> ProtocolRecord | None:
        try:
            row = self.connection.execute("SELECT * FROM protocols WHERE condition = ?", (condition,)).fetchone()
        except sqlite3.Error as error:
            raise RepositoryUnavailable("Consulta de protocolo indisponível") from error
        if row is None:
            return None
        source = Source(id=f"protocol:{row['condition']}:{row['version']}", title=f"Protocolo sintético: {row['condition']}", snippet=row["summary"], kind="protocolo")
        return ProtocolRecord(condition=row["condition"], version=row["version"], summary=row["summary"], source=source)
