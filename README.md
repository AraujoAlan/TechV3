# Assistente Clínico — estado atual

Projeto acadêmico de assistente clínico materno-infantil. O repositório contém um protótipo LangChain/SQLite e notebooks de preparação, fine-tuning e avaliação.

## O que está implementado

- SQLite demonstrativo com prontuários, exames e protocolos.
- Quatro funções decoradas como tools: consulta de prontuário, exames, protocolos e alerta de terminal.
- Agente ReAct com `MemorySaver` em processo, usando Ollama por padrão.
- Pipeline de preparação de dados, treino QLoRA de Qwen3.5-4B e avaliação do adapter nos notebooks.

## Limites importantes

- O modelo fine-tuned **não está integrado ao runtime**. A opção `python main.py --finetuned` carrega, hoje, o modelo base `Qwen/Qwen2.5-1.5B-Instruct` apenas como demonstração; ela não carrega o adapter Qwen3.5-4B treinado.
- O pipeline de treino demonstra mensagens de resposta final e não demonstra suporte a chamadas de tools, JSON de tools ou decisões de roteamento. Portanto, não trate o modelo fine-tuned como router ou modelo de tool calling sem dados, capacidades e testes específicos que comprovem esse suporte.
- O ReAct atual decide as tools livremente. Ele não é um fluxo de domínio seguro: não há autorização antes de ler prontuário, validação determinística da resposta, fontes rastreáveis ou auditoria persistida.
- O alerta atual apenas imprime uma mensagem no terminal; não notifica uma equipe nem persiste um evento.
- `MemorySaver` mantém memória somente durante o processo atual.

O plano para corrigir esses limites está em [docs/design-doc-langgraph.md](docs/design-doc-langgraph.md). Ele é uma proposta, não uma implementação concluída.

## Execução do protótipo

```bash
pip install -r requirements.txt
python main.py
```

O modo padrão requer Ollama e `llama3.2`. O comando abaixo serve exclusivamente para inspecionar o pipeline textual de demonstração, não para demonstrar o modelo treinado:

```bash
python main.py --finetuned
```

## Verificação local

```bash
python testar_pipeline.py
```

O script verifica imports, SQLite e as três tools de leitura. Ele não inicia um LLM nem valida a integração do adapter.

## Arquitetura alvo

```text
pergunta + RequestContext
        |
router determinístico / StateGraph
        |
autorização -> consultas -> validação -> fontes/auditoria
        |
modelo fine-tuned (somente geração da resposta final)
```

O modelo não define autorização, IDs de pacientes ou tools a executar. Essas decisões devem ser determinísticas e testáveis.

## Dados e segurança

Os dados do SQLite são apenas demonstrativos e não representam integração hospitalar. Não use o protótipo com dados reais. Para uma implementação clínica, são necessários autorização, minimização de dados, logs persistentes e validação antes da entrega da resposta.

## Estrutura relevante

- [main.py](main.py): protótipo atual LangChain/SQLite.
- [notebooks/05_treino.ipynb](notebooks/05_treino.ipynb): treino do adapter LoRA.
- [notebooks/06_avaliacao.ipynb](notebooks/06_avaliacao.ipynb): avaliação do adapter.
- [docs/design-doc-langgraph.md](docs/design-doc-langgraph.md): arquitetura alvo, workflow e plano de implementação.
