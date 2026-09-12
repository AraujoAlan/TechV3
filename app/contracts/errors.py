class WorkflowServiceError(Exception):
    """Base para falhas que exigem encerramento seguro do workflow."""


class RepositoryUnavailable(WorkflowServiceError):
    pass


class AlertUnavailable(WorkflowServiceError):
    pass


class GeneralLLMUnavailable(WorkflowServiceError):
    pass


class FinalAnswerModelUnavailable(WorkflowServiceError):
    pass
