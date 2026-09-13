# Design Doc — Workflow LangGraph do Assistente Clínico

**Status:** Implementado no MVP local

**Base:** `main` em `5d9acf3`, ou sucessor validado no início da implementação

**Branch de implementação:** `feat/langgraph-workflow`

**Escopo:** demonstração de assistente clínico materno-infantil com dados sintéticos

## 1. Resumo

Este documento substitui a orquestração implícita do agente ReAct por um `StateGraph` de domínio. O grafo controla, em ordem verificável, interpretação estruturada, autorização, recuperação de contexto, análise, criticidade, alerta simulado, geração, validação, fontes e auditoria.

O objetivo é atender à Fase 3 com uma demonstração local, modular e testável. Não é um sistema hospitalar de produção, não processa dados reais e não notifica equipes reais.

## 2. Contexto e fatos verificados

Antes deste MVP, o protótipo ReAct usava tools e `MemorySaver`, sem autorização antes de ler prontuários, validação determinística, fontes rastreáveis ou auditoria persistida. O caminho atual de demonstração é o `StateGraph` descrito neste documento, com SQLite e fixtures materno-infantis sintéticas.

O adapter Qwen3.5-4B + LoRA foi treinado e avaliado nos notebooks, mas ainda não é carregado pelo runtime. A opção legada `main.py --finetuned` carrega `Qwen/Qwen2.5-1.5B-Instruct`, isto é, um modelo-base de demonstração, não o adapter treinado. Ela não pode ser usada como prova de integração do fine-tuning.

## 3. Objetivos

- Usar um `StateGraph` compilado no CLI.
- Consultar prontuários e exames somente para pacientes explicitamente autorizados no contexto de demonstração.
- Usar dados, protocolos e pacientes sintéticos coerentes com gestação, puerpério ou bebês até um ano.
- Contextualizar respostas com dados recuperados e fontes rastreáveis.
- Aplicar regras determinísticas de criticidade, alertas simulados idempotentes e validação antes de exibir qualquer resposta.
- Usar `general_llm` para interpretação, análise estruturada, clarificação e crítica auxiliar, sem delegar controles de segurança a ele.
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
  |-- rotas e controles determinísticos
  |-- general_llm (GPT-4.1 mini) para interpretação e análise estruturada
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
| `app/llm` | Contratos, prompts e carregamento de `general_llm` e do adapter final. |
| `app/cli.py` | Contexto demo, entrada, exibição segura e evidências da execução. |
| `tests/` | Unitários com fakes e integração com SQLite sintético. |

As tools LangChain existentes podem ser adaptadores finos de serviços, mas não são a autoridade do fluxo. O ReAct em `main.py` permanece legado até a demonstração do novo CLI passar.

As assinaturas, modelos Pydantic, responsabilidades, erros e checklist de handoff entre o grafo e essas dependências estão definidos em [langgraph-backend-contract.md](langgraph-backend-contract.md). O contrato deve incluir a porta de `general_llm`, além da já existente `FinalAnswerLLM`. O StateGraph depende somente dessas portas, permitindo testar suas rotas com fakes antes da integração com SQLite, `general_llm` ou o adapter real.

## 7. Estado e contratos

O estado contém mensagens, `RequestContext`, `audit_id`, pergunta original, paciente e condição normalizados, intenção, autorização, contexto recuperado, fontes, análise, criticidade, alerta, rascunho, resposta final, resultado da crítica auxiliar, resultado da validação, violações, contador de revisão e código de erro.

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
10. `garantir_escalonamento_critico`
11. `criticar_resposta`
12. `validar_seguranca`

O workflow possui duas dependências de LLM, injetadas por papel e nunca escolhidas livremente por um nó:

| Dependência | Modelo | Nós permitidos | Limites |
| --- | --- | --- | --- |
| `general_llm` | OpenAI `gpt-4.1-mini` | `interpretar_pergunta`, `analisar_informacoes`, clarificação e `criticar_resposta` | Retorna saída estruturada validada; não chama tools, não acessa dados e não toma decisões de segurança. |
| `final_answer_llm` | Qwen3.5-4B + adapter LoRA fine-tuned (padrão) ou OpenAI configurável para teste ponta a ponta | Somente `gerar_resposta` | Redige a resposta final somente a partir de fatos autorizados e fontes recuperadas. |

