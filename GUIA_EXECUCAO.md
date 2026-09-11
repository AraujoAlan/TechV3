# 🎬 Guia Rápido de Execução - Pipeline LangChain

**Branch:** `langchain-integration`

Este guia é para **gravar o vídeo de demonstração** do pipeline LangChain integrado.

---

## 📋 Pré-requisitos

### Opção 1: Usar Ollama (Recomendado para o vídeo - mais rápido)

```bash
# 1. Instalar Ollama
# Baixe de: https://ollama.ai

# 2. Instalar modelo
ollama pull llama3.2

# 3. Verificar instalação
ollama list
```

### Opção 2: Usar Modelo Fine-tuned (Demonstrar integração completa)

```bash
# Não precisa instalar nada extra
# O modelo será baixado automaticamente do HuggingFace
# Requer ~8GB de RAM/VRAM
```

---

## 🚀 Instalação

```bash
# 1. Mudar para a branch
git checkout langchain-integration

# 2. Instalar dependências
pip install -r requirements.txt
```

---

## 🎥 Roteiro para o Vídeo (5-7 minutos)

### **PARTE 1: Introdução (30s)**

```
"Nesta demonstração vou mostrar o pipeline LangChain integrado com:
- Base de dados SQLite estruturada
- Modelo fine-tuned customizado
- Sistema de contextualização de respostas"
```

### **PARTE 2: Mostrar Arquitetura (1min)**

Abra o `README.md` e mostre:
- Diagrama do pipeline completo (linha 145-179)
- Schema do banco de dados (linha 209-240)
- Componentes principais (linha 183-188)

```
"O sistema tem 5 componentes principais:
1. LangChain Agent que decide quais ferramentas usar
2. 4 Tools que consultam o banco de dados SQLite
3. Base de dados com 5 tabelas relacionais
4. Modelo fine-tuned Qwen3.5-4B especializado
5. Sistema de memória para contexto persistente"
```

### **PARTE 3: Mostrar o Código (1min)**

Abra `main.py` e mostre rapidamente:

1. **Classe DatabaseProntuarios** (linha 108-327)
```
"Aqui está o banco de dados estruturado com SQLite.
Temos 5 tabelas: pacientes, diagnósticos, medicamentos, exames e protocolos.
Tudo é criado automaticamente na primeira execução."
```

2. **Tools do LangChain** (linha 335-448)
```
"Estas são as 4 ferramentas que o Agent pode usar:
- buscar_prontuario: consulta dados do paciente
- verificar_exames_pendentes: lista exames pendentes
- consultar_protocolo: busca protocolos médicos
- registrar_alerta_equipe: registra alertas"
```

3. **Função criar_assistente_medico** (linha 453-529)
```
"Aqui montamos o pipeline completo:
- Escolhemos o modelo (local ou fine-tuned)
- Registramos as tools
- Configuramos o system prompt
- Adicionamos memória persistente com MemorySaver"
```

### **PARTE 4: Execução com Ollama (2min)**

```bash
# Terminal 1: Iniciar assistente
python main.py
```

**Demonstrar 3 exemplos:**

```
Exemplo 1 - Consulta simples:
🩺 Médico: Preciso de informações sobre o paciente 12345

[Mostrar que o Agent usa a tool buscar_prontuario automaticamente]
[Mostrar resposta com dados do banco: nome, idade, diagnósticos, medicamentos, alergias]
```

```
Exemplo 2 - Contextualização com protocolo:
🩺 Médico: O paciente 12345 tem hipertensão. Qual o protocolo?

[Mostrar que o Agent:
 1. Busca o prontuário primeiro
 2. Consulta o protocolo de hipertensão
 3. Responde contextualizando com dados do paciente]
```

```
Exemplo 3 - Memória persistente:
🩺 Médico: Quais exames estão pendentes para ele?

[Mostrar que o Agent lembra do paciente 12345 da conversa anterior]
[Não precisa repetir o ID do paciente]
```

### **PARTE 5: Execução com Modelo Fine-tuned (2min)**

