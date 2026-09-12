# Design Doc — Workflow LangGraph do Assistente Clínico

**Status:** Proposto

**Base:** main em 5d9acf3, ou sucessor validado no início da implementação

**Branch de implementação:** feat/langgraph-workflow

**Escopo:** Assistente clínico materno-infantil

## 1. Resumo

Este documento propõe substituir a orquestração implícita do agente ReAct por um StateGraph próprio. O grafo torna visível e controlável a sequência de interpretação, autorização, recuperação de contexto, análise, alerta, geração e validação de respostas clínicas.

A proposta atende ao entregável de fluxos LangGraph e reforça os requisitos de segurança, rastreabilidade, explicabilidade, modularização e demonstração da Fase 3.

## 2. Contexto

A main já contém um assistente LangChain com quatro tools, SQLite, MemorySaver, documentação e scripts de demonstração. O agente ReAct decide quais tools chamar, porém a aplicação não controla de forma determinística:

- a autorização antes de recuperar prontuário;
- quando exames e protocolos devem ser consultados;
- o tratamento de perguntas incompletas;
- o registro de criticidade e alertas;
- a validação obrigatória da resposta;
- a construção de fontes e trilha de auditoria.

O desafio pede um assistente treinado com dados hospitalares, consultas a dados estruturados, respostas contextualizadas, limites clínicos, logging, fontes e fluxos LangGraph. O ReAct atual usa LangGraph internamente, mas não fornece um fluxo de domínio explícito suficiente para demonstrar esses controles.

## 3. Objetivos

- Implementar um StateGraph compilado e usado pelo CLI e, futuramente, pela API.
- Recuperar prontuário, exames e protocolos somente quando necessários e permitidos.
- Validar autorização antes de qualquer consulta de dado identificável.
- Classificar criticidade com regras determinísticas e análise estruturada.
- Registrar alertas de demonstração de modo auditável e idempotente.
- Entregar apenas respostas validadas, com fontes realmente recuperadas.
- Manter a LLM, os serviços, o grafo e a interface desacoplados e testáveis.
- Produzir evidências para README, relatório técnico e vídeo da Fase 3.

## 4. Não objetivos

- Conectar-se a um prontuário hospitalar real ou notificar uma equipe real.
- Substituir a avaliação ou a decisão clínica humana.
- Implementar prescrição, posologia ou ajuste terapêutico autônomo.
- Tornar MemorySaver uma solução de persistência de produção.
- Tornar FastAPI/SSE requisito para a primeira entrega do workflow.

## 5. Escopo clínico e dados

O domínio será materno-infantil: gestantes, puérperas e bebês até um ano. A decisão preserva o escopo declarado pelo modelo e pelo prompt mais recentes.

Os pacientes, exames e protocolos de demonstração devem ser sintéticos e coerentes com esse domínio. Dados genéricos hoje existentes devem ser substituídos ou identificados como legado e excluídos da demonstração clínica. Nenhum dado real de paciente deve ser incluído.

## 6. Estado atual e pré-requisitos

| Item | Estado atual | Decisão |
| --- | --- | --- |
| Orquestração | Agente ReAct decide livremente as tools. | Substituir pelo StateGraph explícito. |
| Dados | SQLite e ferramentas de consulta já existem. | Extrair para repositório injetável e popular apenas dados sintéticos. |
| Prompt | O system message é criado, mas não chega de forma explícita ao agente atual. | Aplicar prompts em cada nó de LLM. |
| Fine-tuning | A documentação declara Qwen + LoRA; a função atual usa pipeline de demonstração. | Validar adapter/modelo antes de alegar integração completa. |
| Structured output | Pode não ser suportado pelo pipeline textual. | Detectar capacidades e usar fallback determinístico. |
| Memória | MemorySaver opera apenas no processo. | Documentar a limitação e projetar checkpointer durável como evolução. |
| Dependências | requirements e pyproject divergem. | Definir pyproject e uv.lock como fonte de verdade. |
| Autorização | Inexistente. | Exigir contexto de autorização antes de consulta identificável. |

## 7. Decisões arquiteturais

### 7.1 StateGraph em vez de ReAct como orquestrador

O StateGraph controlará as rotas de negócio e os invariantes de segurança. LangChain continua responsável por prompts, parsers, LLM e tools.

**Motivo:** ReAct oferece flexibilidade, mas não garante que prontuário, exames, validação ou alerta ocorram na ordem exigida.

### 7.2 Serviços Python por trás das tools

Os nós chamarão interfaces de serviços por injeção de dependência. As quatro tools existentes serão adaptadores finos desses serviços, preservando compatibilidade com o CLI.