`interpretar_pergunta` usa `general_llm` para propor intenção, condição e referências ao paciente em formato estruturado. O ID precisa corresponder ao formato aceito e é validado deterministicamente; a condição é normalizada contra o catálogo de protocolos, incluindo remoção determinística de acentos e equivalência entre espaços, `_` e `-` (por exemplo, `puerpério` → `puerperio`). Dúvida, conflito ou ausência de campos mínimos resulta em clarificação, sem consulta clínica. A LLM não pode inventar identificadores, ampliar permissões ou decidir rotas de negócio.

Uso de LLM por nó:

| Nó | Uso de LLM | Autoridade final |
| --- | --- | --- |
| `inicializar_execucao` | Não usa LLM. | Código. |
| `interpretar_pergunta` | `general_llm` propõe campos estruturados. | Validador determinístico e catálogo de protocolos. |
| `autorizar_acesso`, `buscar_prontuario`, `verificar_exames`, `consultar_protocolo` | Não usam LLM. | Serviços Python. |
| `analisar_informacoes` | `general_llm` sintetiza achados estruturados a partir do contexto autorizado. | Dados recuperados e regras determinísticas. |
| `registrar_alerta_simulado` | Não usa LLM. | Serviço de criticidade e alerta. |
| `gerar_resposta` | Exclusivamente `final_answer_llm`. | Validador de segurança e fontes. |
| `garantir_escalonamento_critico` | Não usa LLM. Se a regra de criticidade for positiva, acrescenta deterministicamente a orientação de busca imediata de avaliação humana quando ela não estiver no rascunho. | Código; não depende da aderência do modelo ao prompt. |
| `criticar_resposta` | `general_llm` retorna crítica estruturada de coerência, citações e linguagem indevida. | Não aprova, bloqueia, nem inicia revisão. |
| `validar_seguranca` | Não usa LLM; recebe a crítica como evidência auxiliar. | Validador determinístico. |

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
  critical -->|sim sem paciente| limited
  critical -->|não| answer
  answer --> escalation_check[garantir_escalonamento_critico]
  escalation_check --> critic[criticar_resposta]
  critic --> safety[validar_seguranca]
  limited --> END
  clarify --> END
  safety -->|aprovada| END
  safety -->|revisão e contador = 0| revise[incrementar contador de revisão] --> answer
  safety -->|bloqueada ou contador = 1| blocked[mensagem segura de bloqueio] --> END
~~~

Regras de roteamento:

- Sem paciente e sem condição: clarificar sem consulta clínica; `general_llm` pode ajudar a formular o pedido de dados mínimos.
- Condição sem paciente: recuperar somente protocolo e responder de forma geral.
- Paciente sem condição: recuperar prontuário e exames autorizados; não consultar protocolo nulo.
- Paciente e condição: recuperar prontuário, exames e protocolo autorizados/aplicáveis.
- Acesso negado: nunca chamar repositório clínico.
- Criticidade sem paciente: encerrar com limitação segura, sem alerta vinculado.
- Criticidade com paciente: persistir alerta simulado antes da resposta.
- Após `gerar_resposta`, `garantir_escalonamento_critico` preserva o rascunho não crítico. Para caso crítico, garante a orientação fixa de busca imediata de avaliação humana antes da crítica e validação; isso não depende de a LLM ter seguido o prompt.
- `gerar_resposta` sempre segue para `garantir_escalonamento_critico`, `criticar_resposta` e então para `validar_seguranca`; a crítica é auditável e não toma decisão de rota.
- A revisão é permitida enquanto `contador_de_revisão < MAX_RESPONSE_REVISIONS`: o grafo incrementa o contador, fornece as violações determinísticas para `gerar_resposta` e repete o ciclo. O padrão `MAX_RESPONSE_REVISIONS=1` resulta em no máximo duas gerações por execução; ao atingir o limite, uma nova reprovação segue para a mensagem segura de bloqueio.

### 8.1 Exemplos de execução

Os exemplos mostram o caminho completo desde a mensagem até a saída validada. `general_llm` é OpenAI `gpt-4.1-mini`; `final_answer_llm` é Qwen3.5-4B + adapter LoRA por padrão, podendo ser OpenAI configurável para teste ponta a ponta.

#### Paciente autorizado e caso crítico

