# Contrato de integração — LangGraph e serviços

**Status:** contrato para implementação

**Consumidor:** `app/graph` (StateGraph)

**Implementadores:** backend/dados, LangChain/modelo e segurança/auditoria

## 1. Objetivo e limites

Este contrato permite implementar e testar o workflow LangGraph sem depender de SQLite, modelo treinado ou serviços reais. O grafo depende apenas das portas descritas aqui; cada equipe fornece uma implementação real e uma fake determinística para testes.

O escopo é a demonstração com dados sintéticos. Não define API HTTP, autenticação corporativa, prontuário real nem notificações externas.

## 2. Regras de integração

- O grafo chama `AuthorizationService` antes de qualquer método identificável do repositório.
- O repositório nunca recebe nem decide permissões; ele recebe apenas o ID previamente autorizado pelo grafo.
- `NotFound` é diferente de `Unavailable`: ausência de paciente/protocolo é resposta controlada; indisponibilidade encerra o fluxo com limitação segura.
- Métodos de leitura não alteram estado. `record_alert` e `record_event` devem ser idempotentes quando receberem a mesma chave.
- Nenhuma implementação deve escrever ou retornar dados reais de paciente.
- O grafo não conhece SQL, tabelas, detalhes de LangChain, paths de modelo ou formato do log.

## 3. Modelos compartilhados

Os modelos devem ficar em módulo sem dependência de LangGraph, por exemplo `app/contracts/models.py`.

~~~python
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class RequestContext(BaseModel):
    conversation_id: str
    requester_id: str
    authorized_patient_ids: frozenset[str]
    mode: Literal["demo"] = "demo"


class Source(BaseModel):
    id: str
    title: str
    snippet: str | None = None
    kind: Literal["protocolo", "prontuario", "exame", "documento"]


class PatientRecord(BaseModel):
    patient_id: str
    summary: str
    source: Source


class PendingExam(BaseModel):
    exam_id: str
    name: str
    requested_at: datetime | None = None
    source: Source


class ProtocolRecord(BaseModel):
    condition: str
    version: str
    summary: str
    source: Source


class CriticalityResult(BaseModel):
    is_critical: bool
    rule_code: str | None = None
    rule_version: str
    reason: str | None = None


class AlertRequest(BaseModel):
    audit_id: str
    patient_id: str | None = None
    rule_code: str
    rule_version: str
    reason: str
    idempotency_key: str


class AlertRecord(BaseModel):
    alert_id: str
    idempotency_key: str
    created_at: datetime
    status: Literal["simulated_recorded"]


class ValidationResult(BaseModel):
    approved: bool
    requires_revision: bool = False
    violations: list[str] = Field(default_factory=list)
    safe_message: str | None = None
~~~

`Source.id` deve ser estável, único e versionado quando aplicável, por exemplo `protocol:hipertensao-gestacional:v1`. O backend retorna fatos e fontes, não texto pronto de resposta clínica.

## 4. Portas requeridas pelo StateGraph

As assinaturas abaixo são o contrato mínimo. Podem ser declaradas como `Protocol`, classes abstratas ou interfaces equivalentes.

~~~python
from typing import Protocol


class AuthorizationService(Protocol):
    def is_patient_authorized(
        self, context: RequestContext, patient_id: str
    ) -> bool: ...


class MedicalRepository(Protocol):
    def get_patient_record(self, patient_id: str) -> PatientRecord | None: ...

    def get_pending_exams(self, patient_id: str) -> list[PendingExam]: ...

    def get_protocol(self, condition: str) -> ProtocolRecord | None: ...


class CriticalityService(Protocol):
    def evaluate(
        self,
        *,
        record: PatientRecord | None,
        exams: list[PendingExam],
        protocol: ProtocolRecord | None,
    ) -> CriticalityResult: ...


class AlertService(Protocol):
    def record_simulated_alert(self, request: AlertRequest) -> AlertRecord: ...


class AuditLogger(Protocol):
    def record_event(
        self,
        *,
        audit_id: str,
        event: str,
        node: str,
        details: dict[str, str | int | float | bool | None],
        idempotency_key: str,
    ) -> None: ...


class FinalAnswerLLM(Protocol):
    def generate(
        self,
        *,
        question: str,
        context: str,
        sources: list[Source],
    ) -> str: ...


class SafetyValidator(Protocol):
    def validate(
        self,
        *,
        answer: str,
        sources: list[Source],
        has_individual_context: bool,
        is_critical: bool,
    ) -> ValidationResult: ...
~~~

## 5. Responsabilidades por implementação

