# Contrato da API — Assistente Médico

Especificação do que o backend (FastAPI + LangGraph) precisa expor para o
frontend funcionar. A UI está escrita contra este contrato JSON síncrono.

Enquanto a API não estiver no ar, `VITE_USE_MOCK=true` mantém o frontend com
`src/api/mock.ts`, que devolve o mesmo `ChatResponse`. Para plugar o backend
real basta `VITE_USE_MOCK=false`.

**Fonte da verdade em código:** [`src/api/types.ts`](src/api/types.ts).

> O contrato SSE anterior (`token`, `tool_start`, `tool_end`) foi descontinuado
> na versão 1: exponha apenas a resposta já validada, sem rascunho nem trilha
> interna de nós.

---

## Base

O frontend chama caminhos relativos (`/api/...`):

- **Dev** — o Vite faz proxy de `/api` para `http://localhost:8000`
  (ver `vite.config.ts`).
- **Produção** — o FastAPI serve o `dist/` no mesmo host, depois de `/api/*`.

Nos dois casos a origem é a mesma, então não há CORS a resolver.

---

## `POST /api/chat`

### Request

`Content-Type: application/json`

```json
{
  "question": "Paciente P-042 com hipertensão gestacional tem exames pendentes?",
  "conversation_id": "conv-optional"
}
```

| Campo | Obrigatório | Regra |
| --- | --- | --- |
| `question` | Sim | Texto não vazio; o backend aplica limite de tamanho. |
| `conversation_id` | Não | Correlação/auditoria. Não é credencial nem ativa memória. |

O frontend **não** envia histórico completo, papel do usuário nem
`authorized_patient_ids`. Autorização vem só do servidor.

### Response — `200`

`Content-Type: application/json`

```json
{
  "audit_id": "uuid",
  "outcome": "completed",
  "answer": "Resposta já validada [S1].",
  "sources": [
    {
      "id": "record:P-042:v1",
      "title": "Prontuário sintético",
      "snippet": "Gestante sintética...",
      "kind": "prontuario"
    }
  ],
  "alert": {
    "status": "simulated_recorded"
  }
}
```

| Campo | Regra |
| --- | --- |
| `audit_id` | Sempre presente para correlação. |
| `outcome` | `completed` (resposta validada) ou `limited` (limitação segura). |
| `answer` | Somente `final_answer` validado — nunca rascunho. |
| `sources` | Lista pública de fontes; pode ser vazia. |
| `alert` | `null` ou `{ "status": "simulated_recorded" }`. |

Limitação clínica, paciente inexistente ou não autorizado → `200` com
`outcome: "limited"` (sem `403`/`404` que permitam enumeração).

### Erros HTTP

| Situação | Status |
| --- | ---: |
| JSON inválido / pergunta ausente ou longa | 422 |
| Não autenticado | 401 |
| Sem permissão de acesso à aplicação | 403 |
| Falha inesperada | 500 (mensagem genérica) |

---

## `GET /api/health`

```json
{ "status": "ok", "mode": "demo" }
```

Alimenta o indicador do cabeçalho (“API conectada”). Não carrega modelos.

---

## Checklist de aceite (frontend)

- [ ] `VITE_USE_MOCK=false` envia só `question` (+ `conversation_id` opcional).
- [ ] A UI renderiza `answer`, `sources` e o alerta simulado quando houver.
- [ ] Não há `toolCalls`, prompt, rascunho ou violações na UI.
- [ ] Loading, erro de rede, cancelamento e `outcome: limited` são claros.
- [ ] Cabeçalho mostra “API conectada” quando `/api/health` retorna `200`.
- [ ] `npm run lint` e `npm run build` passam.
