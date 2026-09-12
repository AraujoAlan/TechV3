"""
Sistema de Assistente Médico Virtual usando LangChain
Tech Challenge - Etapa 2: Criação de assistente médico com LangChain

LEGADO: este arquivo mantém o protótipo ReAct da etapa anterior. A demonstração
controlada usa `python -m app.cli`; o adapter LoRA real só é carregado por
`app.llm.factory.QwenLoraFinalAnswerLLM`.
"""

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent as create_agent
from langgraph.checkpoint.memory import MemorySaver
import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()


# ========== CONFIGURAÇÃO DO MODELO ==========
# OPÇÃO 1: Usar OpenAI (temporário para desenvolvimento)
def criar_llm_openai():
    """
    Modelo OpenAI para desenvolvimento inicial.
    """
    return ChatOpenAI(
        model="gpt-4o-mini",  # Modelo mais acessível
        temperature=0.3,  # Baixa temperatura para respostas mais precisas
        api_key=os.getenv("OPENAI_API_KEY")
    )


# OPÇÃO 2: Usar modelo local GRATUITO via Ollama
def criar_llm_local():
    """
    Modelo local gratuito usando Ollama.
    Primeiro instale o Ollama em https://ollama.ai
    Depois rode: ollama pull llama3.2
    """
    try:
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model="llama3.2",
            temperature=0.3
        )
    except Exception as e:
        print(f"\n⚠️  Erro ao carregar modelo local: {e}")
        print("Para usar modelo local gratuito:")
        print("1. Instale Ollama: https://ollama.ai")
        print("2. Execute: ollama pull llama3.2")
        print("3. Execute: pip install langchain-ollama")
        raise


# OPÇÃO 3: Usar modelo base compatível para demonstração
def criar_llm_base_legado():
    """
    Usa modelo base Qwen apenas para o protótipo legado ReAct.

    Não representa o adapter fine-tuned e não deve ser usado como evidência de
    integração do modelo treinado.
    """
    from langchain_community.llms import HuggingFacePipeline
    from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
    import torch

    # Usar modelo base para demonstração (leve e rápido)
    model_id = "Qwen/Qwen2.5-1.5B-Instruct"  # Modelo menor para demo

    print(f"\n🔄 Carregando modelo para demonstração: {model_id}")
    print("⏳ Aguarde o download (~1.5GB)...\n")
    print("📝 NOTA: O adapter fine-tuned está em notebooks/05_treino.ipynb")
    print("   Para o vídeo, demonstramos o PIPELINE LangChain funcionando.\n")

    # Carregar tokenizer
    print("   [1/2] Carregando tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(model_id)

    # Carregar modelo
    print("   [2/2] Carregando modelo...")
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        device_map="auto",
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        low_cpu_mem_usage=True
    )

    # Criar pipeline
    pipe = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
        max_new_tokens=256,
        temperature=0.3,
        do_sample=True
    )

    print("\n✅ Modelo carregado! Pipeline LangChain pronto!\n")
    return HuggingFacePipeline(pipeline=pipe)


# ========== BASE DE DADOS ESTRUTURADA ==========