```bash
# Terminal 2: Iniciar com modelo fine-tuned
python main.py --finetuned

# Aguardar download do modelo (mostrar no vídeo)
```

**Demonstrar 1 exemplo:**

```
🩺 Médico: Paciente 67890 com artrite. O que você recomenda?

[Mostrar que:
 1. Modelo fine-tuned é carregado
 2. Agent busca prontuário automaticamente
 3. Resposta é especializada (treinado no MedPT)
 4. Usa linguagem técnica médica]
```

### **PARTE 6: Mostrar Banco de Dados (1min)**

```bash
# Abrir banco SQLite para verificar
sqlite3 hospital.db

# Mostrar tabelas
.tables

# Mostrar exemplo de dados
SELECT * FROM pacientes;
SELECT * FROM diagnosticos WHERE paciente_id = '12345';
SELECT * FROM exames WHERE status = 'pendente';

.quit
```

```
"Aqui vocês podem ver que todos os dados são armazenados de forma estruturada.
O Agent consulta essas tabelas em tempo real para contextualizar as respostas."
```

### **PARTE 7: Conclusão (30s)**

```
"Resumindo, implementamos:
✓ Pipeline LangChain completo com Agent ReAct
✓ Base de dados SQLite estruturada com 5 tabelas
✓ 4 Tools para consulta automática de dados
✓ Integração com modelo fine-tuned HuggingFace
✓ Sistema de contextualização que busca dados reais do banco
✓ Memória persistente para manter contexto da conversa

Todos os requisitos do Tech Challenge foram atendidos!"
```

---

## 📝 Comandos Rápidos

```bash
# Executar com Ollama (rápido)
python main.py

# Executar com fine-tuned (demonstrar integração)
python main.py --finetuned

# Modo demonstração (sem interação)
python main.py --demo

# Ver estrutura do banco
sqlite3 hospital.db ".schema"

# Ver dados
sqlite3 hospital.db "SELECT * FROM pacientes;"
```

---

## 🎯 Perguntas de Exemplo para Demonstração

### Básicas (mostram tools funcionando):
- `Preciso de informações sobre o paciente 12345`
- `Quais exames estão pendentes para o paciente 67890?`
- `Qual o protocolo para tratamento de diabetes?`

### Contextualizadas (mostram integração BD + LLM):
- `O paciente 12345 tem diabetes. Qual o protocolo?`
- `Paciente 67890 com artrite. O que você recomenda?`
- `O paciente 12345 é alérgico a penicilina. Isso é importante?`

### Memória persistente (mostram MemorySaver):
- Primeiro: `Mostre o prontuário do paciente 12345`
- Depois: `Quais exames estão pendentes para ele?` (sem repetir ID)
- Depois: `Qual protocolo você recomenda para ele?` (lembra contexto)

---

## ⚠️ Troubleshooting

### Erro: "Ollama not found"
```bash
# Instalar Ollama de https://ollama.ai
ollama pull llama3.2
```

### Erro: "Out of memory" com fine-tuned
```bash
# Usar Ollama em vez disso
python main.py
```

### Erro: Module not found
```bash
# Reinstalar dependências
pip install -r requirements.txt --upgrade
```

---

## 📊 Estrutura dos Arquivos (para referência no vídeo)

```
TechV3/
├── main.py                 ← Código principal (650 linhas)
├── requirements.txt        ← Dependências
├── hospital.db             ← Banco SQLite (criado automaticamente)
├── README.md               ← Documentação completa
└── GUIA_EXECUCAO.md        ← Este arquivo
```

---

## ✅ Checklist para Gravação

- [ ] Git checkout langchain-integration
- [ ] pip install -r requirements.txt
- [ ] Ollama instalado e testado (ou preparar para usar fine-tuned)
- [ ] Terminal limpo e fonte legível
- [ ] README.md aberto em outra aba
- [ ] main.py aberto para mostrar código
- [ ] Gravar tela + webcam
- [ ] Testar perguntas antes de gravar

**Tempo total estimado: 5-7 minutos**

Boa gravação! 🎬
