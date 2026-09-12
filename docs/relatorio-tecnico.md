# Relatório técnico — MVP LangGraph

## Arquitetura

O CLI cria um `RequestContext` demo e executa o `StateGraph`. Serviços injetáveis implementam autorização, SQLite sintético, criticidade, alertas simulados, auditoria e validação. O grafo não conhece SQL, credenciais nem paths de modelos.

`gpt-4.1-mini` é usado exclusivamente para interpretação estruturada, análise e crítica auxiliar. Qwen3.5-4B com adapter LoRA é usado somente para redigir a resposta final. A validação determinística é a autoridade final.

## Evidências e limites

Os testes unitários usam LLMs falsas; as integrações reais possuem smoke tests isolados. SQLite registra fontes estáveis, alertas idempotentes e eventos de auditoria minimizados. Alertas são sempre descritos como simulados registrados.

Não há API, autenticação corporativa, dados reais, notificação externa ou checkpointer durável. A validação confirma regras e citações estruturadas, mas não garante a correção semântica completa de toda paráfrase em texto livre.
