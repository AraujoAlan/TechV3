# Relatório técnico — Tech Challenge Fase 3

## 1. Resumo executivo

Este projeto implementa um MVP acadêmico de assistente clínico materno-infantil. Ele combina um modelo Qwen3.5-4B ajustado por LoRA para redigir respostas, um workflow `StateGraph` para controlar o fluxo clínico e serviços locais em SQLite para contexto, fontes, alertas simulados e auditoria.

O projeto opera exclusivamente com dados de demonstração. Os prontuários, exames e protocolos consultados em tempo de execução são sintéticos. O corpus usado no fine-tuning é um proxy público curado a partir de `AKCIT/MedPT`; ele não representa protocolos nem dados internos de um hospital real. Portanto, o MVP não deve ser empregado em assistência clínica, prescrição ou decisão autônoma.

## 2. Escopo e limites de atuação

O assistente apoia a consulta de informações disponíveis no contexto autorizado, mas não substitui avaliação profissional. As regras do MVP bloqueiam padrões de prescrição, dose, posologia e ajuste autônomo; casos críticos exigem orientação de avaliação humana e registram somente um alerta **simulado**.

Não fazem parte do MVP atual: API pública, autenticação corporativa, dados reais, notificação externa a equipes, checkpointer durável ou integração do frontend com o workflow. A integração frontend–backend via API é evolução planejada para a etapa final de produto e demonstração; ela deverá manter o backend como autoridade de autorização e validação.

## 3. Dados, preprocessing, anonimização e curadoria

Os notebooks versionados em `notebooks/` descrevem o pipeline de dados:

1. `01_extracao_escopo.ipynb` seleciona perguntas e respostas do dataset público `AKCIT/MedPT` para o domínio materno-infantil e registra justificativas de inclusão/exclusão.
2. `02_curadoria.ipynb` aplica filtros de qualidade, verificações de anonimização, deduplicação e retenção por cobertura mínima de condição.
3. `03_reescrita.ipynb` adapta perguntas originalmente voltadas a pacientes para o registro técnico do assistente. Itens reescritos são identificados para análise posterior.
4. `04_dataset_build.ipynb` constrói os splits e o formato de conversa usado no treino.

O MedPT é tratado como fonte previamente anonimizada segundo o seu dataset card, mas a curadoria ainda remove ou mascara possíveis identificadores residuais no texto. Isso não equivale a certificação de anonimização para uso clínico real. Os exemplos distribuídos no repositório ficam em `dataset_exemplo/`, com 50 registros para cada split (`train_amostra.jsonl`, `val_amostra.jsonl` e `test_amostra.jsonl`), e servem como evidência reproduzível do formato sem incluir prontuários locais.

O split não é aleatório por linha: `cluster_id` é usado como grupo no `StratifiedGroupKFold`. Assim, perguntas semelhantes de um mesmo cluster não aparecem simultaneamente em treino e validação/teste, reduzindo vazamento entre conjuntos. O formato final usa mensagens `system`, `user` e `assistant`; a instrução de sistema explicita apoio à decisão, ausência de prescrição autônoma e necessidade de avaliação profissional.

## 4. Fine-tuning da LLM

O treino está documentado em `notebooks/05_treino.ipynb`.

| Item | Configuração registrada |
| --- | --- |
| Modelo-base | `unsloth/Qwen3.5-4B` |
| Estratégia | SFT com Unsloth, QLoRA 4-bit e `SFTTrainer` |
| Adapter | LoRA, `r=16`, `lora_alpha=16`, `lora_dropout=0` |
| Módulos | projeções de atenção, mixer e MLP compatíveis com a arquitetura híbrida do Qwen3.5 |
| Épocas | 2 |
| Learning rate | `2e-4` |
| Batch por dispositivo | 2 |
| Acumulação de gradiente | 4 |
| Avaliação/checkpoint | a cada 250 passos |

Foram registrados 12.240 exemplos de treino, 3.060 passos e 32.464.896 parâmetros treináveis de 4.571.730.432 do modelo (0,71%). A loss de treino ao final foi `1,1778`. O adapter resultante está em `modelos/lora_model/`; seu `adapter_config.json` referencia o mesmo modelo-base e é aplicado pelo runtime sobre o modelo multimodal compatível antes da geração.

