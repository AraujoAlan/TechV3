# Design Doc — Workflow LangGraph do Assistente Clínico

**Status:** Aprovado para implementação

**Base:** `main` em `5d9acf3`, ou sucessor validado no início da implementação

**Branch de implementação:** `feat/langgraph-workflow`

**Escopo:** demonstração de assistente clínico materno-infantil com dados sintéticos

## 1. Resumo

Este documento substitui a orquestração implícita do agente ReAct por um `StateGraph` de domínio. O grafo controla, em ordem verificável, interpretação determinística, autorização, recuperação de contexto, análise, criticidade, alerta simulado, geração, validação, fontes e auditoria.

O objetivo é atender à Fase 3 com uma demonstração local, modular e testável. Não é um sistema hospitalar de produção, não processa dados reais e não notifica equipes reais.

## 2. Contexto e fatos verificados

A implementação atual contém ReAct, quatro tools, SQLite e `MemorySaver`, mas não possui autorização antes de ler prontuários, validação determinística, fontes rastreáveis ou auditoria persistida. O banco atual contém exemplos genéricos fora do escopo materno-infantil e deve ser substituído antes da demonstração.

O adapter Qwen3.5-4B + LoRA foi treinado e avaliado nos notebooks, mas ainda não é carregado pelo runtime. A opção legada `main.py --finetuned` carrega `Qwen/Qwen2.5-1.5B-Instruct`, isto é, um modelo-base de demonstração, não o adapter treinado. Ela não pode ser usada como prova de integração do fine-tuning.

## 3. Objetivos

- Usar um `StateGraph` compilado no CLI.
- Consultar prontuários e exames somente para pacientes explicitamente autorizados no contexto de demonstração.
- Usar dados, protocolos e pacientes sintéticos coerentes com gestação, puerpério ou bebês até um ano.
- Contextualizar respostas com dados recuperados e fontes rastreáveis.
- Aplicar regras determinísticas de criticidade, alertas simulados idempotentes e validação antes de exibir qualquer resposta.
- Integrar o adapter fine-tuned apenas para geração de resposta final, após smoke test de carregamento.
- Produzir testes, README, relatório técnico e roteiro de vídeo compatíveis com a entrega.

## 4. Não objetivos

- Integração com prontuário, identidade, alertas ou dados reais de hospital.
- API FastAPI/SSE, autenticação corporativa ou checkpointer durável no MVP.
- Prescrição, posologia, ajuste terapêutico ou decisão clínica autônoma.
- Garantir detecção semântica absoluta de toda alucinação de texto livre.
- Usar o modelo fine-tuned para tool calling, extração de IDs, autorização, roteamento ou criticidade.

## 5. Escopo de dados e confiança

O MVP opera somente em modo `demo`, com fixtures sintéticas versionadas. O CLI cria o contexto de acesso; a pergunta do usuário nunca pode fornecer ou ampliar permissões.

~~~python
class RequestContext(BaseModel):
    conversation_id: str
    requester_id: str
    authorized_patient_ids: frozenset[str]
    mode: Literal["demo"]
~~~

Uma futura API autenticada deverá criar esse contexto em serviço de identidade confiável. Até existir essa integração, qualquer tentativa de usar modo autenticado deve falhar de modo seguro.

Regras de acesso:

- `conversation_id` identifica memória e auditoria; não concede autorização.
- Cada leitura identificável revalida o paciente contra `authorized_patient_ids`.
- ID ausente, ambíguo, inexistente ou não autorizado não provoca busca aproximada, enumeração nem acesso ao repositório.
- Protocolos sintéticos não identificáveis podem ser consultados sem paciente.
- Conteúdo recuperado é sempre dado delimitado, nunca instrução para o modelo.

## 6. Arquitetura do MVP

~~~text
CLI (`python -m app.cli`)
       |
pergunta + RequestContext sintético
       |
StateGraph
  |-- nós e rotas determinísticos
  |-- adapter Qwen + LoRA apenas na resposta final
       |
serviços Python injetáveis
  |-- autorização | repositório SQLite | criticidade
  |-- alerta simulado | validador | auditoria
       |
SQLite com fixtures, alerts e audit_events
~~~

### 6.1 Backend local de referência