**Motivo:** Os mesmos comportamentos passam a ser testáveis sem LLM, graph runner ou tool calling.

### 7.3 Autorização antes da recuperação

Cada execução recebe:

~~~python
class RequestContext(BaseModel):
    conversation_id: str
    requester_id: str
    authorized_patient_ids: set[str]
    mode: Literal["demo", "authenticated"]
~~~

No modo demo, a lista é sintética e explícita. No modo autenticado, ela deverá vir de um serviço de identidade. Sem contexto autorizado, o repositório não é chamado.

**Motivo:** O prompt e o validador de texto não impedem acesso indevido ao prontuário.

### 7.4 Capacidades explícitas de LLM

O workflow terá duas dependências de LLM, injetadas por papel e nunca escolhidas livremente por um nó:

| Dependência | Modelo inicial | Nós permitidos | Formato e limite |
| --- | --- | --- | --- |
| `general_llm` | OpenAI `gpt-4.1-mini` | `interpretar_pergunta`, `analisar_informacoes`, criticidade auxiliar, clarificação e crítica auxiliar da resposta | JSON Schema estrito quando houver contrato estruturado. Não chama tools nem toma decisões de segurança. |
| `final_answer_llm` | Qwen3.5-4B + adapter LoRA fine-tuned | Somente `gerar_resposta` | Texto final baseado apenas no estado autorizado e nas fontes recuperadas. |

O adapter de LLM declara suporte a chat, JSON estruturado e streaming. A `general_llm` produz campos estruturados, que são validados antes de alterar o estado. Para modelo textual:

- o ID é extraído e validado deterministicamente;
- a condição é normalizada contra o catálogo de protocolos;
- a LLM pode propor extrações ou um resumo, mas não define autorização, rotas de negócio, criticidade final nem inventa identificadores.

O modelo fine-tuned não é usado para tool calling, roteamento, extração de IDs, autorização, alerta, auditoria ou validação. Seu dataset de treino contém respostas finais, não exemplos de tools ou de roteamento.

**Motivo:** Um HuggingFacePipeline textual não deve ser tratado como um chat model com tool calling ou structured output; o modelo fine-tuned foi treinado para redação final, enquanto os controles de segurança precisam ser determinísticos e testáveis.

### 7.5 Alertas de demonstração

Alertas serão eventos idempotentes persistidos em uma tabela alerts, contendo audit_id, paciente opcional, motivo, timestamp e chave de idempotência.

**Motivo:** O desafio pede emissão de alertas, mas a demonstração não pode alegar que notificou uma equipe real. A interface e a documentação devem chamá-los de simulados.

## 8. Arquitetura proposta

~~~text
CLI / API opcional
       |
RequestContext + pergunta
       |
StateGraph
  |-- nós de domínio
  |-- rotas condicionais
  |-- checkpointer
       |
Serviços: autorização | repositório | alerta | validador | auditoria
       |
SQLite sintético

LangChain e adaptadores de LLM são usados nos nós de interpretação, análise,
clarificação/crítica auxiliar e geração de resposta. `general_llm` atende os nós
intermediários; `final_answer_llm` é exclusivo da geração final.
~~~

| Camada | Responsabilidade |
| --- | --- |
| Adaptador de LLM | Capacidades, invocação do modelo e streaming. |
| LangChain | Prompts, Pydantic e parsers. |
| LangGraph | Estado, nós, rotas, retries e checkpointer. |
| Serviços | Regras, autorização, SQLite, alertas e auditoria. |
| API | Tradução opcional para FastAPI/SSE. |

## 9. Estado e contratos

O estado contém mensagens com reducer add_messages, RequestContext, audit_id, pergunta, patient_id, condition, intent, status de autorização, contexto recuperado, fontes, análise, criticidade, alerta, rascunho, resposta final, status de entrega, violações, contador de revisão e código de erro.

As fontes seguem o contrato do frontend:

~~~python
class Source(BaseModel):
    id: str
    title: str
    snippet: str | None = None
    kind: Literal["protocolo", "prontuario", "exame", "documento"]
~~~

Cada nó retorna somente o fragmento de estado modificado. Sources são deduplicadas por id. A resposta só pode citar fontes que existam no estado.

## 10. Workflow

Os nós são:

1. inicializar_execucao
2. interpretar_pergunta
3. autorizar_acesso
4. buscar_prontuario
5. verificar_exames
6. consultar_protocolo
7. analisar_informacoes
8. registrar_alerta_simulado
9. gerar_resposta
10. validar_seguranca