class DatabaseProntuarios:
    """
    Gerenciador de banco de dados SQLite para prontuários do hospital.
    Em produção, substituir por PostgreSQL ou outro SGBD corporativo.
    """

    def __init__(self, db_path: str = "hospital.db"):
        """Inicializa conexão com banco de dados SQLite"""
        self.db_path = db_path
        self.conn = None
        self._inicializar_banco()

    def _inicializar_banco(self):
        """Cria tabelas e popula com dados de exemplo"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Permite acesso por nome de coluna

        cursor = self.conn.cursor()

        # Tabela de pacientes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pacientes (
                id TEXT PRIMARY KEY,
                nome TEXT NOT NULL,
                idade INTEGER,
                sexo TEXT,
                alergias TEXT,
                ultimo_atendimento TEXT
            )
        """)

        # Tabela de diagnósticos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS diagnosticos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paciente_id TEXT,
                diagnostico TEXT,
                data_diagnostico TEXT,
                FOREIGN KEY (paciente_id) REFERENCES pacientes(id)
            )
        """)

        # Tabela de medicamentos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS medicamentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paciente_id TEXT,
                medicamento TEXT,
                dosagem TEXT,
                data_inicio TEXT,
                FOREIGN KEY (paciente_id) REFERENCES pacientes(id)
            )
        """)

        # Tabela de exames
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS exames (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paciente_id TEXT,
                tipo_exame TEXT,
                status TEXT,
                data_solicitacao TEXT,
                data_realizacao TEXT,
                FOREIGN KEY (paciente_id) REFERENCES pacientes(id)
            )
        """)

        # Tabela de protocolos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS protocolos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                condicao TEXT UNIQUE,
                descricao TEXT,
                condutas TEXT
            )
        """)

        self.conn.commit()
        self._popular_dados_exemplo()

    def _popular_dados_exemplo(self):
        """Popula banco com dados de exemplo se estiver vazio"""
        cursor = self.conn.cursor()

        # Verifica se já tem dados
        cursor.execute("SELECT COUNT(*) FROM pacientes")
        if cursor.fetchone()[0] > 0:
            return  # Já populado

        # Inserir pacientes
        pacientes = [
            ("12345", "João Silva", 45, "M", "Penicilina", "2024-01-15"),
            ("67890", "Maria Santos", 62, "F", "", "2024-01-20")
        ]
        cursor.executemany(
            "INSERT INTO pacientes VALUES (?, ?, ?, ?, ?, ?)",
            pacientes
        )

        # Inserir diagnósticos
        diagnosticos = [
            ("12345", "Hipertensão", "2023-05-10"),
            ("12345", "Diabetes tipo 2", "2023-06-15"),
            ("67890", "Artrite reumatoide", "2022-11-20")
        ]
        cursor.executemany(
            "INSERT INTO diagnosticos (paciente_id, diagnostico, data_diagnostico) VALUES (?, ?, ?)",
            diagnosticos
        )

        # Inserir medicamentos
        medicamentos = [
            ("12345", "Losartana", "50mg", "2023-05-10"),
            ("12345", "Metformina", "850mg", "2023-06-15"),
            ("67890", "Metotrexato", "15mg", "2022-11-20")
        ]
        cursor.executemany(
            "INSERT INTO medicamentos (paciente_id, medicamento, dosagem, data_inicio) VALUES (?, ?, ?, ?)",
            medicamentos
        )

        # Inserir exames
        exames = [
            ("12345", "Hemograma completo", "pendente", "2024-01-15", None),
            ("12345", "HbA1c", "pendente", "2024-01-15", None),
            ("67890", "Fator reumatoide", "pendente", "2024-01-20", None)
        ]
        cursor.executemany(
            "INSERT INTO exames (paciente_id, tipo_exame, status, data_solicitacao, data_realizacao) VALUES (?, ?, ?, ?, ?)",
            exames
        )

        # Inserir protocolos
        protocolos = [
            ("hipertensao",
             "Protocolo de tratamento para hipertensão arterial",
             "1. Monitorar pressão arterial diariamente\n2. Avaliar função renal a cada 6 meses\n3. Orientar dieta hipossódica\n4. Prescrever IECA ou BRA se não houver contraindicação"),
            ("diabetes",
             "Protocolo de tratamento para diabetes tipo 2",
             "1. Monitorar glicemia capilar\n2. Solicitar HbA1c a cada 3 meses\n3. Avaliar função renal e fundo de olho anualmente\n4. Iniciar com metformina se não houver contraindicação")
        ]
        cursor.executemany(
            "INSERT INTO protocolos (condicao, descricao, condutas) VALUES (?, ?, ?)",
            protocolos
        )

        self.conn.commit()

    def buscar_prontuario_completo(self, paciente_id: str) -> Optional[Dict]:
        """Busca prontuário completo do paciente com todas as informações relacionadas"""
        cursor = self.conn.cursor()

        # Buscar dados do paciente
        cursor.execute("SELECT * FROM pacientes WHERE id = ?", (paciente_id,))
        paciente = cursor.fetchone()

        if not paciente:
            return None

        # Buscar diagnósticos
        cursor.execute("SELECT diagnostico FROM diagnosticos WHERE paciente_id = ?", (paciente_id,))
        diagnosticos = [row[0] for row in cursor.fetchall()]

        # Buscar medicamentos
        cursor.execute("SELECT medicamento, dosagem FROM medicamentos WHERE paciente_id = ?", (paciente_id,))
        medicamentos = [f"{row[0]} {row[1]}" for row in cursor.fetchall()]

        return {
            "id": paciente["id"],
            "nome": paciente["nome"],
            "idade": paciente["idade"],
            "sexo": paciente["sexo"],
            "diagnosticos": diagnosticos,
            "medicamentos": medicamentos,
            "alergias": paciente["alergias"],
            "ultimo_atendimento": paciente["ultimo_atendimento"]
        }

    def buscar_exames_pendentes(self, paciente_id: str) -> List[Dict]:
        """Busca exames pendentes de um paciente"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT tipo_exame, data_solicitacao
            FROM exames
            WHERE paciente_id = ? AND status = 'pendente'
        """, (paciente_id,))

        return [{"tipo": row[0], "solicitado_em": row[1]} for row in cursor.fetchall()]

    def buscar_protocolo(self, condicao: str) -> Optional[Dict]:
        """Busca protocolo médico por condição"""
        cursor = self.conn.cursor()
        condicao_lower = condicao.lower().replace(" ", "")

        cursor.execute("""
            SELECT descricao, condutas
            FROM protocolos
            WHERE LOWER(REPLACE(condicao, ' ', '')) = ?
        """, (condicao_lower,))

        protocolo = cursor.fetchone()
        if not protocolo:
            return None

        return {
            "descricao": protocolo[0],
            "condutas": protocolo[1].split("\n")
        }

    def listar_protocolos_disponiveis(self) -> List[str]:
        """Lista todos os protocolos disponíveis"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT condicao FROM protocolos")
        return [row[0] for row in cursor.fetchall()]

    def fechar(self):
        """Fecha conexão com banco de dados"""
        if self.conn:
            self.conn.close()


# Instância global do banco de dados
db = DatabaseProntuarios()


# ========== FERRAMENTAS (TOOLS) DO LANGCHAIN ==========

@tool
def buscar_prontuario(paciente_id: str) -> str:
    """
    Busca informações do prontuário de um paciente pelo ID no banco de dados.
    Retorna dados atualizados do paciente incluindo diagnósticos, medicamentos e alergias.

    Args:
        paciente_id: ID único do paciente no sistema

    Returns:
        Informações completas do prontuário ou mensagem de erro
    """
    prontuario = db.buscar_prontuario_completo(paciente_id)

    if not prontuario:
        return f"Paciente com ID {paciente_id} não encontrado no sistema."

    alergias_texto = prontuario['alergias'] if prontuario['alergias'] else 'Nenhuma alergia registrada'

    info = f"""