Será implementado um backend mínimo, local e baseado em SQLite para permitir que o `StateGraph` seja exercitado com dependências reais, e não somente com fakes. Ele é um adaptador de referência para a demonstração e para os testes de integração; não é uma API de produção.

Seu escopo é limitado a:

- `MedicalRepositorySqlite` com pacientes, exames e protocolos sintéticos materno-infantis;
- autorização de demonstração baseada em `RequestContext`;
- persistência SQLite de `alerts` simulados e `audit_events` minimizados;
- implementação das portas descritas em [langgraph-backend-contract.md](langgraph-backend-contract.md).

Ele não inclui FastAPI, SSE, autenticação corporativa, banco remoto, notificações externas, filas ou checkpointer durável. Essas evoluções continuam fora do MVP.

| Camada | Responsabilidade no MVP |
| --- | --- |
| `app/graph` | Estado, nós, rotas e compilação do `StateGraph`. |
| `app/services` | Regras determinísticas, autorização, SQLite, alertas, auditoria e validação. |
| `app/llm` | Carregamento e prompt do adapter final; contrato de geração. |
| `app/cli.py` | Contexto demo, entrada, exibição segura e evidências da execução. |
| `tests/` | Unitários com fakes e integração com SQLite sintético. |

As tools LangChain existentes podem ser adaptadores finos de serviços, mas não são a autoridade do fluxo. O ReAct em `main.py` permanece legado até a demonstração do novo CLI passar.

As assinaturas, modelos Pydantic, responsabilidades, erros e checklist de handoff entre o grafo e essas dependências estão definidos em [langgraph-backend-contract.md](langgraph-backend-contract.md). O StateGraph depende somente dessas portas, permitindo testar suas rotas com fakes antes da integração com SQLite ou o adapter real.

## 7. Estado e contratos

O estado contém mensagens, `RequestContext`, `audit_id`, pergunta original, paciente e condição normalizados, intenção, autorização, contexto recuperado, fontes, análise, criticidade, alerta, rascunho, resposta final, resultado da validação, violações, contador de revisão e código de erro.

`audit_id`, pergunta original, `RequestContext` e versões de regras/protocolos são imutáveis depois de `inicializar_execucao`. Cada nó retorna somente o fragmento de estado que possui. `messages` usa `add_messages`; fontes são deduplicadas por `id`.

~~~python
class Source(BaseModel):
    id: str                 # Ex.: protocol:hipertensao-gestacional:v1
    title: str
    snippet: str | None = None
    kind: Literal["protocolo", "prontuario", "exame", "documento"]
~~~

Fontes são enumeradas no prompt como `[S1]`, `[S2]` e assim por diante, cada uma mapeada para um `Source.id` existente no estado. A resposta final só pode citar esses marcadores enumerados; o validador verifica seu mapeamento para fontes recuperadas. Essa regra prova rastreabilidade de fontes recuperadas, mas não afirma verificar semanticamente toda paráfrase produzida por texto livre.

## 8. Workflow

Os nós são:

1. `inicializar_execucao`
2. `interpretar_pergunta`
3. `autorizar_acesso`
4. `buscar_prontuario`
5. `verificar_exames`
6. `consultar_protocolo`
7. `analisar_informacoes`
8. `registrar_alerta_simulado`
9. `gerar_resposta`
10. `validar_seguranca`

`interpretar_pergunta` usa parsing determinístico: extrai ID em formato aceito e normaliza condição contra o catálogo de protocolos. Dúvida, conflito ou ausência de ambos os campos resulta em clarificação. O MVP não depende de uma `general_llm`; uma interface para análise estruturada por LLM poderá ser adicionada futuramente sem conceder autoridade de segurança a ela.