~~~mermaid
flowchart TD
  user[Mensagem: Paciente P-042 com hipertensão gestacional tem exames pendentes?]
  interpret[interpretar_pergunta\n general_llm]
  auth[autorizar_acesso\n determinístico]
  record[buscar_prontuario\n serviço]
  exams[verificar_exames\n serviço]
  protocol[consultar_protocolo\n serviço]
  analysis[analisar_informacoes\n general_llm]
  critical{regra de criticidade\n determinística}
  alert[registrar_alerta_simulado\n serviço idempotente]
  answer[gerar_resposta\n final_answer_llm]
  escalation[garantir_escalonamento_critico\n determinístico]
  critic[criticar_resposta\n general_llm]
  safety[validar_seguranca\n determinístico]
  final[Resposta final validada\n fontes e alerta simulado]

  user --> interpret --> auth -->|autorizado| record --> exams --> protocol --> analysis --> critical
  critical -->|crítico| alert --> answer --> escalation --> critic --> safety -->|aprovada| final
  safety -->|revisão e contador = 0| answer
  safety -->|bloqueada ou contador = 1| blocked[mensagem segura de bloqueio]
~~~

#### Pergunta geral, sem identificação de paciente

~~~mermaid
flowchart TD
  user[Mensagem: Quais sinais exigem atenção na hipertensão gestacional?]
  interpret[interpretar_pergunta\n general_llm]
  patient{paciente identificado?\n determinístico}
  protocol[consultar_protocolo\n serviço]
  analysis[analisar_informacoes\n general_llm]
  critical{regra de criticidade\n determinística}
  answer[gerar_resposta\n final_answer_llm]
  escalation[garantir_escalonamento_critico\n determinístico]
  critic[criticar_resposta\n general_llm]
  safety[validar_seguranca\n determinístico]
  final[Resposta geral validada\n fontes do protocolo]

  user --> interpret --> patient -->|não| protocol --> analysis --> critical
  critical -->|sem criticidade individual| answer --> escalation --> critic --> safety -->|aprovada| final
  safety -->|revisão e contador = 0| answer
  safety -->|bloqueada ou contador = 1| blocked[mensagem segura de bloqueio]
~~~

## 9. LLM e geração final

`general_llm` é OpenAI `gpt-4.1-mini` e é obrigatório nos nós permitidos na seção anterior. Ele recebe apenas a pergunta ou dados já autorizados e delimitados, devolve saída estruturada conforme schema e suas falhas, recusas ou respostas inválidas encerram a etapa em clarificação ou limitação segura. Em `criticar_resposta`, devolve violações candidatas e justificativas associadas a fontes; não aprova, bloqueia ou repete o fluxo. Não há fallback que transforme um modelo textual em autoridade de acesso, criticidade ou validação.

`final_answer_llm` é injetado exclusivamente em `gerar_resposta`. O provider padrão é Qwen3.5-4B + LoRA, carregado como modelo multimodal em 4 bits antes de aplicar o adapter; `QWEN_ENABLE_CPU_OFFLOAD=true` permite teste híbrido GPU+CPU em máquinas com pouca VRAM. Para validar o fluxo ponta a ponta sem carregar o Qwen, o CLI aceita `FINAL_ANSWER_PROVIDER=openai` e `OPENAI_FINAL_MODEL` (padrão `gpt-4.1-mini`). Os smoke tests são comandos explícitos do operador; o CLI não os executa automaticamente nem registra a versão do adapter no audit log.

Não há fallback silencioso para modelo-base. Se o adapter não estiver disponível, o fluxo encerra com erro seguro e auditado. A opção legada `--finetuned` deve ser removida ou renomeada para não alegar carregar o adapter.

O prompt final contém apenas pergunta, fatos autorizados, fontes enumeradas e limites de resposta. Nenhuma LLM recebe poderes para escolher tools, pacientes ou rotas. A geração é acumulada por completo; nenhum token de rascunho é exibido antes de `validar_seguranca` aprová-lo.

## 10. Segurança e validação

O validador determinístico é a autoridade final. Ele recebe a saída de `criticar_resposta` como evidência auxiliar de coerência clínica, citações e recomendações indevidas, mas uma crítica favorável nunca aprova uma resposta sozinha. O validador:

- exige fontes citadas existentes no estado;
- bloqueia resposta individual sem contexto autorizado suficiente;
- bloqueia prescrição, dose, posologia e ajuste autônomo por padrões e regras explícitas;
- permite fato recuperado apenas quando atribuído à fonte apropriada;
- exige escalonamento humano para criticidade;
- recebe o escalonamento crítico já garantido por um nó determinístico; continua verificando essa condição como defesa em profundidade;
- permite reformulações até o limite configurado;
- substitui falha final por template seguro, sem vazar rascunho, prompt ou dados internos.