| Porta | Responsável | Implementação real esperada | Fake de teste |
| --- | --- | --- | --- |
| `AuthorizationService` | Backend/segurança | Compara o contexto demo com o ID solicitado. | Retorna permitido/negado configurável. |
| `MedicalRepository` | Backend/dados | SQLite sintético, com fixtures e fontes estáveis. | Retorna registros configurados ou `None`. |
| `CriticalityService` | Backend/regra de domínio | Regras Python pequenas e versionadas. | Retorna criticidade configurada. |
| `AlertService` | Backend/auditoria | Grava `alerts` SQLite com chave única. | Guarda chamadas em memória; pode falhar sob comando. |
| `AuditLogger` | Backend/auditoria | Grava `audit_events` SQLite minimizado. | Guarda eventos em memória. |
| `SafetyValidator` | Segurança/backend | Aplica regras de fontes, contexto e bloqueios. | Aprova, pede revisão ou bloqueia conforme cenário. |
| `FinalAnswerLLM` | LangChain/modelo | Carrega Qwen3.5-4B + adapter LoRA e gera texto. | Retorna texto pré-definido. |
| `StateGraph` | Responsável por LangGraph | Orquestra portas, estado e rotas. | N/A; é testado com as fakes acima. |

## 6. Contratos de falha

| Situação | Retorno da porta | Comportamento obrigatório do grafo |
| --- | --- | --- |
| Paciente não autorizado | `False` em autorização | Não chama repositório; produz limitação segura. |
| Paciente/protocolo não encontrado | `None` | Não inventa dados; clarifica ou responde limitação. |
| Exames não encontrados | Lista vazia | Continua sem alegar exame pendente. |
| Repositório indisponível | Exceção de infraestrutura | Audita, não faz nova consulta e encerra com limitação segura. |
| Alerta indisponível | Exceção de infraestrutura | Não entrega resposta clínica normal; audita a falha. |
| Modelo indisponível | Exceção de infraestrutura | Não usa fallback silencioso; encerra com limitação segura. |
| Resposta inválida | `ValidationResult(approved=False)` | Uma reformulação; depois template seguro de bloqueio. |

Exceções de infraestrutura devem ser específicas, como `RepositoryUnavailable`, `AlertUnavailable` e `ModelUnavailable`; não usar `None` para representar indisponibilidade.

## 7. Persistência esperada do backend

O backend pode reaproveitar `hospital.db`, mas deve substituir fixtures genéricas e adicionar tabelas mínimas:

~~~text
alerts(
  alert_id, audit_id, patient_id, rule_code, rule_version,
  reason, idempotency_key UNIQUE, created_at, status
)

audit_events(
  event_id, audit_id, node, event, duration_ms,
  source_ids, rule_version, validation_result,
  error_code, idempotency_key UNIQUE, created_at
)
~~~

O backend não armazena prompts completos, chaves, prontuário integral ou rascunho reprovado no audit log. O alerta tem status fixo `simulated_recorded`; não há integração de notificação real.

## 8. Exemplo mínimo de fake

~~~python
class FakeRepository:
    def get_patient_record(self, patient_id: str) -> PatientRecord | None:
        return PatientRecord(
            patient_id=patient_id,
            summary="Gestante sintética em acompanhamento.",
            source=Source(
                id=f"record:{patient_id}:v1",
                title="Prontuário sintético",
                kind="prontuario",
            ),
        )

    def get_pending_exams(self, patient_id: str) -> list[PendingExam]:
        return []

    def get_protocol(self, condition: str) -> ProtocolRecord | None:
        return None
~~~

O teste do grafo injeta esse fake e uma `FakeFinalAnswerLLM`. O teste de integração substitui as fakes por SQLite e pelo adapter real, sem alterar nós ou rotas.

## 9. Checklist de handoff e integração

Antes de integrar componentes reais, confirmar:

- [ ] Modelos Pydantic compartilhados importam sem depender de LangGraph ou SQLite.
- [ ] Todas as portas possuem fake usada nos testes do grafo.
- [ ] O SQLite retorna `Source` estável para cada dado recuperado.
- [ ] O adapter real implementa `FinalAnswerLLM.generate` e não faz tool calling.
- [ ] A execução real prova que o adapter Qwen3.5-4B + LoRA foi carregado.
- [ ] Alertas usam a mesma `idempotency_key` em reexecuções.
- [ ] Auditoria não contém dados sensíveis ou rascunhos bloqueados.
- [ ] O teste integrado cobre autorização, fontes, validação e alerta crítico.
