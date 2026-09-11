# 🏥 Assistente Médico Virtual - Tech Challenge Etapa 3

Sistema de assistente médico virtual desenvolvido com **LangChain**, capaz de auxiliar em condutas clínicas, responder dúvidas de médicos e sugerir procedimentos baseados nos protocolos internos do hospital.

## 📋 Requisitos Atendidos

✅ **Pipeline com LangChain** que integra LLM customizada (fine-tuned Qwen3.5-4B)
✅ **Consultas em base de dados estruturadas** (SQLite com prontuários e registros)
✅ **Contextualização de respostas** com informações atualizadas do paciente
✅ **Integração completa** com modelo fine-tuned da Etapa 1 (emidiosouza/assistente-maternidade)
✅ **Memory persistente** para manter contexto entre perguntas
✅ **Sistema de Tools** para consulta automática de dados

---

## 🎯 Funcionalidades

### 1. **Ferramentas (Tools) Disponíveis**

O assistente possui 4 ferramentas principais:

- **🔍 Buscar Prontuário**: Acessa informações completas de pacientes
- **📊 Verificar Exames Pendentes**: Lista exames solicitados e não realizados
- **📖 Consultar Protocolos**: Busca protocolos médicos do hospital
- **🚨 Registrar Alertas**: Notifica a equipe médica sobre situações críticas

### 2. **Pipeline Inteligente com LangChain**

- **Agent System**: Utiliza agentes do LangChain para decisões autônomas
- **Tool Calling**: O assistente escolhe automaticamente quais ferramentas usar
- **Contextualização**: Combina dados de múltiplas fontes antes de responder
- **Memória de Conversação**: Mantém contexto ao longo do diálogo

### 3. **Integração com Modelo Fine-Tuned**

O sistema está **pronto para integração** com o modelo da Etapa 1:

- Função `criar_llm_finetuned()` com 3 opções de integração
- Documentação completa em `INSTRUCOES_INTEGRACAO.md`
- Suporte para Ollama, HuggingFace ou API customizada

---

## 🚀 Como Usar

### 1. **Instalação**

```bash
# Instale as dependências
pip install -r requirements.txt

# Configure as variáveis de ambiente (opcional)
cp .env.example .env
# Edite o .env se precisar usar OpenAI
```

### 2. **Execução**

```bash
# Modo 1: Usar Ollama local (rápido, gratuito)
python main.py

# Modo 2: Usar modelo fine-tuned HuggingFace
python main.py --finetuned

# Modo 3: Demonstração automática
python main.py --demo
```