O treino calcula loss apenas sobre a resposta do assistente, não sobre a instrução de sistema ou a pergunta. Essa decisão evita otimizar o modelo para repetir a entrada e foca o ajuste na saída desejada.

## 5. Avaliação do modelo fine-tuned

`notebooks/06_avaliacao.ipynb` compara o modelo-base e o adapter LoRA no mesmo split de validação, com o mesmo procedimento de loss e com o adapter habilitado/desabilitado no mesmo modelo. A validação tem 1.530 registros: 243 com alvo humano preservado e 1.287 com resposta reescrita.

| Recorte de validação | Loss base | Loss LoRA | Redução relativa |
| --- | ---: | ---: | ---: |
| Geral | 2,2159 | 1,3049 | 41,1% |
| Alvo humano | 2,6878 | 1,9804 | 26,3% |
| Alvo reescrito por LLM | 2,1477 | 1,2026 | 44,0% |

Esses números mostram melhor aderência do adapter ao corpus de validação. Eles não comprovam segurança clínica, generalização para pacientes reais ou superioridade em todos os domínios. A diferença entre os recortes também é relevante: a perda é menor em respostas reescritas, portanto existe risco de o modelo se ajustar mais ao estilo produzido na etapa de reescrita do que a respostas humanas originais. A avaliação inclui inspeção qualitativa de respostas lado a lado, que deve permanecer sob revisão humana antes de qualquer alegação clínica.

## 6. Assistente com LangChain e LangGraph

O CLI `python -m app.cli` monta o `RequestContext` de demonstração e executa um `StateGraph`. `ChatOpenAI` via LangChain fornece o `general_llm` para interpretação estruturada, análise e crítica; ele não escolhe ferramentas, autorização, criticidade ou rotas. O `final_answer_llm` é Qwen+LoRA por padrão. Para validar o fluxo sem GPU, `FINAL_ANSWER_PROVIDER=openai` permite usar `gpt-4.1-mini` exclusivamente como provider final de teste.

~~~mermaid
flowchart TD
  start([Pergunta]) --> init[inicializar]
  init --> interpret[interpretar e normalizar condição]
  interpret --> has_patient{Paciente identificado?}
  has_patient -->|sim| authorize[autorizar acesso]
  authorize -->|autorizado| record[buscar prontuário e exames]
  authorize -->|negado| limited[limitação segura]
  record --> has_condition_after_record{Condição reconhecida?}
  has_condition_after_record -->|sim| protocol[consultar protocolo]
  has_condition_after_record -->|não| analyze[analisar contexto]
  has_patient -->|não| has_condition{Condição reconhecida?}
  has_condition -->|sim| protocol
  has_condition -->|não| limited
  protocol --> analyze[analisar contexto]
  analyze --> critical{critério crítico?}
  critical -->|sim, paciente| alert[registrar alerta simulado]
  critical -->|sim, sem paciente| limited
  critical -->|não| generate[gerar resposta]
  alert --> generate
  generate --> escalation[garantir escalonamento crítico]
  escalation --> critique[criticar resposta]
  critique --> validate[validar segurança]
  validate -->|revisar dentro do limite| generate
  validate -->|aprovada| answer([resposta com fontes])
  validate -->|bloqueada| limited
~~~

O repositório SQLite fornece prontuário, exame e protocolo sintéticos. Cada item recuperado origina uma `Source` estável, exibida como `[S1]`, `[S2]` e assim por diante. A autorização é verificada antes de qualquer consulta identificável; o identificador presente na pergunta não cria permissão.

## 7. Segurança, validação, explicabilidade e auditoria

O workflow aplica regras determinísticas para:

- validar o ID de paciente e normalizar condições do catálogo, incluindo `puerpério` → `puerperio`;
- impedir acesso a prontuário e exame sem autorização explícita;
- identificar criticidade a partir de regras versionadas e persistir alerta somente simulado;
- garantir orientação de avaliação humana em caso crítico, mesmo se a geração a omitir;
- bloquear citações fora das fontes recuperadas, falta de citação quando há fonte, prescrição/dose/posologia e afirmações individuais sem contexto autorizado;
- limitar reformulações com `MAX_RESPONSE_REVISIONS` — o padrão `1` permite uma geração inicial e, no máximo, uma revisão.

