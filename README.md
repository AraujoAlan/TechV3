# Assistente Clínico Materno-Infantil — demonstração LangGraph

MVP acadêmico com dados inteiramente sintéticos. O caminho demonstrado é um `StateGraph` controlado: autorização antes de qualquer leitura identificável, fontes rastreáveis, criticidade determinística, alerta **simulado** persistido e validação antes da exibição.

Não é um sistema hospitalar, não aceita dados reais, não prescreve e não notifica equipes reais.

## Instalação e testes

`pyproject.toml` e `uv.lock` são as fontes de verdade de dependências.

```bash
uv sync --group dev
uv run pytest
```

## Demonstração local

O modo fake exercita todo o grafo sem rede ou modelo pesado:

```bash
uv run python -m app.cli --fake --authorized-patient P-042 "Paciente P-042 com hipertensão gestacional tem exames pendentes?"
```

Em uso normal, o CLI exige `OPENAI_API_KEY` para `gpt-4.1-mini` e `QWEN_LORA_ADAPTER_PATH` para o adapter LoRA de Qwen3.5-4B. Não há fallback para modelo-base.

```bash
uv run python -m app.cli --smoke-general-llm
uv run python -m app.cli --smoke-final-answer-llm
```

Os smoke tests acessam integrações reais e são separados da suíte determinística. A memória é apenas do processo e nunca amplia a autorização do `RequestContext`.

## Garantias demonstradas

- O modelo geral só interpreta, analisa e critica saídas estruturadas; não escolhe ferramentas nem decisões de segurança.
- O adapter fine-tuned só gera o texto final após recuperação autorizada.
- Fontes `[S#]` são validadas contra fontes efetivamente recuperadas.
- Dose, posologia, prescrição e ajuste autônomo são bloqueados por regras explícitas.
- Casos críticos exigem escalonamento humano; com paciente autorizado, um alerta simulado idempotente é registrado antes da resposta.

O validador é um controle demonstrável, não uma garantia de validação semântica absoluta de texto livre. Consulte o [guia de configuração e execução](docs/guia-execucao-local.md), a [arquitetura](docs/design-doc-langgraph.md) e o [contrato](docs/langgraph-backend-contract.md).