PRONTUÁRIO DO PACIENTE - ID: {paciente_id}
Nome: {prontuario['nome']}
Idade: {prontuario['idade']} anos
Sexo: {prontuario['sexo']}
Diagnósticos: {', '.join(prontuario['diagnosticos'])}
Medicamentos em uso: {', '.join(prontuario['medicamentos'])}
Alergias: {alergias_texto}
Último atendimento: {prontuario['ultimo_atendimento']}
    """
    return info.strip()


@tool
def verificar_exames_pendentes(paciente_id: str) -> str:
    """
    Verifica se há exames pendentes para um paciente consultando o banco de dados.
    Útil para acompanhamento de solicitações médicas e gestão de procedimentos.

    Args:
        paciente_id: ID único do paciente no sistema

    Returns:
        Lista de exames pendentes ou mensagem indicando ausência
    """
    exames = db.buscar_exames_pendentes(paciente_id)

    if not exames:
        return f"Não há exames pendentes para o paciente {paciente_id}."

    resultado = f"EXAMES PENDENTES - Paciente {paciente_id}:\n"
    for i, exame in enumerate(exames, 1):
        resultado += f"{i}. {exame['tipo']} - Solicitado em {exame['solicitado_em']}\n"

    return resultado.strip()


@tool
def consultar_protocolo(condicao: str) -> str:
    """
    Consulta o protocolo médico do hospital para uma condição específica no banco de dados.
    Retorna diretrizes e condutas padronizadas conforme protocolos institucionais.

    Args:
        condicao: Nome da condição médica (ex: "hipertensao", "diabetes")

    Returns:
        Protocolo detalhado ou mensagem de erro
    """
    protocolo = db.buscar_protocolo(condicao)

    if not protocolo:
        protocolos_disponiveis = db.listar_protocolos_disponiveis()
        return f"Protocolo para '{condicao}' não encontrado. Protocolos disponíveis: {', '.join(protocolos_disponiveis)}"

    resultado = f"""
PROTOCOLO: {protocolo['descricao']}

