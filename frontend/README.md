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

## Rodando

```bash
nvm use          # Node 22
npm install
cp .env.example .env.local
npm run dev      # http://localhost:5173
```

Com a API no ar (`uv run uvicorn app.api.app:app --reload --port 8000`) e
`VITE_USE_MOCK=false`, o Vite faz proxy de `/api` para `localhost:8000`.

Scripts: `dev`, `build` (typecheck + bundle), `preview`, `lint`.

## Estrutura

A separação pedida é rígida: **nada em `ui/` importa `fetch`**.

```
src/
├── api/          # tudo que fala com o backend
│   ├── types.ts      # contrato (Message, ChatRequest, ChatResponse)
│   ├── config.ts     # base URL e chave do mock
│   ├── chat.ts       # sendChat() — POST JSON
│   ├── mock.ts       # backend falso, mesmo ChatResponse
│   ├── health.ts     # indicador de API no ar
│   ├── errors.ts     # ApiError + mensagens para o médico
│   └── index.ts      # barrel público do módulo
│
├── ui/           # componentes React, sem conhecimento de rede
│   ├── chat/         # ChatView, MessageList, MessageBubble, Composer,
│   │                 # SourceList, EmptyState
│   ├── layout/       # AppShell, Header
│   └── primitives/   # RichText (markdown mínimo), icons
│
├── app/          # composição: App + useChat (única ponte api ↔ ui)
├── lib/          # utilidades puras (id, cn, time)
└── styles.css    # tokens de cor e tema claro/escuro
```

## Contrato da API

A especificação completa está em [`CONTRATO.md`](CONTRATO.md). Em código, a
fonte da verdade é [`src/api/types.ts`](src/api/types.ts).

Resumo: `POST /api/chat` recebe `{ question, conversation_id? }` e responde
JSON com `answer`, `sources`, `outcome` e `alert`; `GET /api/health` alimenta
o indicador do cabeçalho.

`VITE_USE_MOCK=true` mantém a UI com o mock local. Para a API real:
`VITE_USE_MOCK=false`.

## Requisitos da Fase 3 refletidos na UI

- **Explainability** — `SourceList` mostra as fontes citadas em cada resposta.
- **Auditoria segura** — alerta simulado quando o backend registra
  `simulated_recorded`; sem expor trilha interna de nós ou rascunhos.
- **Limites de atuação** — aviso fixo no composer: apoio à decisão, não
  prescreve nem substitui a avaliação clínica.

## Servindo pelo FastAPI

As rotas `/api/*` são registradas primeiro; em seguida o `frontend/dist` é
montado. Em desenvolvimento o proxy do Vite (`vite.config.ts`) aponta `/api`
para `http://localhost:8000` — sem CORS.
