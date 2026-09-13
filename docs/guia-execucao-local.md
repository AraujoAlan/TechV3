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
QWEN_LORA_ADAPTER_PATH=/caminho/absoluto/para/modelos/lora_model
QWEN_BASE_MODEL=unsloth/Qwen3.5-4B
QWEN_ENABLE_CPU_OFFLOAD=false
QWEN_CPU_OFFLOAD_MAX_MEMORY=12GiB
QWEN_MAX_NEW_TOKENS=256
MAX_RESPONSE_REVISIONS=1
FINAL_ANSWER_PROVIDER=qwen
OPENAI_FINAL_MODEL=gpt-4.1-mini
```

Não compartilhe nem versione a chave OpenAI. Após baixar o adapter na seção seguinte, obtenha um caminho absoluto portável com:

```bash
uv run python -c "from pathlib import Path; print(Path('modelos/lora_model').resolve())"
```

Copie o resultado para `QWEN_LORA_ADAPTER_PATH`.

## 4. Baixar o adapter LoRA

O adapter é público no repositório Hugging Face [`emidiosouza/assistente-maternidade`](https://huggingface.co/emidiosouza/assistente-maternidade). Baixe-o para o caminho configurado no `.env`:

```bash
ADAPTER_DIR="$(pwd)/modelos/lora_model"
mkdir -p "$ADAPTER_DIR"
uv run hf download emidiosouza/assistente-maternidade \
  --local-dir "$ADAPTER_DIR"
```

Confirme os artefatos:

```bash
ls "$ADAPTER_DIR/adapter_config.json"
ls "$ADAPTER_DIR/adapter_model.safetensors"
```

O adapter configura `unsloth/Qwen3.5-4B` como o modelo-base. O download do adapter é pequeno (cerca de 65 MB), mas o modelo-base é baixado na primeira execução e ocupa cerca de 9,35 GB.

## 5. Smoke tests das integrações reais

Após configurar o `.env` e baixar o adapter, execute cada integração isoladamente:

```bash
uv run python -m app.cli --smoke-general-llm
uv run python -m app.cli --smoke-final-answer-llm
```

`--smoke-general-llm` confirma que `OPENAI_API_KEY` permite ao `gpt-4.1-mini` retornar uma interpretação estruturada. Com `FINAL_ANSWER_PROVIDER=qwen`, `--smoke-final-answer-llm` carrega tokenizer, modelo-base e adapter LoRA, sem executar o `StateGraph` nem gerar resposta. Com `FINAL_ANSWER_PROVIDER=openai`, esse mesmo comando faz uma geração curta para verificar o provider OpenAI; ainda não executa o `StateGraph` nem consulta SQLite.

Em uma GPU pequena, é possível testar o carregamento híbrido, mantendo módulos que não couberem na GPU em RAM/FP32:

```bash
QWEN_ENABLE_CPU_OFFLOAD=true \
QWEN_CPU_OFFLOAD_MAX_MEMORY=12GiB \
QWEN_MAX_NEW_TOKENS=64 \
uv run python -m app.cli --smoke-final-answer-llm
```

Isso é apenas um teste local: requer bastante RAM e pode ser muito lento durante a geração. Mantenha a variável como `false` para a execução normal em uma GPU compatível.

`QWEN_MAX_NEW_TOKENS` limita o tamanho da resposta final e usa `256` como padrão. Para validar geração em uma máquina com offload CPU, prefira `32` ou `64`; em uma GPU com VRAM suficiente, `256` oferece mais espaço para uma resposta completa.

`MAX_RESPONSE_REVISIONS` define quantas gerações adicionais podem ocorrer após a resposta inicial reprovar na validação. O padrão `1` permite no máximo duas gerações e duas críticas; use `0` para limitar o fluxo a uma única geração e uma crítica.

Para validar o fluxo completo sem carregar o Qwen local, configure `FINAL_ANSWER_PROVIDER=openai`. O provider usa `OPENAI_FINAL_MODEL=gpt-4.1-mini` por padrão e mantém as mesmas etapas de crítica, validação, auditoria e alerta:

```bash
FINAL_ANSWER_PROVIDER=openai \
MAX_RESPONSE_REVISIONS=0 \
uv run python -m app.cli \
  --authorized-patient P-042 \
  "Paciente P-042 com hipertensão gestacional tem exames pendentes?"
```

O padrão permanece `FINAL_ANSWER_PROVIDER=qwen`; não há fallback automático para OpenAI.

## Auditoria e consumo do OpenAI

Cada execução registra no SQLite `clinical_demo.db` eventos `started`, `completed` e `failed`. Nos nós que chamam OpenAI (`interpret`, `analyze`, `critique` e também `generate` quando `FINAL_ANSWER_PROVIDER=openai`), o evento `llm_usage` armazena modelo e tokens de entrada, saída e total retornados pela API. A conclusão de `validate` inclui contagem e descrição das violações, sem armazenar o texto gerado. Os prompts e a chave da API não são gravados.

Para consultar a última execução:

```bash
uv run python - <<'PY'
import json
import sqlite3

with sqlite3.connect("clinical_demo.db") as connection:
    rows = connection.execute("""
        SELECT node, event, details, created_at
        FROM audit_events
        WHERE audit_id = (
            SELECT audit_id FROM audit_events ORDER BY created_at DESC LIMIT 1
        )
        ORDER BY created_at
    """).fetchall()