CONDUTAS RECOMENDADAS:
"""
    for i, conduta in enumerate(protocolo['condutas'], 1):
        resultado += f"{i}. {conduta}\n"

    return resultado.strip()


@tool
def registrar_alerta_equipe(paciente_id: str, mensagem: str) -> str:
    """
    Registra um alerta para a equipe médica sobre um paciente.

    Args:
        paciente_id: ID do paciente
        mensagem: Mensagem de alerta

    Returns:
        Confirmação do registro
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Em produção, isso gravaria em um sistema de alertas real
    log_alerta = f"""
ALERTA REGISTRADO
Data/Hora: {timestamp}
Paciente ID: {paciente_id}
Mensagem: {mensagem}
Status: Enviado para equipe médica
    """

    print(f"\n{'='*60}")
    print("🚨 NOVO ALERTA MÉDICO")
    print(log_alerta)
    print('='*60)

    return f"Alerta registrado com sucesso em {timestamp} para o paciente {paciente_id}."


# ========== CONFIGURAÇÃO DO ASSISTENTE ==========

def criar_assistente_medico(usar_modelo_base_legado: bool = False):
    """
    Cria o assistente médico virtual com LangChain.
    Pipeline completo com:
    - Modelo de linguagem (local ou modelo base de demonstração)
    - Tools para consulta em base de dados estruturada
    - Memory para contexto persistente
    - Sistema de contextualização de respostas

    Args:
        usar_modelo_base_legado: Se True, usa o modelo base de demonstração;
            se False, usa Ollama local.
    """

    # Escolha do modelo
    if usar_modelo_base_legado:
        print("\n🔬 Usando modelo base para demonstração (não é o adapter fine-tuned)...")
        llm = criar_llm_base_legado()
    else:
        print("\n🤖 Usando modelo local via Ollama...")
        llm = criar_llm_local()

    # Ferramentas disponíveis para o assistente
    # Essas ferramentas consultam o banco de dados estruturado
    tools = [
        buscar_prontuario,
        verificar_exames_pendentes,
        consultar_protocolo,
        registrar_alerta_equipe
    ]

    # Prompt do sistema aplicado ao agente em toda invocação.
    system_message = """
Você é um assistente clínico de um hospital maternidade, que apoia profissionais de saúde no acompanhamento de gestantes, puérperas e bebês até 1 ano.

Você responde a médicos, em registro técnico. Você apoia a decisão clínica; você não a substitui.

SUAS RESPONSABILIDADES:
1. Auxiliar médicos com condutas clínicas baseadas nos protocolos do hospital
2. Consultar prontuários e contextualizar respostas com dados atualizados do paciente
3. Sugerir tratamentos conforme diretrizes internas
4. Verificar exames pendentes e alertar a equipe quando necessário
5. Responder dúvidas técnicas sobre procedimentos

DIRETRIZES IMPORTANTES:
- SEMPRE consulte o prontuário do paciente antes de dar recomendações específicas
- Baseie suas respostas nos protocolos do hospital disponíveis nas ferramentas
- Contextualize suas respostas com os dados do paciente (idade, diagnósticos, medicamentos, alergias)
- Nunca prescreva medicamento, dose ou conduta como determinação final: toda sugestão precisa de validação do profissional responsável
- Quando a informação disponível não sustentar uma resposta, diga isso em vez de preencher a lacuna
- Registre alertas quando identificar situações críticas ou inconsistências
- NUNCA invente informações - use apenas dados disponíveis nas ferramentas

FLUXO DE TRABALHO RECOMENDADO:
1. Se a pergunta menciona um paciente específico → busque o prontuário primeiro
2. Verifique se há exames pendentes relevantes para o caso
3. Consulte o protocolo apropriado se houver
4. Contextualize a resposta com os dados obtidos
5. Se necessário, registre alertas para a equipe

LIMITAÇÕES:
- Você é um auxiliar, não substitui o julgamento clínico do médico
- Sempre mencione a necessidade de avaliação presencial quando relevante
- Indique quando uma conduta foge do escopo dos protocolos padrão
"""

    # Configuração de memória persistente para manter contexto da conversa
    memory = MemorySaver()

    # Criação do agente com langgraph e memory
    agent_executor = create_agent(
        model=llm,
        tools=tools,
        checkpointer=memory,  # Adiciona memória para contexto persistente
        prompt=system_message,
    )

    return agent_executor


# ========== INTERFACE DE USO ==========