Uso de LLM por nó:

| Nó | Uso de LLM | Autoridade final |
| --- | --- | --- |
| `inicializar_execucao` | Não usa LLM. | Código. |
| `interpretar_pergunta` | `general_llm` para extrair campos em JSON Schema. | Validador determinístico; dúvida ou conflito pede clarificação. |
| `autorizar_acesso`, `buscar_prontuario`, `verificar_exames`, `consultar_protocolo` | Não usam LLM. | Serviços Python. |
| `analisar_informacoes` | `general_llm` pode sintetizar achados estruturados. | Regras e dados recuperados. |
| `registrar_alerta_simulado` | Não usa LLM. | Regras determinísticas de criticidade e serviço de alerta. |
| `gerar_resposta` | Exclusivamente `final_answer_llm` fine-tuned. | Validador de segurança e fontes. |
| `validar_seguranca` | Pode chamar `general_llm` como crítica auxiliar. | Validador determinístico; uma crítica favorável não aprova resposta sozinha. |

~~~mermaid
flowchart TD
  START --> init[inicializar_execucao] --> interpret[interpretar_pergunta]
  interpret --> patient{Paciente?}
  patient -->|sim| auth[autorizar_acesso]
  auth -->|autorizado| record[buscar_prontuario] --> exams[verificar_exames]
  auth -->|negado| limited[resposta de limitação]
  patient -->|não| condition{Condição?}
  exams --> condition
  condition -->|sim| protocol[consultar_protocolo] --> analysis[analisar_informacoes]
  condition -->|não| analysis
  analysis --> critical{Crítico?}
  critical -->|sim e paciente| alert[registrar_alerta_simulado] --> answer[gerar_resposta]
  critical -->|sim sem paciente| escalation[resposta de escalonamento]
  critical -->|não| answer
  answer --> safety[validar_seguranca]
  limited --> safety
  escalation --> safety
  safety -->|aprovada| END
  safety -->|uma revisão| answer
  safety -->|bloqueada ou clarificação| END
~~~

### Regras de roteamento

- Paciente sem condição: prontuário e exames, depois análise; nunca consulta protocolo nulo.
- Condição sem paciente: somente protocolo e resposta geral, sem contexto individual.
- Sem paciente e sem condição: pedir dados mínimos, sem consulta.
- Acesso negado: não chamar repositório clínico.
- Caso crítico sem paciente: escalar para avaliação humana, sem alerta vinculado a um paciente inexistente.
- Caso crítico com paciente: registrar o alerta simulado antes da resposta.

## 11. Segurança, validação e auditoria

Criticidade combina regras determinísticas versionadas do domínio, análise estruturada auxiliar da `general_llm` e contexto autorizado. A LLM não dispara alertas sozinha; as regras determinísticas definem o resultado final.

O validador determinístico:

- bloqueia prescrição, dose, posologia e ajuste como conduta autônoma;
- permite citar dose ou medicamento recuperado como fato, não como recomendação nova;
- permite resumir protocolo recuperado e atribuído a fonte;
- rejeita fatos, exames e fontes ausentes do estado;
- bloqueia resposta individual quando o contexto é insuficiente;
- exige escalonamento humano para casos críticos;
- permite apenas uma reformulação; depois entrega uma mensagem segura de bloqueio.

Uma candidata reprovada nunca é exibida. A mensagem de bloqueio é uma resposta nova e validada.

O audit logger registra audit_id, início/fim de nó, rota, duração, fontes referenciadas, alerta e resultado da validação. Não registra prontuário integral, chaves, prompts completos ou texto clínico desnecessário.

## 12. Alternativas consideradas

| Alternativa | Decisão | Motivo |
| --- | --- | --- |
| Manter ReAct como fluxo principal | Rejeitada. | Não garante ordem, autorização, validação ou alerta. |
| Usar LLM para toda extração e roteamento | Rejeitada. | IDs, autorização e condições precisam de controles determinísticos. |
| Usar o fine-tuned como router ou para tool calling | Rejeitada. | O treino foi feito para respostas finais e não contém chamadas de tools ou rotas. |
| Usar uma única LLM para todos os nós | Rejeitada. | Separa a LLM geral estruturada da LLM fine-tuned de redação e reduz o escopo de confiança de cada uma. |
| Validar só por prompt ou LLM avaliadora | Rejeitada. | Não fornece proteção testável contra respostas impróprias. |
| Alerta real para equipe | Adiada. | Exige integração operacional, consentimento e observabilidade externa. |
| FastAPI/SSE no núcleo inicial | Adiada. | É útil para o frontend, mas não bloqueia o entregável LangGraph. |
| Checkpointer durável agora | Adiado. | MemorySaver é suficiente para a demonstração em processo; persistência real requer infraestrutura própria. |

