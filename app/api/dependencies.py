from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request

from app.graph.workflow import WorkflowDependencies


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    requester_id: str
    authorized_patient_ids: frozenset[str]


def _parse_patient_ids(raw: str) -> frozenset[str]:
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def get_demo_principal() -> AuthenticatedPrincipal:
    """Identidade e autorização vêm só do servidor — nunca do JSON do navegador."""
    requester_id = os.getenv("DEMO_REQUESTER_ID", "demo-clinician").strip() or "demo-clinician"
    authorized = _parse_patient_ids(os.getenv("DEMO_AUTHORIZED_PATIENT_IDS", "P-042"))
    return AuthenticatedPrincipal(requester_id=requester_id, authorized_patient_ids=authorized)


def get_current_principal(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_demo_principal)],
) -> AuthenticatedPrincipal:
    return principal


def get_workflow_deps(request: Request) -> WorkflowDependencies:
    return request.app.state.deps


def get_invoke_lock(request: Request) -> threading.Lock:
    return request.app.state.invoke_lock
