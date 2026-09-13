# Assistente Clínico Materno-Infantil — demonstração LangGraph

MVP acadêmico de assistente clínico com um `StateGraph` controlado: autorização antes de leitura identificável, contexto SQLite, fontes rastreáveis, criticidade determinística, alerta **simulado** persistido e validação antes da exibição.

Os prontuários, exames e protocolos consultados em execução são sintéticos. O corpus de fine-tuning é um proxy público curado a partir de `AKCIT/MedPT`, descrito no [relatório técnico](docs/relatorio-tecnico.md); ele não representa dados internos de hospital. Não é um sistema hospitalar, não aceita dados reais, não prescreve e não notifica equipes reais.

## Instalação e testes

`pyproject.toml` e `uv.lock` são as fontes de verdade de dependências.

```bash
uv sync --group dev
uv run pytest
```

## Configuração

Copie o arquivo de exemplo e preencha a chave OpenAI:

```bash
cp .env.example .env
```

`OPENAI_API_KEY` é necessária no fluxo real porque `gpt-4.1-mini` interpreta, analisa e critica. O provider da resposta final é configurável:

- `FINAL_ANSWER_PROVIDER=qwen` é o padrão e usa Qwen3.5-4B + adapter LoRA; requer `QWEN_LORA_ADAPTER_PATH` e GPU/RAM compatíveis.
- `FINAL_ANSWER_PROVIDER=openai` usa `OPENAI_FINAL_MODEL=gpt-4.1-mini` em `gerar_resposta`, permitindo testar o fluxo ponta a ponta sem carregar o Qwen localmente.

Não há fallback automático entre providers ou para modelo-base. As variáveis de offload, tokens Qwen e revisões estão documentadas no [guia local](docs/guia-execucao-local.md).

## Demonstração local

O modo fake exercita todo o grafo sem rede ou modelo pesado:

```bash
uv run python -m app.cli --fake \
  --authorized-patient P-042 \
  "Paciente P-042 com hipertensão gestacional tem exames pendentes?"
```

Para testar o fluxo real com GPT-4.1 mini também como gerador final:

```bash
FINAL_ANSWER_PROVIDER=openai \
OPENAI_FINAL_MODEL=gpt-4.1-mini \
MAX_RESPONSE_REVISIONS=1 \
uv run python -m app.cli \
  --authorized-patient P-042 \
  "Paciente P-042 com hipertensão gestacional tem exames pendentes?"
```

Smoke tests das integrações reais:

```bash
uv run python -m app.cli --smoke-general-llm
uv run python -m app.cli --smoke-final-answer-llm
```

Com provider Qwen, o segundo comando carrega modelo-base e adapter; com provider OpenAI, ele faz uma geração curta. Nenhum smoke test executa o `StateGraph` ou consulta SQLite.

## Garantias demonstradas

- `general_llm` somente interpreta, analisa e critica saídas estruturadas; não decide autorização, rotas, criticidade ou aprovação.
- O provider final só recebe contexto autorizado e fontes recuperadas.
- Fontes `[S#]` são validadas contra fontes efetivamente recuperadas.
- Dose, posologia, prescrição e ajuste autônomo são bloqueados por regras explícitas.
- Casos críticos exigem escalonamento humano; o nó determinístico garante essa orientação quando a geração a omite. Com paciente autorizado, um alerta simulado idempotente é registrado antes da resposta.
- `MAX_RESPONSE_REVISIONS=1` permite uma geração inicial e no máximo uma revisão.
- Auditoria minimizada registra eventos de nó, uso de LLM e violações, sem prompts, chaves, prontuário integral ou rascunhos reprovados.

O MVP não possui memória conversacional persistente. O `conversation_id` de demonstração não concede autorização. O validador é um controle demonstrável, não uma garantia de validação semântica absoluta de texto livre.


## API e interface web

```bash
# API (demo com LLMs determinísticas)
API_USE_FAKES=true DEMO_AUTHORIZED_PATIENT_IDS=P-042 \
  uv run uvicorn app.api.app:app --reload --port 8000

# Frontend (outro terminal)
cd frontend && echo 'VITE_USE_MOCK=false' > .env.local && npm run dev
```

Contrato: `POST /api/chat` recebe `{ "question", "conversation_id?" }` e devolve
apenas a resposta já validada (`answer`, `sources`, `outcome`, `alert`). Detalhes
em [frontend/CONTRATO.md](frontend/CONTRATO.md).

## Documentação

- [Guia de configuração e execução local](docs/guia-execucao-local.md)
- [Design do workflow LangGraph](docs/design-doc-langgraph.md)
- [Contrato entre grafo e serviços](docs/langgraph-backend-contract.md)
- [Relatório técnico da Fase 3](docs/relatorio-tecnico.md)
- [Requisitos do Tech Challenge](docs/tech_challenge_fase_3.md)
