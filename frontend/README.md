# Frontend — Assistente Virtual · Ginecologia

Interface de chat para o assistente médico da Fase 3. É uma SPA em **React +
Vite + TypeScript**, sem servidor Node próprio: o `npm run build` gera
`dist/`, que o FastAPI serve em produção. O monolito continua sendo um
processo só.

## Stack

| Item | Escolha | Motivo |
| --- | --- | --- |
| Framework | React 19 + Vite | SPA pura. Sem SSR/SEO a resolver — o chat fica atrás de login. |
| Estilo | Tailwind CSS v4 | Tokens em CSS, tema claro/escuro sem lib de componentes. |
| Node | 22 (`.nvmrc`) | Vite 8 exige `>=20.19`. Rode `nvm use` antes de instalar. |
| Lint | oxlint | Já vem no scaffold; roda em milissegundos. |

Por que **não** Next.js: o valor dele (Server Components, Route Handlers, SSR)
duplicaria a camada que o backend Python já é. Sobraria um servidor Node só
para fazer proxy do FastAPI — um salto a mais, sem ganho.

## Rodando

```bash
nvm use          # Node 22
npm install
cp .env.example .env.local
npm run dev      # http://localhost:5173
```

Scripts: `dev`, `build` (typecheck + bundle), `preview`, `lint`.

## Estrutura

A separação pedida é rígida: **nada em `ui/` importa `fetch`**.

```
src/
├── api/          # tudo que fala com o backend
│   ├── types.ts      # contrato (Message, StreamEvent, ChatRequest…)
│   ├── config.ts     # base URL e chave do mock
│   ├── chat.ts       # streamChat() — POST + SSE
│   ├── sse.ts        # parser de Server-Sent Events sobre fetch
│   ├── mock.ts       # backend falso, mesmos eventos do real
│   ├── health.ts     # indicador de API no ar
│   ├── errors.ts     # ApiError + mensagens para o médico
│   └── index.ts      # barrel público do módulo
│
├── ui/           # componentes React, sem conhecimento de rede
│   ├── chat/         # ChatView, MessageList, MessageBubble, Composer,
│   │                 # ToolTrace, SourceList, EmptyState
│   ├── layout/       # AppShell, Header
│   └── primitives/   # RichText (markdown mínimo), icons
│
├── app/          # composição: App + useChat (única ponte api ↔ ui)
├── lib/          # utilidades puras (id, cn, time)
└── styles.css    # tokens de cor e tema claro/escuro
```

## Contrato da API

A especificação completa do que o backend precisa expor está em
[`CONTRATO.md`](CONTRATO.md): corpo da requisição, os seis eventos do stream
SSE, tratamento de erro e checklist de aceite. Em código, a fonte da verdade é
[`src/api/types.ts`](src/api/types.ts).

Resumo: `POST /api/chat` recebe o histórico em JSON e responde
`text/event-stream`; `GET /api/health` alimenta o indicador do cabeçalho.

Enquanto a API não existir, `VITE_USE_MOCK=true` mantém a UI funcionando com
`src/api/mock.ts` — mesmo formato de eventos, streaming incluído. Para plugar o
backend real basta `VITE_USE_MOCK=false`; nenhum componente muda.

## Requisitos da Fase 3 refletidos na UI

- **Explainability** — `SourceList` mostra as fontes citadas em cada resposta.
- **Rastreabilidade** — `ToolTrace` expõe cada tool executada pelo agent, com
  entrada, saída e status.
- **Limites de atuação** — aviso fixo no composer: apoio à decisão, não
  prescreve nem substitui a avaliação clínica.

## Servindo pelo FastAPI

```python
from fastapi.staticfiles import StaticFiles

# depois de registrar as rotas /api/*
app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend")
```

Com isso o `/api` do proxy de desenvolvimento (`vite.config.ts`) e o caminho de
produção viram o mesmo — não há CORS para resolver em lugar nenhum.