~~~mermaid
flowchart TD
  START --> init[inicializar_execucao] --> interpret[interpretar_pergunta]
  interpret --> patient{Paciente identificado?}
  patient -->|sim| auth[autorizar_acesso]
  auth -->|negado, ausente ou inválido| limited[resposta de limitação]
  auth -->|autorizado| record[buscar_prontuario] --> exams[verificar_exames]
  patient -->|não| condition{Condição reconhecida?}
  condition -->|não| clarify[pedir dados mínimos]
  condition -->|sim| protocol_general[consultar_protocolo]
  exams --> condition_after_record{Condição reconhecida?}
  condition_after_record -->|sim| protocol[consultar_protocolo]
  condition_after_record -->|não| analysis[analisar_informacoes]
  protocol --> analysis
  protocol_general --> analysis
  analysis --> critical{Regra crítica?}
  critical -->|sim e paciente| alert[registrar_alerta_simulado] --> answer[gerar_resposta]
  critical -->|sim sem paciente| escalation[resposta de escalonamento]
  critical -->|não| answer
  answer --> safety[validar_seguranca]
  limited --> safety
  clarify --> safety
  escalation --> safety
  safety -->|aprovada| END
  safety -->|uma revisão| answer
  safety -->|bloqueada| blocked[mensagem segura de bloqueio] --> END
~~~

Regras de roteamento:

- Sem paciente e sem condição: clarificar sem consulta e sem LLM.
- Condição sem paciente: recuperar somente protocolo e responder de forma geral.
- Paciente sem condição: recuperar prontuário e exames autorizados; não consultar protocolo nulo.
- Paciente e condição: recuperar prontuário, exames e protocolo autorizados/aplicáveis.
- Acesso negado: nunca chamar repositório clínico.
- Criticidade sem paciente: escalonar, sem alerta de paciente.
- Criticidade com paciente: persistir alerta simulado antes da resposta.

## 9. LLM e geração final

O adapter Qwen3.5-4B + LoRA é a única LLM obrigatória do MVP e é injetado exclusivamente em `gerar_resposta`. Antes de uma execução clínica normal, o CLI executa smoke test que comprova carregar o adapter correto e registra sua versão no audit log.

Não há fallback silencioso para modelo-base. Se o adapter não estiver disponível, o fluxo encerra com erro seguro e auditado. A opção legada `--finetuned` deve ser removida ou renomeada para não alegar carregar o adapter.

O prompt final contém apenas pergunta, fatos autorizados, fontes enumeradas e limites de resposta. O modelo não recebe poderes para escolher tools, pacientes ou rotas. A geração é acumulada por completo; nenhum token de rascunho é exibido antes de `validar_seguranca` aprová-lo.

## 10. Segurança e validação

O validador determinístico é a autoridade final. Ele:

- exige fontes citadas existentes no estado;
- bloqueia resposta individual sem contexto autorizado suficiente;
- bloqueia prescrição, dose, posologia e ajuste autônomo por padrões e regras explícitas;
- permite fato recuperado apenas quando atribuído à fonte apropriada;
- exige escalonamento humano para criticidade;
- permite uma única reformulação;
- substitui falha final por template seguro, sem vazar rascunho, prompt ou dados internos.

O validador oferece controles demonstráveis, não garantia de validação semântica total de toda frase livre. Essa limitação deve constar no README e no relatório técnico.

## 11. Criticidade, alertas e auditoria

Criticidade vem de regras Python pequenas, versionadas e associadas a fixtures sintéticas. A LLM não determina nem dispara alertas.

`alerts` armazena `audit_id`, paciente opcional, motivo/código de regra, versão da regra, timestamp e chave de idempotência única. O alerta é sempre chamado de **simulado registrado**, nunca de alerta enviado/notificado para equipe. Se sua persistência falhar, o workflow não entrega resposta clínica normal: audita a falha e retorna limitação segura.

`audit_events` registra `audit_id`, início/fim de nó, rota, duração, IDs de fontes, versão de protocolo/regra, resultado de validação, alerta e código de erro. Não registra prontuário integral, prompts completos, chaves ou texto clínico desnecessário.

SQLite é suficiente para fixtures, alertas e auditoria da demonstração. Filas, outbox distribuído, alertas externos e observabilidade operacional são evoluções fora de escopo.

## 12. Dados e repositório

O repositório encapsula SQLite por injeção de fábrica/conexão, inicializa fixtures idempotentes e expõe contratos tipados. Dados atuais genéricos serão substituídos por pacientes, exames e protocolos sintéticos materno-infantis, todos identificados como demonstração.

Protocolos e regras de criticidade possuem versão. Cada fonte tem ID estável; a execução registra as versões efetivamente usadas. Não há dados reais de paciente no repositório, logs, vídeo ou dataset entregue.

## 13. Falhas, memória e API futura

