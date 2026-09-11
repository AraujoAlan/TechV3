# 🚀 Como Executar o Pipeline LangChain

**Branch:** `langchain-integration`

---

## ✅ Passo a Passo Rápido

### 1️⃣ **Verificar que está na branch correta**

```bash
git checkout langchain-integration
git pull  # Se necessário
```

### 2️⃣ **Instalar dependências**

```bash
pip install -r requirements.txt
```

### 3️⃣ **Testar instalação (RECOMENDADO)**

```bash
python testar_pipeline.py
```

**Saída esperada:**
```
✅ TODOS OS TESTES PASSARAM!
✅ Imports funcionando
✅ Banco de dados SQLite operacional
✅ 5 tabelas criadas e populadas
✅ 4 Tools do LangChain funcionando
```

---

## 🎬 Opções de Execução

### **OPÇÃO 1: Modelo Fine-tuned (Recomendado para o vídeo)**

```bash
python main.py --finetuned
```

**O que acontece:**
- ✅ Baixa automaticamente o modelo do HuggingFace
- ✅ Modelo: `emidiosouza/assistente-maternidade` (Qwen3.5-4B + LoRA)
- ✅ Especializado em atendimento materno-infantil
- ⚠️ Requer ~8GB RAM/VRAM
- ⏱️ Primeira execução demora ~5min (download)

### **OPÇÃO 2: Ollama Local (Alternativa)**

```bash
# Primeiro instalar Ollama
# Download: https://ollama.ai

# Instalar modelo
ollama pull llama3.2

# Executar
python main.py
```

---

## 💬 Perguntas para Demonstração

### **Sequência Recomendada (5 minutos):**

#### 1. **Consulta básica** (mostra tool buscar_prontuario)
```
Preciso de informações sobre o paciente 12345
```
**O que mostrar:**
- Agent decide usar a tool automaticamente
- Tool consulta SQLite
- Retorna: nome, idade, diagnósticos, medicamentos, alergias

---

#### 2. **Contextualização** (mostra integração BD + LLM + protocolo)
```
O paciente 12345 tem diabetes. Qual o protocolo?
```
**O que mostrar:**
- Agent busca prontuário primeiro
- Agent consulta protocolo de diabetes
- LLM contextualiza resposta com dados do paciente
- Resposta menciona medicamentos e alergias específicas

---

#### 3. **Memória persistente** (mostra MemorySaver)
```
Quais exames estão pendentes para ele?
```
**O que mostrar:**
- Não precisa repetir "12345"
- Agent lembra do contexto da conversa anterior
- Busca exames do paciente correto

---

#### 4. **Outro paciente** (mostra versatilidade)
```
Paciente 67890 com artrite. O que você recomenda?
```
**O que mostrar:**
- Agent busca novo prontuário
- Contextualiza com dados diferentes
- Modelo fine-tuned usa linguagem técnica médica

---

#### 5. **Sair**
```
sair
```

---

## 🔍 Verificar Banco de Dados (Para o Vídeo)

Mostrar que os dados são reais no SQLite:

```bash
# Abrir SQLite
sqlite3 hospital.db

# Comandos úteis:
.tables                              # Ver tabelas
.schema pacientes                    # Ver estrutura
SELECT * FROM pacientes;             # Ver pacientes
SELECT * FROM diagnosticos WHERE paciente_id = '12345';
SELECT * FROM exames WHERE status = 'pendente';
.quit
```

---

## 📊 Estrutura para Mostrar no Vídeo

### **1. DIAGRAMA_FLUXO.md + README.md** (1 min)
- **DIAGRAMA_FLUXO.md:** 📊 ABRIR ESTE ARQUIVO PRIMEIRO!
  - Diagramas Mermaid interativos (renderizam no GitHub/VS Code)
  - Fluxo sequencial completo
  - Padrão ReAct explicado
  - Exemplo completo de execução
- README.md: Arquitetura (linha 145-181)
- README.md: Schema do BD (linha 209-240)

### **2. main.py** (1 min)
Mostrar rapidamente:

**Banco de dados SQLite:**
```python
# Linha 108-327
class DatabaseProntuarios:
    # 5 tabelas relacionais
    # Métodos para consulta estruturada
```

**Tools do LangChain:**
```python
# Linha 335-448
@tool
def buscar_prontuario(paciente_id: str) -> str:
    # Consulta banco de dados
    prontuario = db.buscar_prontuario_completo(paciente_id)
```

**Pipeline completo:**
```python
# Linha 453-532
def criar_assistente_medico(usar_modelo_finetuned: bool = False):
    # LLM (local ou fine-tuned)
    # Tools (4 ferramentas)
    # Memory (MemorySaver)
    # Agent (ReAct)
```

### **3. Execução** (3 min)
- Executar as 4 perguntas de exemplo
- Mostrar respostas contextualizadas

### **4. SQLite** (30s)
- Mostrar dados reais no banco

---

## ⚠️ Troubleshooting

### **Erro: "Ollama not found"**
```bash
# Instalar Ollama: https://ollama.ai
ollama pull llama3.2
```

### **Erro: "Out of memory" com fine-tuned**
```bash
# Usar Ollama em vez disso
python main.py
```

### **Erro: "ModuleNotFoundError"**
```bash
pip install -r requirements.txt --upgrade
```

### **Erro: "UnicodeEncodeError" (Windows)**
✅ Já corrigido! O código detecta Windows e configura UTF-8 automaticamente.

### **Warning: "create_react_agent deprecated"**
✅ É esperado! O código usa o import correto com fallback.

---

## 📝 Checklist Final Antes de Gravar

- [ ] `git checkout langchain-integration`
- [ ] `pip install -r requirements.txt`
- [ ] `python testar_pipeline.py` → Tudo verde?
- [ ] Ollama instalado OU preparado para usar fine-tuned
- [ ] Terminal limpo e fonte legível
- [ ] README.md aberto em outra aba
- [ ] main.py aberto para mostrar código
- [ ] Perguntas de exemplo anotadas

---

## 🎯 Resumo do que foi implementado

✅ **Pipeline LangChain Completo**
- Agent ReAct com decisão autônoma
- 4 Tools que consultam banco de dados
- MemorySaver para contexto persistente

✅ **Base de Dados Estruturada (SQLite)**
- 5 tabelas relacionais
- Schema completo e normalizado
- Dados de exemplo pré-populados

✅ **Integração Modelo Fine-tuned**
- HuggingFace: emidiosouza/assistente-maternidade
- Qwen3.5-4B + LoRA
- Especializado em maternidade

✅ **Contextualização de Respostas**
- Busca automática de dados no BD
- Respostas baseadas em informações reais do paciente
- Considera diagnósticos, medicamentos e alergias

---

**Tempo estimado do vídeo: 5-7 minutos**

Boa gravação! 🎬
