# Guia de configuração e execução local

Este guia descreve como instalar, validar e demonstrar o workflow LangGraph. O projeto usa exclusivamente dados sintéticos; não use dados reais de pacientes.

## 1. Pré-requisitos

- Python 3.12 e [uv](https://docs.astral.sh/uv/).
- Git.
- Uma chave OpenAI para o fluxo real (`gpt-4.1-mini`).
- Para gerar a resposta final real, o adapter LoRA e capacidade suficiente para o modelo-base Qwen3.5-4B.

Na raiz do repositório, instale as dependências:

```bash
uv sync --group dev
```

## 2. Validar o workflow sem modelos reais

Esta é a opção recomendada para desenvolvimento local. Ela executa o `StateGraph` completo com LLMs determinísticas: autorização, SQLite, fontes, criticidade, alerta simulado, revisão e validação.

```bash
uv run pytest -q

uv run python -m app.cli --fake \
  --authorized-patient P-042 \
  "Paciente P-042 com hipertensão gestacional tem exames pendentes?"
```

O resultado deve exibir fontes `[S1]`, `[S2]`, `[S3]` e `Alerta simulado registrado.`

Teste também uma tentativa sem autorização; ela não pode consultar prontuário:

```bash
uv run python -m app.cli --fake \
  "Paciente P-042 com hipertensão gestacional tem exames pendentes?"
```

## 3. Configurar `.env`

Copie o exemplo e preencha os valores. O `.env` é ignorado pelo Git e o CLI o carrega automaticamente.

```bash
cp .env.example .env
```

Conteúdo esperado:

```env
OPENAI_API_KEY=sua_chave_openai
QWEN_LORA_ADAPTER_PATH=/home/igor/repos/fiap/TechV3/modelos/lora_model
QWEN_BASE_MODEL=unsloth/Qwen3.5-4B
```

Não compartilhe nem versione a chave OpenAI.

## 4. Baixar o adapter LoRA

O adapter é público no repositório Hugging Face [`emidiosouza/assistente-maternidade`](https://huggingface.co/emidiosouza/assistente-maternidade). Baixe-o para o caminho configurado no `.env`:

```bash
mkdir -p modelos/lora_model
uv run hf download emidiosouza/assistente-maternidade \
  --local-dir modelos/lora_model
```

Confirme os artefatos:

```bash
ls modelos/lora_model/adapter_config.json
ls modelos/lora_model/adapter_model.safetensors
```

O adapter configura `unsloth/Qwen3.5-4B` como o modelo-base. O download do adapter é pequeno (cerca de 65 MB), mas o modelo-base é baixado na primeira execução e ocupa cerca de 9,35 GB.

## 5. Smoke tests das integrações reais

Após configurar o `.env` e baixar o adapter, execute cada integração isoladamente:

```bash
uv run python -m app.cli --smoke-general-llm
uv run python -m app.cli --smoke-final-answer-llm
```

Só depois de ambos passarem execute o fluxo real:

```bash
uv run python -m app.cli \
  --authorized-patient P-042 \
  "Paciente P-042 com hipertensão gestacional tem exames pendentes?"
```

## 6. Limitação deste computador

O computador usado neste repositório tem RTX 2050 com 4 GB de VRAM e 15 GB de RAM. O loader atual não quantiza o Qwen3.5-4B; por isso, o adapter real não deve carregar de forma confiável nessa máquina. Use `--fake` para demonstrar localmente o workflow LangGraph.

Para a execução real do adapter, use uma GPU com ao menos 12–16 GB de VRAM, por exemplo uma T4 em Colab ou Kaggle. Não substitua o adapter por um modelo-base ou modelo menor sem registrar e revalidar a mudança.

## 7. Solução de problemas

| Sintoma | Ação |
| --- | --- |
| `uv: command not found` | Instale o uv e abra um novo terminal. |
| `OPENAI_API_KEY` ausente | Crie/preencha `.env`; o CLI o carrega automaticamente. |
| `QWEN_LORA_ADAPTER_PATH não configurado` | Preencha o caminho absoluto no `.env`. |
| Adapter não encontrado | Refaça o download e confira `adapter_config.json`. |
| Erro de memória/CUDA | Use `--fake` localmente ou mova o smoke test final para uma GPU maior. |
| `clinical_demo.db` apareceu | É banco SQLite derivado da demonstração e já está no `.gitignore`. |
