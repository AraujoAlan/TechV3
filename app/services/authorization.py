from app.contracts.models import RequestContext


class DemoAuthorizationService:
    def is_patient_authorized(self, context: RequestContext, patient_id: str) -> bool:
        return context.mode == "demo" and patient_id in context.authorized_patient_ids
