# Contrato da API — Assistente Médico

Especificação do que o backend (FastAPI + LangChain/LangGraph) precisa expor
para o frontend funcionar. A UI já está escrita contra este contrato.

Enquanto a API não existir, `VITE_USE_MOCK=true` mantém o frontend rodando com
`src/api/mock.ts`, que emite exatamente estes mesmos eventos. Para plugar o
backend real basta `VITE_USE_MOCK=false` — nenhum componente muda.

**Fonte da verdade em código:** [`src/api/types.ts`](src/api/types.ts).
Se alterarem o contrato, alterem os dois.

---

## Base

O frontend chama caminhos relativos (`/api/...`):

- **Dev** — o Vite faz proxy de `/api` para `http://localhost:8000`
  (ver `vite.config.ts`).
- **Produção** — o FastAPI serve o `dist/` no mesmo host.

Nos dois casos a origem é a mesma, então não há CORS a resolver.

---

## `POST /api/chat`

### Request

`Content-Type: application/json`

```jsonc
{
  "messages": [
    { "role": "user",      "content": "Mostre o prontuário da paciente 12345" },
    { "role": "assistant", "content": "Paciente 12345 — 34 anos..." },
    { "role": "user",      "content": "Quais exames estão pendentes?" }
  ],
  "conversationId": "conv_a1b2c3d4"
}
```

| Campo | Tipo | Obrigatório | Descrição |
| --- | --- | --- | --- |
| `messages` | `Array<{role, content}>` | sim | Histórico completo, em ordem cronológica. `role` é `"user"` ou `"assistant"`. |
| `conversationId` | `string` | não | Estável durante a conversa. Serve para o backend manter memória/checkpoint do LangGraph. |

> **Decisão em aberto para o backend:** o frontend manda o histórico completo
> **e** o `conversationId`. Usem o que preferirem — histórico stateless, ou só
> o id com checkpointer do LangGraph. O frontend não muda.

### Response

`200` com `Content-Type: text/event-stream`.

Headers necessários:

```http
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no
```

`X-Accel-Buffering: no` só importa se houver nginx na frente — sem ele o proxy
bufferiza e o streaming morre.

Cada evento é uma linha `data:` com um JSON, seguida de **linha em branco**:

```
data: {"type":"token","content":"A "}

```

---

## Eventos do stream

São seis tipos. Todos carregam o campo `type`.

```jsonc
// Fragmento de texto da resposta. O frontend concatena na ordem de chegada.
// Mande os espaços junto — "A " e não "A".
{ "type": "token", "content": "A " }

// O agent decidiu chamar uma tool.
{ "type": "tool_start", "id": "t1", "name": "buscar_prontuario",
  "input": { "paciente_id": "12345" } }

// A tool retornou. O `id` precisa bater com o do tool_start correspondente.
{ "type": "tool_end", "id": "t1", "output": "Prontuário encontrado: 34 anos, G2P1A0." }

// Fontes usadas na resposta. Uma vez por turno, perto do fim.
{ "type": "sources", "sources": [
    { "id": "s1",
      "title": "Protocolo Interno — Ginecologia v2.1",
      "snippet": "Seção 3: estratificação de risco e conduta inicial.",
      "kind": "protocolo" }
  ] }

// Fim do turno. Sempre mande, mesmo sem os campos opcionais.
{ "type": "done", "messageId": "msg_9f", "conversationId": "conv_a1b2c3d4" }

// Falha tratada (o modelo caiu, a tool explodiu, timeout...).
{ "type": "error", "message": "O modelo não respondeu a tempo. Tente novamente." }
```

### Campos por evento

| Evento | Campo | Tipo | Obrigatório |
| --- | --- | --- | --- |
| `token` | `content` | `string` | sim |
| `tool_start` | `id` | `string` | sim |
| | `name` | `string` | sim |
| | `input` | `object` | não |
| `tool_end` | `id` | `string` | sim — correlaciona com o `tool_start` |
| | `output` | `string` | sim |
| `sources` | `sources` | `Source[]` | sim |
| `done` | `messageId` | `string` | não |
| | `conversationId` | `string` | não — se vier, o frontend passa a usar esse |
| `error` | `message` | `string` | sim — texto para o médico ler, não stack trace |

### `Source`

