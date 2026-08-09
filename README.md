# 🏥 Assistente Médico Virtual - Tech Challenge Etapa 2

Sistema de assistente médico virtual desenvolvido com **LangChain**, capaz de auxiliar em condutas clínicas, responder dúvidas de médicos e sugerir procedimentos baseados nos protocolos internos do hospital.

## 📋 Requisitos Atendidos

✅ **Pipeline com LangChain** que integra LLM customizada
✅ **Consultas em base de dados estruturadas** (prontuários e registros)
✅ **Contextualização de respostas** com informações atualizadas do paciente
✅ **Preparado para integração** com modelo fine-tuned da Etapa 1

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
# Clone ou acesse o diretório do projeto
cd LangChain

# Instale as dependências
pip install -r requirements.txt

# Configure as variáveis de ambiente
cp .env.example .env
# Edite o .env com suas credenciais (se necessário)
```

### 2. **Execução**

```bash
# Modo interativo (conversa com o assistente)
python main.py

# Modo demonstração (executa exemplos automáticos)
# Descomente a linha no final do main.py e execute
```

### 3. **Exemplos de Perguntas**

```
🩺 Médico: Preciso de informações sobre o paciente 12345
🩺 Médico: Quais exames estão pendentes para o paciente 12345?
🩺 Médico: Qual o protocolo para tratamento de hipertensão?
🩺 Médico: O paciente 67890 está com dor nas articulações, o que fazer?
```

---

## 🔧 Integração com Modelo Fine-Tuned

### **Passo 1: Escolha a Opção de Integração**

Consulte `INSTRUCOES_INTEGRACAO.md` para ver as 3 opções:

1. **Ollama** (recomendado para modelos locais)
2. **HuggingFace** (flexível para qualquer modelo)
3. **API Customizada** (melhor performance em produção)

### **Passo 2: Modifique a Função**

No arquivo `main.py`, localize a função `criar_llm_finetuned()` (linha ~34) e substitua conforme o exemplo da opção escolhida.

**Exemplo com Ollama:**

```python
def criar_llm_finetuned():
    from langchain_community.llms import Ollama
    return Ollama(
        model="assistente-medico",  # Seu modelo fine-tuned
        temperature=0.3
    )
```

### **Passo 3: Teste**

```bash
python main.py
```

---

## 📁 Estrutura do Projeto

```
LangChain/
├── main.py                      # Código principal do assistente
├── requirements.txt             # Dependências do projeto
├── .env.example                 # Exemplo de variáveis de ambiente
├── INSTRUCOES_INTEGRACAO.md     # Guia de integração com modelo fine-tuned
└── README.md                    # Este arquivo
```

---

## 🏗️ Arquitetura Técnica

### **1. Pipeline LangChain**

```
Pergunta do Médico
    ↓
Agent LangChain (decide o que fazer)
    ↓
Tools (busca dados necessários)
    ↓
LLM Fine-Tuned (processa e raciocina)
    ↓
Resposta Contextualizada
```

### **2. Componentes Principais**

- **LLM**: Modelo de linguagem (OpenAI temporário → Fine-tuned)
- **Agent**: Sistema de decisão automática do LangChain
- **Tools**: Ferramentas para acessar dados (prontuários, protocolos, etc.)
- **Memory**: Mantém contexto da conversa
- **Prompt System**: Define comportamento e diretrizes do assistente

### **3. Fluxo de Decisão**

1. Médico faz pergunta
2. Agent analisa a pergunta
3. Agent decide quais tools usar
4. Tools buscam dados relevantes
5. LLM recebe pergunta + contexto dos tools
6. LLM gera resposta baseada em protocolos
7. Resposta é retornada ao médico

---

## 📊 Dados de Exemplo

O sistema inclui dados simulados para teste:

- **2 pacientes** com prontuários completos
- **Exames pendentes** para ambos
- **2 protocolos médicos** (hipertensão e diabetes)

**Em produção**, substitua pela conexão real:

```python
# No arquivo main.py, classe DatabaseProntuarios
# Substituir por:
import psycopg2  # ou outro driver de banco

class DatabaseProntuarios:
    def __init__(self):
        self.conn = psycopg2.connect(
            host="seu_host",
            database="hospital_db",
            user="usuario",
            password="senha"
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