Falha de parsing, repositório, carregamento do adapter ou validação encerra o fluxo sem novas consultas e produz mensagem segura/auditada. Consultas de leitura podem ser repetidas com segurança; efeitos de alerta usam idempotência e não devem receber retry automático cego.

`MemorySaver` mantém contexto somente durante o processo e não concede autorização. O CLI gera ou recebe um `conversation_id` de demonstração; reiniciar o processo perde contexto, limitação que deve ser exibida na documentação.

FastAPI/SSE não bloqueia a entrega. Se implementada depois, a API deve reconstituir o contexto de autorização no backend e emitir somente texto já validado, fontes e metadados mínimos de tools — nunca prontuário integral em eventos SSE.

## 14. Estrutura de código

~~~text
app/
├── graph/       state.py, nodes.py, routes.py, workflow.py
├── llm/         factory.py, prompts.py, schemas.py
├── services/    authorization.py, medical_repository.py,
│                criticality.py, alert_service.py,
│                safety_validator.py, audit_logger.py
└── cli.py
tests/
├── unit/
└── integration/
docs/
└── relatorio-tecnico.md
~~~

## 15. Testes e evidências

Testes unitários usam serviços e LLMs falsas determinísticas. O adapter real aparece somente em smoke test separado. O aceite deve cobrir:

| Caso | Resultado esperado |
| --- | --- |
| Paciente autorizado + condição | Prontuário, exames e protocolo; fontes e resposta validada. |
| Paciente sem condição | Prontuário/exames, sem protocolo nulo. |
| Condição sem paciente | Somente protocolo e resposta geral. |
| Sem paciente e sem condição | Clarificação sem consulta. |
| ID não autorizado | Nenhuma leitura clínica e resposta segura. |
| ID inexistente | Ausência controlada, sem dados inventados. |
| Caso crítico com paciente | Alerta idempotente antes da resposta. |
| Caso crítico sem paciente | Escalonamento, sem alerta vinculado. |
| Falha de alerta | Limitação segura e auditoria. |
| Prescrição/dose nova | Reformulação ou bloqueio. |
| Citação inexistente | Bloqueio antes de exibir a resposta. |
| Falha de repositório/modelo | Limitação segura e auditoria. |
| Mesmo `thread_id` | Contexto no mesmo processo, sem ampliar autorização. |
| Reinício | Perda de memória documentada. |

## 16. Plano de entrega

1. Congelar SHA, alinhar README e dependências.
2. Acordar e versionar o contrato em [langgraph-backend-contract.md](langgraph-backend-contract.md).
3. Criar o backend local de referência: serviços injetáveis, schema SQLite, fixtures sintéticas, `alerts` e `audit_events`.
4. Implementar estado, rotas e nós determinísticos do `StateGraph` com fakes das portas.
5. Implementar fontes, criticidade, alerta idempotente e validador.
6. Integrar adapter Qwen3.5-4B + LoRA exclusivamente em `gerar_resposta`; remover alegação incorreta de `--finetuned`.
7. Criar testes unitários/integração e smoke test do adapter.
8. Atualizar README, relatório técnico e roteiro de vídeo.
9. Implementar FastAPI/SSE somente se sobrar tempo após a validação do núcleo.

`pyproject.toml` e `uv.lock` são a fonte de verdade de dependências. O README deve usar `uv sync`; `requirements.txt` deve ser removido da instrução ou regenerado de modo compatível.

## 17. Critérios de sucesso

- O CLI usa `StateGraph`, não ReAct, para o caminho demonstrado.
- Todas as leituras identificáveis são autorizadas antes do repositório.
- Toda saída exibida foi validada antes da apresentação.
- Fontes exibidas foram efetivamente recuperadas e suas citações são verificadas.
- Alertas são persistidos, idempotentes, auditáveis e explicitamente simulados.
- Dados da demonstração são sintéticos e materno-infantis.
- O StateGraph possui testes de integração contra o backend local SQLite de referência, além dos testes unitários com fakes.
- Testes de rotas, acesso, fontes, falhas, criticidade e validação passam sem API externa.
- O adapter fine-tuned correto é carregado e demonstrado apenas como gerador final.
- README, relatório e vídeo mostram arquitetura, limites, logs, fontes e evidências exigidas pela Fase 3.