## 13. Estrutura de código

~~~text
app/
├── graph/       state.py, nodes.py, routes.py, workflow.py
├── llm/         factory.py, capabilities.py, prompts.py, schemas.py
├── services/    authorization.py, medical_repository.py,
│                alert_service.py, safety_validator.py, audit_logger.py
├── api/         routes.py e schemas.py, em fase posterior
└── cli.py
tests/
├── unit/
└── integration/
docs/
└── relatorio-tecnico.md
~~~

O repositório clínico encapsula SQLite, recebe conexão/fábrica por injeção de dependência, inicializa dados sintéticos idempotentes e inclui a tabela alerts.

## 14. Testes e validação

| Caso | Resultado esperado |
| --- | --- |
| Paciente autorizado e condição | prontuário, exames e protocolo; fontes reais e resposta validada. |
| Paciente sem condição | prontuário/exames e análise; sem protocolo nulo. |
| Condição sem paciente | somente protocolo e resposta geral. |
| ID não autorizado | nenhum acesso clínico; resposta segura. |
| ID inexistente | ausência controlada e sem dados inventados. |
| Pergunta insuficiente | pedido de esclarecimento sem consulta. |
| Caso crítico com paciente | regra + análise e alerta idempotente antes da resposta. |
| Caso crítico sem ID | escalonamento sem alerta de paciente. |
| Prescrição ou dose nova | reformulação ou bloqueio. |
| Dose recuperada | pode ser citada apenas como fato. |
| Fonte inexistente ou falha do repositório | limitação segura e auditoria. |
| Mesmo thread_id | contexto permitido no mesmo processo. |
| Reinício | ausência de persistência documentada até checkpointer durável. |
| API, quando existir | autorização, fontes, done final e cancelamento. |

Testes unitários usam serviços e LLM falsos determinísticos. Modelos reais entram apenas em smoke tests.

## 15. Plano de entrega

1. Congelar SHA, corrigir prompt, dependências e documentação do modelo.
2. Extrair serviços, preparar dados sintéticos do domínio e criar alerts.
3. Implementar estado, autorização, nós e rotas do StateGraph.
4. Implementar `LLMFactory` com `general_llm=OpenAI gpt-4.1-mini` e `final_answer_llm=Qwen3.5-4B + LoRA`; injetar cada dependência apenas nos nós permitidos e remover o uso enganoso de `--finetuned` como se carregasse o adapter.
5. Implementar schemas Pydantic, parsing/validação semântica e tratamento de recusa/erro da `general_llm`.
6. Implementar criticidade, alerta, geração e validação.
7. Implementar auditoria, fontes e documentação dos limites de memória.
8. Criar testes, relatório técnico e roteiro de vídeo.
9. Integrar FastAPI/SSE somente após a aprovação do núcleo.

## 16. Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| `general_llm` retorna JSON válido, porém semanticamente inadequado | Validar enums, IDs, catálogo, confiança e regras de negócio; em dúvida, pedir clarificação. |
| Falha, timeout ou recusa da OpenAI | Não consultar dados adicionais nem gerar decisão clínica; registrar o evento minimizado e retornar clarificação/limitação segura. |
| Modelo fine-tunado não suporta JSON/tools | Não usá-lo para JSON/tools; restringi-lo à geração final. |
| Dados de demonstração fora do escopo | Substituir por dados sintéticos materno-infantis antes do vídeo. |
| Vazamento de dados | Autorizar antes da busca, minimizar logs e usar somente dados sintéticos. |
| Falso alerta | Regras versionadas, idempotência e alerta explicitamente simulado. |
| Documentação diverge do código | Checklist de evidências e smoke test antes da demonstração. |
| Escopo cresce com API | API é fase posterior e não bloqueia o grafo. |

## 17. Critérios de sucesso

- Existe um StateGraph compilado e usado pelo aplicativo.
- Todas as consultas identificáveis passam por autorização.
- Todas as respostas passam por validação antes de exibição.
- Fontes exibidas foram de fato recuperadas.
- Alertas simulados são idempotentes, rastreáveis e não são apresentados como notificação real.
- Testes de rotas, segurança, falhas e criticidade passam sem API externa.
- O repositório contém dataset anonimizado ou sintético, fine-tuning, integração LangChain, fluxo LangGraph e relatório técnico.
- O vídeo de até 15 minutos mostra modelo, fluxo automatizado, resposta contextualizada, logs e validação.
