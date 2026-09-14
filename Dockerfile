# Imagem da API. O modelo não mora aqui — quem serve os pesos é o llama-server,
# no outro serviço do compose. Aqui ficam o agente, as ferramentas, o banco do
# hospital e o frontend já compilado.

# --- estágio 1: compilar o frontend ------------------------------------------
FROM node:22-alpine AS frontend

WORKDIR /frontend

# VITE_USE_MOCK precisa ser `false` AQUI, não em runtime: o Vite substitui
# `import.meta.env.*` no momento do build, e não existe leitura de configuração
# depois. Uma imagem construída sem isso serve a interface falando com o mock.
ENV VITE_USE_MOCK=false

COPY frontend/package.json frontend/package-lock.json ./
# `npm ci` e não `npm install`: respeita o lock, e falha se ele estiver fora de
# sincronia em vez de resolver sozinho.
RUN npm ci

COPY frontend/ ./
# O build roda `tsc -b` antes do vite, então erro de tipo quebra a imagem — o
# que é proposital: melhor falhar no build que servir interface quebrada.
RUN npm run build

# --- estágio 2: a API ---------------------------------------------------------
FROM python:3.12-slim AS api

# uv é o gerenciador que o projeto já usa; vem da imagem oficial dele.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/usr/local

# Dependências antes do código: o Docker reaproveita esta camada enquanto o
# pyproject/uv.lock não mudarem, e a instalação é a parte cara.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY app/ ./app/
COPY dados_hospital/ ./dados_hospital/
COPY --from=frontend /frontend/dist ./frontend/dist

# O banco é montado a partir dos parquets no start (app/main.py), não aqui:
# assim trocar os parquets não exige reconstruir a imagem.
ENV CAMINHO_DUCKDB=/app/data/hospital.duckdb \
    DIRETORIO_PUBLICADO=/app/dados_hospital \
    DIRETORIO_FRONTEND=/app/frontend/dist \
    CAMINHO_LOG=/app/logs/auditoria.jsonl

RUN mkdir -p /app/data /app/logs

EXPOSE 8000

# Sem --reload: isso é produção do trabalho, não desenvolvimento.
CMD ["uvicorn", "app.main:aplicacao", "--host", "0.0.0.0", "--port", "8000"]