O validador oferece controles demonstráveis, não garantia de validação semântica total de toda frase livre. Essa limitação deve constar no README e no relatório técnico.

## 11. Criticidade, alertas e auditoria

Criticidade vem de regras Python pequenas, versionadas e associadas a fixtures sintéticas. `general_llm` pode sintetizar achados que serão considerados pelas regras, mas não determina criticidade nem dispara alertas.

`alerts` armazena `audit_id`, paciente opcional, motivo/código de regra, versão da regra, timestamp e chave de idempotência única. O alerta é sempre chamado de **simulado registrado**, nunca de alerta enviado/notificado para equipe. Se sua persistência falhar, o workflow não entrega resposta clínica normal: audita a falha e retorna limitação segura.

`audit_events` registra `audit_id`, nó, evento, `details`, chave de idempotência e timestamp. Há eventos `started`, `completed`, `failed` e, para chamadas de LLM, `llm_usage` com modelo e tokens. Em `validate`, `details` inclui contador, quantidade e texto resumido das violações. Não registra prontuário integral, prompts completos, chaves ou texto clínico desnecessário.

SQLite é suficiente para fixtures, alertas e auditoria da demonstração. Filas, outbox distribuído, alertas externos e observabilidade operacional são evoluções fora de escopo.

## 12. Dados e repositório

O repositório encapsula SQLite por injeção de fábrica/conexão, inicializa fixtures idempotentes e expõe contratos tipados. Dados atuais genéricos serão substituídos por pacientes, exames e protocolos sintéticos materno-infantis, todos identificados como demonstração.

Protocolos e regras de criticidade possuem versão. Cada fonte tem ID estável; a execução registra as versões efetivamente usadas. Não há dados reais de paciente no repositório, logs, vídeo ou dataset entregue.

## 13. Falhas, memória e API futura

Falha de parsing, de `general_llm`, de repositório, de carregamento do adapter ou de validação encerra o fluxo sem novas consultas e produz mensagem segura/auditada. Consultas de leitura podem ser repetidas com segurança; efeitos de alerta usam idempotência e não devem receber retry automático cego.

O MVP atual não usa checkpointer nem memória conversacional durável. O CLI recebe um `conversation_id` de demonstração no `RequestContext`, mas cada execução é independente; esse identificador não concede autorização.

FastAPI/SSE não bloqueia a entrega. Se implementada depois, a API deve reconstituir o contexto de autorização no backend e emitir somente texto já validado, fontes e metadados mínimos de tools — nunca prontuário integral em eventos SSE.

## 14. Estrutura de código

~~~text
app/
├── graph/       state.py, workflow.py
├── llm/         factory.py, fakes.py
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

Testes unitários usam serviços e LLMs falsas determinísticas. As integrações reais de `general_llm` e do adapter final aparecem somente em smoke tests separados. O aceite deve cobrir:

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
| Execuções independentes com o mesmo `conversation_id` demo | Não compartilham memória nem ampliam autorização. |
| Reinício | Nenhuma memória conversacional é persistida. |

## 16. Plano de entrega

1. Congelar SHA, alinhar README e dependências.
2. Acordar e versionar o contrato em [langgraph-backend-contract.md](langgraph-backend-contract.md).
3. Criar o backend local de referência: serviços injetáveis, schema SQLite, fixtures sintéticas, `alerts` e `audit_events`.
4. Implementar estado, rotas e nós do `StateGraph`, incluindo as portas e fakes de `general_llm`, com controles determinísticos de segurança.
5. Implementar fontes, criticidade, alerta idempotente e validador.
6. Integrar `general_llm=OpenAI gpt-4.1-mini` somente nos nós permitidos e o adapter Qwen3.5-4B + LoRA exclusivamente em `gerar_resposta`; remover alegação incorreta de `--finetuned`.
7. Criar testes unitários/integração, com fakes das duas LLMs, e smoke tests de cada integração real.
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
- O `general_llm` é usado apenas para interpretação, análise estruturada, clarificação e crítica auxiliar, sem substituir decisões determinísticas.
- README, relatório e vídeo mostram arquitetura, limites, logs, fontes e evidências exigidas pela Fase 3.