`clinical_demo.db` persiste eventos de auditoria minimizados por `audit_id`: início, conclusão, falha e uso de LLM. Quando disponível, `llm_usage` guarda modelo e tokens; `validate` grava quantidade e resumo de violações. Prompts, chaves, prontuário integral e rascunhos reprovados não são registrados. Alertas possuem chave de idempotência e status `simulated_recorded`.

As fontes tornam a origem do contexto verificável, mas a validação ainda não realiza fact-checking semântico de cada frase. Isso foi observado na pergunta geral sobre puerpério: o protocolo sintético era genérico e a geração apresentou detalhes além do texto recuperado. Uma citação existente não prova sustentação semântica integral; fontes e fixtures devem conter o nível de detalhe que se deseja responder.

## 8. Evidências de execução e testes

A suíte local possui 30 testes unitários e cobre contratos, rotas de acesso, criticidade, alertas idempotentes, validação, revisões, telemetria e carregamento do Qwen.

```bash
uv sync --group dev
uv run pytest
```

Foram executados cinco cenários reais com `gpt-4.1-mini` como provider final para avaliação ponta a ponta:

| Cenário | Resultado observado |
| --- | --- |
| P-042 autorizado, hipertensão gestacional | Fontes de prontuário/exame/protocolo, escalonamento humano e alerta simulado. |
| Pergunta geral sobre puerpério | Protocolo recuperado após normalização de condição; limitação semântica registrada na seção anterior. |
| P-101 autorizado, exames pendentes | Ausência de informação respondida sem inventar exame. |
| P-042 sem autorização | Limitação segura antes de qualquer consulta clínica. |
| P-999 autorizado, inexistente | Limitação segura após ausência controlada de prontuário. |

Os smoke tests separam a disponibilidade das integrações reais da suíte determinística:

```bash
uv run python -m app.cli --smoke-general-llm
uv run python -m app.cli --smoke-final-answer-llm
```

Para Qwen em GPU pequena, `QWEN_ENABLE_CPU_OFFLOAD=true` permite teste GPU+CPU, com maior uso de RAM e latência. `QWEN_MAX_NEW_TOKENS` afeta somente a geração Qwen; o provider OpenAI é limitado pelo serviço configurado, não por essa variável.

## 9. Reprodutibilidade e organização do código

`pyproject.toml` e `uv.lock` são as fontes de dependência. O código é organizado em `app/graph`, `app/llm`, `app/services` e `app/contracts`; interfaces permitem testes com fakes sem rede nem modelo pesado. O guia operacional completo está em [guia-execucao-local.md](guia-execucao-local.md), e as decisões de arquitetura e contratos estão em [design-doc-langgraph.md](design-doc-langgraph.md) e [langgraph-backend-contract.md](langgraph-backend-contract.md).

## 10. Próximos passos

1. Enriquecer os protocolos sintéticos e adicionar validação de suporte semântico entre afirmações e fontes.
2. Consolidar a avaliação final no split de teste e complementar a loss com rubrica humana de segurança, fidelidade às fontes e utilidade.
3. Implementar API autenticada para o `StateGraph`; a API deverá reconstruir o `RequestContext` no backend e expor somente resposta validada, fontes e metadados mínimos.
4. Integrar o frontend existente à API, removendo respostas mockadas e preservando estados de carregamento, fontes, limitações e alerta simulado.
5. Gravar vídeo de até 15 minutos cobrindo pipeline de dados/fine-tuning, smoke test, caso crítico autorizado, bloqueio de acesso, fontes, audit log e limitações conhecidas.

## 11. Conclusão

O MVP demonstra o ciclo técnico requerido: dados curados para fine-tuning, adapter LoRA, integração LangChain/LangGraph, consulta estruturada contextualizada, controles de segurança, fontes rastreáveis e auditoria. Os resultados de loss indicam adaptação ao corpus, enquanto os testes de fluxo demonstram autorização, bloqueio seguro e escalonamento determinístico. As limitações são explícitas: não há dados reais, validação semântica completa, API autenticada ou integração frontend–backend nesta etapa.