def executar_assistente(usar_modelo_base_legado: bool = False):
    """
    Função principal para executar o assistente médico.
    Pipeline completo com consulta em base de dados estruturada e contextualização.

    Args:
        usar_modelo_base_legado: Se True, usa o modelo base de demonstração;
            se False, usa Ollama.
    """
    print("="*70)
    print("🏥 ASSISTENTE MÉDICO VIRTUAL - TECH CHALLENGE")
    print("="*70)
    print("\n📊 Configuração do Pipeline LangChain:")
    print("  ✓ Base de dados SQLite estruturada")
    print("  ✓ Tools para consulta de prontuários e protocolos")
    print("  ✓ Memory para contexto persistente")
    print("  ✓ Sistema de contextualização de respostas")

    assistente = criar_assistente_medico(usar_modelo_base_legado)

    print("\n✅ Assistente inicializado com sucesso!")
    print("\n🔧 Ferramentas disponíveis:")
    print("  • Buscar prontuário de paciente (consulta BD)")
    print("  • Verificar exames pendentes (consulta BD)")
    print("  • Consultar protocolos médicos (consulta BD)")
    print("  • Registrar alertas para equipe")
    print("\n💬 Exemplos de perguntas:")
    print("  - Preciso de informações sobre o paciente 12345")
    print("  - O paciente 12345 tem diabetes. Qual o protocolo?")
    print("  - Quais exames estão pendentes para o paciente 67890?")
    print("\nDigite 'sair' para encerrar.\n")

    # Configuração de thread para memória persistente
    config = {"configurable": {"thread_id": "sessao_medica_1"}}

    # Loop de conversação
    while True:
        try:
            pergunta = input("🩺 Médico: ").strip()

            if pergunta.lower() in ['sair', 'exit', 'quit']:
                print("\n👋 Encerrando assistente. Até logo!")
                db.fechar()  # Fecha conexão com banco de dados
                break

            if not pergunta:
                continue

            print("\n🤖 Assistente processando...\n")

            # Invoca o assistente com memory/context
            resposta = assistente.invoke(
                {"messages": [("user", pergunta)]},
                config=config  # Mantém contexto entre perguntas
            )

            print(f"\n💡 Assistente: {resposta['messages'][-1].content}\n")
            print("-" * 70 + "\n")

        except EOFError:
            # Ambiente sem input interativo
            print("\n⚠️  Ambiente não suporta input interativo.")
            print("Execute em um terminal normal para usar o modo interativo.\n")
            db.fechar()
            break
        except KeyboardInterrupt:
            print("\n\n👋 Encerrando assistente. Até logo!")
            db.fechar()
            break
        except Exception as e:
            print(f"\n❌ Erro: {str(e)}\n")
            import traceback
            traceback.print_exc()


# ========== EXEMPLOS DE USO ==========

def demonstrar_uso():
    """
    Demonstra casos de uso do assistente sem interação manual.
    """
    print("="*70)
    print("🧪 DEMONSTRAÇÃO DO ASSISTENTE MÉDICO")
    print("="*70)

    assistente = criar_assistente_medico()

    exemplos = [
        "Preciso de informações sobre o paciente 12345",
        "Quais exames estão pendentes para o paciente 12345?",
        "Qual o protocolo para tratamento de hipertensão?",
        "Com base no prontuário do paciente 67890, o que você recomenda?"
    ]

    for i, pergunta in enumerate(exemplos, 1):
        print(f"\n{'='*70}")
        print(f"EXEMPLO {i}: {pergunta}")
        print('='*70)

        try:
            resposta = assistente.invoke({"messages": [("user", pergunta)]})
            print(f"\n💡 Resposta: {resposta['messages'][-1].content}\n")
        except Exception as e:
            print(f"\n❌ Erro: {str(e)}\n")


if __name__ == "__main__":
    import sys
    import io

    # Configurar encoding UTF-8 no Windows
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

    # Configuração de linha de comando
    usar_modelo_base_legado = "--base-legacy" in sys.argv
    modo_demo = "--demo" in sys.argv or "-d" in sys.argv

    if modo_demo:
        # Modo demonstração
        demonstrar_uso()
    else:
        # Modo interativo (padrão)
        print("\n🎛️  Opções de execução:")
        print("  python main.py              → Usa Ollama local")
        print("  python main.py --base-legacy → Usa modelo base Qwen no protótipo legado")
        print("  python -m app.cli            → Usa o workflow LangGraph controlado")
        print("  python main.py --demo       → Modo demonstração\n")

        executar_assistente(usar_modelo_base_legado=usar_modelo_base_legado)