**Nota sobre modelos:**
- **Ollama**: Requer instalação local ([ollama.ai](https://ollama.ai)) e `ollama pull llama3.2`
- **Fine-tuned**: Baixa automaticamente de `emidiosouza/assistente-maternidade` (requer ~8GB RAM/VRAM)

### 3. **Exemplos de Perguntas**

```
🩺 Médico: Preciso de informações sobre o paciente 12345
🩺 Médico: Quais exames estão pendentes para o paciente 12345?
🩺 Médico: Qual o protocolo para tratamento de hipertensão?
🩺 Médico: O paciente 67890 está com dor nas articulações, o que fazer?
```

---

## 🔧 Integração com Modelo Fine-Tuned

### **Status: ✅ INTEGRADO**

O modelo fine-tuned já está integrado e pode ser usado executando:

```bash
python main.py --finetuned
```

**Modelo usado:** `emidiosouza/assistente-maternidade`
- Baseado em Qwen3.5-4B
- Fine-tuned com QLoRA no dataset MedPT
- Especializado em atendimento materno-infantil
- Adapter LoRA disponível no HuggingFace

### **Arquitetura da Integração**

```
Pergunta do Médico
    ↓
[1] LangChain Agent (decide quais tools usar)
    ↓
[2] Tools consultam SQLite
    • buscar_prontuario()
    • verificar_exames_pendentes()
    • consultar_protocolo()
    ↓
[3] Contexto é montado com dados do BD
    ↓
[4] LLM Fine-tuned processa pergunta + contexto
    ↓
[5] Resposta contextualizada com dados do paciente
```

---

## 📁 Estrutura do Projeto

```
TechV3/
├── main.py                      # Código principal do assistente (COMPLETO)
├── requirements.txt             # Dependências do projeto
├── hospital.db                  # Base de dados SQLite (criado automaticamente)
├── .env.example                 # Exemplo de variáveis de ambiente
├── INSTRUCOES_INTEGRACAO.md     # Guia de integração (referência)
├── README.md                    # Este arquivo
├── notebooks/                   # Notebooks da Etapa 1 (fine-tuning)
│   ├── 05_treino.ipynb          # Fine-tuning do modelo
│   └── 06_avaliacao.ipynb       # Avaliação do modelo
└── modelos/                     # Modelos treinados (local)
    └── lora_model/              # Adapter LoRA (se treinado localmente)
```

---

## 🏗️ Arquitetura Técnica

**📊 [Ver Diagrama Completo e Interativo](DIAGRAMA_FLUXO.md)** ← Diagramas Mermaid + Fluxo detalhado

### **1. Pipeline LangChain Completo**

```
Pergunta do Médico
    ↓
┌─────────────────────────────────┐
│ LangChain Agent (ReAct)         │
│ + MemorySaver (contexto)        │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ Tools (consulta BD estruturado) │
│ • buscar_prontuario()           │
│ • verificar_exames_pendentes()  │
│ • consultar_protocolo()         │
│ • registrar_alerta_equipe()     │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ SQLite Database                 │
│ • Tabela: pacientes             │
│ • Tabela: diagnosticos          │
│ • Tabela: medicamentos          │
│ • Tabela: exames                │
│ • Tabela: protocolos            │
└─────────────────────────────────┘
    ↓
[Contexto montado com dados atualizados]
    ↓
┌─────────────────────────────────┐
│ LLM Fine-tuned                  │
│ (Qwen3.5-4B + LoRA)             │
│ Treinado no MedPT               │
└─────────────────────────────────┘
    ↓
Resposta Contextualizada
```

### **2. Componentes Principais**

- **LLM Fine-tuned**: Qwen3.5-4B especializado em atendimento materno-infantil
- **LangChain Agent (ReAct)**: Sistema de decisão automática com raciocínio
- **SQLite Database**: Base estruturada com prontuários, exames e protocolos
- **Tools**: 4 ferramentas para consulta e registro de dados
- **MemorySaver**: Mantém contexto persistente entre perguntas
- **Prompt System**: Diretrizes clínicas e limitações do assistente

### **3. Fluxo de Contextualização**

1. **Entrada**: Médico pergunta sobre paciente X
2. **Agent**: Identifica necessidade de buscar prontuário
3. **Tool**: `buscar_prontuario(X)` consulta SQLite
4. **Contexto**: Retorna diagnósticos, medicamentos, alergias
5. **LLM**: Recebe pergunta + contexto estruturado
6. **Processamento**: Fine-tuned raciocina sobre dados reais
7. **Saída**: Resposta contextualizada com dados do paciente

---

## 📊 Base de Dados Estruturada

O sistema usa **SQLite** com schema completo:

### **Tabelas criadas automaticamente:**

```sql
-- Pacientes
CREATE TABLE pacientes (
    id TEXT PRIMARY KEY,
    nome TEXT, idade INTEGER, sexo TEXT,
    alergias TEXT, ultimo_atendimento TEXT
);

-- Diagnósticos (relação 1:N com pacientes)
CREATE TABLE diagnosticos (
    id INTEGER PRIMARY KEY, paciente_id TEXT,
    diagnostico TEXT, data_diagnostico TEXT
);

-- Medicamentos (relação 1:N com pacientes)
CREATE TABLE medicamentos (
    id INTEGER PRIMARY KEY, paciente_id TEXT,
    medicamento TEXT, dosagem TEXT, data_inicio TEXT
);

-- Exames (relação 1:N com pacientes)
CREATE TABLE exames (
    id INTEGER PRIMARY KEY, paciente_id TEXT,
    tipo_exame TEXT, status TEXT,
    data_solicitacao TEXT, data_realizacao TEXT
);

-- Protocolos médicos
CREATE TABLE protocolos (
    id INTEGER PRIMARY KEY,
    condicao TEXT UNIQUE, descricao TEXT, condutas TEXT
);
```

### **Dados de exemplo inclusos:**
- 2 pacientes com histórico completo
- 3 diagnósticos associados
- 3 medicamentos em uso
- 3 exames pendentes
- 2 protocolos (hipertensão e diabetes)

**Para produção**, migrar para PostgreSQL:

```python
# Substituir na linha 114 do main.py:
import psycopg2
self.conn = psycopg2.connect(
    host="seu_host", database="hospital_db",
    user="usuario", password="senha"
)
```

---

## 🔐 Segurança e Boas Práticas

✅ **Temperatura baixa** (0.3) para respostas médicas precisas
✅ **Validação de dados** antes de processar
✅ **Limitação de iterações** para evitar loops infinitos
✅ **Prompts com diretrizes** claras sobre limitações
✅ **Sistema de alertas** para situações críticas

**⚠️ IMPORTANTE**:
- Este é um **assistente auxiliar**, não substitui julgamento médico
- Sempre valide respostas antes de aplicar clinicamente
- Use apenas em ambiente controlado e com supervisão

---

## 🧪 Testes

### **Casos de Teste Recomendados**

1. **Busca de prontuário existente**
   ```
   Médico: Mostre o prontuário do paciente 12345
   ```

2. **Busca de prontuário inexistente**
   ```
   Médico: Mostre o prontuário do paciente 99999
   ```

3. **Consulta de protocolo**
   ```
   Médico: Qual o protocolo para diabetes?
   ```

4. **Pergunta complexa (combina tools)**
   ```
   Médico: O paciente 12345 está com pressão alta, o que fazer?
   ```

5. **Verificação de exames**
   ```
   Médico: Há exames pendentes para o paciente 67890?
   ```

---

## 📝 Próximos Passos (Sugestões)

Para melhorar o sistema:

1. ✅ **Integrar modelo fine-tuned** da Etapa 1
2. ⬜ Conectar com banco de dados real do hospital
3. ⬜ Adicionar mais protocolos médicos
4. ⬜ Implementar sistema de autenticação
5. ⬜ Criar interface web (Streamlit ou Gradio)
6. ⬜ Adicionar logging e auditoria de decisões
7. ⬜ Integrar com sistema de prontuário eletrônico
8. ⬜ Adicionar suporte a imagens médicas (raio-X, etc.)

---

## 🤝 Contribuindo

Este é um projeto acadêmico (Tech Challenge). Para melhorias:

1. Adicione novos protocolos em `DatabaseProntuarios`
2. Crie novas tools com `@tool`
3. Ajuste os prompts do sistema conforme necessário
4. Teste com dados reais (anonimizados)

---

## 📚 Referências

- [LangChain Documentation](https://python.langchain.com/)
- [LangChain Agents](https://python.langchain.com/docs/modules/agents/)
- [LangChain Tools](https://python.langchain.com/docs/modules/agents/tools/)

---

## 📄 Licença

Projeto acadêmico desenvolvido para o Tech Challenge.

---

## 👥 Autor

Desenvolvido para atender aos requisitos da **Etapa 2 - Criação de assistente médico com LangChain**.

**Data**: Janeiro 2025
**Projeto**: Tech Challenge - Assistente Médico Virtual