for node, event, details, created_at in rows:
    print(created_at, node, event, json.loads(details))
PY
```

Não há fallback automático entre providers. Com `FINAL_ANSWER_PROVIDER=qwen`, indisponibilidade do adapter ou modelo-base encerra o fluxo de modo seguro; com `FINAL_ANSWER_PROVIDER=openai`, indisponibilidade da API encerra-o do mesmo modo. `--fake` usa LLMs determinísticas apenas para desenvolvimento e testes; `python main.py --base-legacy` é o protótipo ReAct anterior e não substitui o adapter fine-tuned.

Só depois de ambos passarem execute o fluxo real:

```bash
uv run python -m app.cli \
  --authorized-patient P-042 \
  "Paciente P-042 com hipertensão gestacional tem exames pendentes?"
```

## 6. Requisitos para a geração local real

O loader carrega o mesmo modelo-base em 4 bits antes de aplicar o adapter LoRA, seguindo a estratégia QLoRA usada no treino. Antes do smoke test final, confirme que a máquina tem espaço em disco para o download do modelo-base, RAM suficiente e VRAM compatível com a carga do modelo e da geração. Como referência prática, uma GPU com 12–16 GB de VRAM ou mais oferece uma margem adequada; GPUs menores podem falhar por memória insuficiente.

Quando a máquina não atender esses requisitos, use `--fake` para demonstrar e validar localmente o workflow LangGraph, ou execute os smoke tests do adapter em uma máquina com GPU maior, como Colab ou Kaggle. Não substitua o adapter por um modelo-base ou modelo menor sem registrar e revalidar a mudança.

## 7. Avaliação manual do fluxo real

Para uma avaliação ponta a ponta sem GPU, use `FINAL_ANSWER_PROVIDER=openai` e execute os cinco cenários abaixo. Eles cobrem caso crítico autorizado, pergunta geral por protocolo, ausência de exame, acesso negado e paciente inexistente.

```bash
FINAL_ANSWER_PROVIDER=openai MAX_RESPONSE_REVISIONS=1 uv run python -m app.cli --authorized-patient P-042 "Paciente P-042 com hipertensão gestacional tem exames pendentes?"
FINAL_ANSWER_PROVIDER=openai MAX_RESPONSE_REVISIONS=1 uv run python -m app.cli "Quais sinais exigem atenção no puerpério?"
FINAL_ANSWER_PROVIDER=openai MAX_RESPONSE_REVISIONS=1 uv run python -m app.cli --authorized-patient P-101 "Paciente P-101 tem exames pendentes?"
FINAL_ANSWER_PROVIDER=openai MAX_RESPONSE_REVISIONS=1 uv run python -m app.cli "Paciente P-042 com hipertensão gestacional tem exames pendentes?"
FINAL_ANSWER_PROVIDER=openai MAX_RESPONSE_REVISIONS=1 uv run python -m app.cli --authorized-patient P-999 "Paciente P-999 tem exames pendentes?"
```

Em caso crítico, `garantir_escalonamento_critico` acrescenta deterministicamente a orientação de avaliação humana se a geração a omitir; o validador mantém essa regra como defesa adicional. A validação confirma a estrutura e o mapeamento das citações, não a fidelidade semântica de toda afirmação livre. Portanto, respostas clínicas detalhadas exigem fontes igualmente detalhadas.

## 8. Solução de problemas

| Sintoma | Ação |
| --- | --- |
| `uv: command not found` | Instale o uv e abra um novo terminal. |
| `OPENAI_API_KEY` ausente | Crie/preencha `.env`; o CLI o carrega automaticamente. |
| `QWEN_LORA_ADAPTER_PATH não configurado` | Preencha o caminho absoluto no `.env`. |
| Adapter não encontrado | Refaça o download e confira `adapter_config.json`. |
| Erro de memória/CUDA | Use `--fake` localmente ou mova o smoke test final para uma GPU maior. |
| `clinical_demo.db` apareceu | É banco SQLite derivado da demonstração e já está no `.gitignore`. |

## 9. API HTTP e frontend

A API FastAPI expõe o mesmo workflow do CLI sem duplicar regras de domínio.

```bash
# Terminal 1 — API com LLMs fake (sem OpenAI/Qwen)
API_USE_FAKES=true \
DEMO_AUTHORIZED_PATIENT_IDS=P-042 \
uv run uvicorn app.api.app:app --reload --port 8000

# Terminal 2 — frontend contra a API real
cd frontend
echo 'VITE_USE_MOCK=false' > .env.local
npm run dev
```

Endpoints:

- `GET /api/health` → `{ "status": "ok", "mode": "demo" }`
- `POST /api/chat` → JSON com `audit_id`, `outcome`, `answer`, `sources`, `alert`

Autorização e pacientes permitidos vêm só do servidor (`DEMO_REQUESTER_ID`,
`DEMO_AUTHORIZED_PATIENT_IDS`). O navegador envia apenas `question` e, opcionalmente,
`conversation_id` para correlação.

Com `FINAL_ANSWER_PROVIDER=openai` e `API_USE_FAKES=false`, a API usa o fluxo real
sem carregar Qwen. Em produção, faça `npm run build` em `frontend/` e suba o
uvicorn: o `frontend/dist` é servido depois das rotas `/api/*`.