| Campo | Tipo | Obrigatório | Descrição |
| --- | --- | --- | --- |
| `id` | `string` | sim | Chave de lista. |
| `title` | `string` | sim | Ex.: `"Protocolo de Hipertensão — Cap. 3"`. |
| `snippet` | `string` | não | Trecho literal usado na resposta. |
| `kind` | `string` | não | `"protocolo"` \| `"prontuario"` \| `"exame"` \| `"documento"`. Define o rótulo na UI. |

---

## Ordem típica num turno

```
data: {"type":"tool_start","id":"t1","name":"buscar_prontuario","input":{"paciente_id":"12345"}}

data: {"type":"tool_end","id":"t1","output":"34 anos, G2P1A0, sem alergias."}

data: {"type":"tool_start","id":"t2","name":"verificar_exames_pendentes","input":{"paciente_id":"12345"}}

data: {"type":"tool_end","id":"t2","output":"2 exames pendentes."}

data: {"type":"token","content":"**Paciente "}

data: {"type":"token","content":"12345** "}

data: {"type":"token","content":"— 34 anos..."}

data: {"type":"sources","sources":[{"id":"s1","title":"Prontuário Eletrônico 12345","kind":"prontuario"}]}

data: {"type":"done","messageId":"msg_9f","conversationId":"conv_a1b2c3d4"}
```

A ordem não é rígida: o agent pode falar, chamar uma tool e voltar a falar, e o
frontend lida com isso. As duas regras que valem são **`done` por último** e
**todo `tool_start` com seu `tool_end`**.

---

## `GET /api/health`

Qualquer `200` serve. Alimenta apenas o indicador no cabeçalho
(`Dados simulados` / `API conectada` / `API indisponível`). Erro ou timeout
mostra "indisponível" e o frontend segue funcionando.

---

## Erros

Dois níveis, tratados de formas diferentes:

- **Antes do stream começar** — responda HTTP `4xx`/`5xx` com JSON. O frontend
  lê o campo `detail` ou `message` e mostra ao médico.
  `HTTPException(status_code=422, detail="...")` do FastAPI já sai no formato
  certo.
- **No meio do stream** — o HTTP já é `200`, então emita
  `{"type":"error","message":"..."}` e encerre. O texto parcial que já chegou
  permanece na tela.

---

## Detalhes que importam na implementação

- **Formatação.** O frontend renderiza um Markdown mínimo: `**negrito**`,
  listas com `-`/`•`, listas numeradas `1.`, e parágrafos separados por linha
  em branco dupla (`\n\n`). Qualquer outra sintaxe aparece como texto literal.
  Nada vira HTML — sem `dangerouslySetInnerHTML` —, então não há risco de
  injeção pelo texto do modelo.
- **Flush.** Dê flush a cada evento. Se o buffer segurar, o streaming vira um
  bloco único no fim e perde o efeito na demonstração.
- **Cancelamento.** Ao clicar em parar, o frontend aborta o `fetch` e a conexão
  cai. Tratem `asyncio.CancelledError` / desconexão do cliente para não deixar
  o agent rodando à toa.
- **Tolerância do cliente.** O parser ignora eventos com JSON malformado em vez
  de derrubar a conversa, remonta eventos partidos entre chunks TCP, e aceita
  `data: [DONE]` como sentinela opcional de fim.
- **Mapeamento LangGraph.** O desenho dos eventos veio do `astream_events`:
  `on_tool_start` → `tool_start`, `on_tool_end` → `tool_end`,
  `on_chat_model_stream` → `token`. Confiram a assinatura e o parâmetro
  `version` contra a versão de `langgraph` fixada no `pyproject.toml`
  (0.2.60+) — isso mudou entre versões.
- **`sources` é trabalho do backend.** Não sai do `astream_events` de graça:
  precisa ser montado a partir do output das tools (qual protocolo ou
  prontuário foi consultado). É o requisito de *explainability* da Fase 3, então
  vale o esforço.

---

## Checklist de aceite

- [ ] `POST /api/chat` responde `text/event-stream` com os headers acima
- [ ] Tokens chegam progressivamente, não todos de uma vez no fim
- [ ] Todo `tool_start` tem `tool_end` com o mesmo `id`
- [ ] Um evento `sources` por turno, quando houver fonte
- [ ] `done` sempre por último
- [ ] `GET /api/health` retorna `200`
- [ ] Desconexão do cliente cancela a execução do agent
