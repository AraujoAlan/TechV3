"""
Sistema de Assistente Médico Virtual usando LangChain
Tech Challenge - Etapa 2: Criação de assistente médico com LangChain

IMPORTANTE: Este código está preparado para integração com modelo fine-tuned.
Para usar o modelo customizado, modifique a seção CONFIGURAÇÃO DO MODELO.
"""

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.tools import tool
from langchain.memory import ConversationBufferMemory
from langchain_core.messages import SystemMessage
import os
from datetime import datetime
from typing import Dict, List, Optional


# ========== CONFIGURAÇÃO DO MODELO ==========
# OPÇÃO 1: Usar OpenAI (temporário para desenvolvimento)
def criar_llm_openai():
    """
    Modelo OpenAI para desenvolvimento inicial.
    """
    return ChatOpenAI(
        model="gpt-4",
        temperature=0.3,  # Baixa temperatura para respostas mais precisas
        api_key=os.getenv("OPENAI_API_KEY")
    )


# OPÇÃO 2: Usar modelo fine-tuned local (LLaMA, Falcon, etc.)
def criar_llm_finetuned():
    """
    SUBSTITUA ESTA FUNÇÃO quando tiver o modelo fine-tuned pronto.

    Exemplos de integração:

    1. Para modelo local via Ollama:
        from langchain_community.llms import Ollama
        return Ollama(
            model="llama2-medical-finetuned",
            temperature=0.3
        )

    2. Para modelo via HuggingFace:
        from langchain_community.llms import HuggingFacePipeline
        from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline

        model_id = "caminho/para/seu/modelo/finetuned"
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForCausalLM.from_pretrained(model_id)

        pipe = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer,
            max_new_tokens=512,
            temperature=0.3
        )

        return HuggingFacePipeline(pipeline=pipe)

    3. Para modelo via API customizada:
        from langchain_community.llms import TextGen
        return TextGen(
            model_url="http://localhost:5000/api/generate",
            temperature=0.3
        )
    """
    # Por enquanto, retorna OpenAI como placeholder
    return criar_llm_openai()


# ========== SIMULAÇÃO DE BASE DE DADOS ==========
# Em produção, substituir por conexão real com banco de dados do hospital

class DatabaseProntuarios:
    """Simula banco de dados de prontuários do hospital"""

    def __init__(self):
        # Dados simulados - em produção, conectar ao banco real
        self.prontuarios = {
            "12345": {
                "nome": "João Silva",
                "idade": 45,
                "sexo": "M",
                "diagnosticos": ["Hipertensão", "Diabetes tipo 2"],
                "medicamentos": ["Losartana 50mg", "Metformina 850mg"],
                "alergias": ["Penicilina"],
                "ultimo_atendimento": "2024-01-15"
            },
            "67890": {
                "nome": "Maria Santos",
                "idade": 62,
                "sexo": "F",
                "diagnosticos": ["Artrite reumatoide"],
                "medicamentos": ["Metotrexato 15mg"],
                "alergias": [],
                "ultimo_atendimento": "2024-01-20"
            }
        }

        self.exames_pendentes = {
            "12345": [
                {"tipo": "Hemograma completo", "solicitado_em": "2024-01-15"},
                {"tipo": "HbA1c", "solicitado_em": "2024-01-15"}
            ],
            "67890": [
                {"tipo": "Fator reumatoide", "solicitado_em": "2024-01-20"}
            ]
        }

        self.protocolos = {
            "hipertensao": {
                "descricao": "Protocolo de tratamento para hipertensão arterial",
                "condutas": [
                    "Monitorar pressão arterial diariamente",
                    "Avaliar função renal a cada 6 meses",
                    "Orientar dieta hipossódica",
                    "Prescrever IECA ou BRA se não houver contraindicação"
                ]
            },
            "diabetes": {
                "descricao": "Protocolo de tratamento para diabetes tipo 2",
                "condutas": [
                    "Monitorar glicemia capilar",
                    "Solicitar HbA1c a cada 3 meses",
                    "Avaliar função renal e fundo de olho anualmente",
                    "Iniciar com metformina se não houver contraindicação"
                ]
            }
        }


# Instância global do banco de dados
db = DatabaseProntuarios()


# ========== FERRAMENTAS (TOOLS) DO LANGCHAIN ==========

@tool
def buscar_prontuario(paciente_id: str) -> str:
    """
    Busca informações do prontuário de um paciente pelo ID.

    Args:
        paciente_id: ID único do paciente no sistema

    Returns:
        Informações completas do prontuário ou mensagem de erro
    """
    prontuario = db.prontuarios.get(paciente_id)

    if not prontuario:
        return f"Paciente com ID {paciente_id} não encontrado no sistema."

    info = f"""
PRONTUÁRIO DO PACIENTE - ID: {paciente_id}
Nome: {prontuario['nome']}
Idade: {prontuario['idade']} anos
Sexo: {prontuario['sexo']}
Diagnósticos: {', '.join(prontuario['diagnosticos'])}
Medicamentos em uso: {', '.join(prontuario['medicamentos'])}
Alergias: {', '.join(prontuario['alergias']) if prontuario['alergias'] else 'Nenhuma alergia registrada'}
Último atendimento: {prontuario['ultimo_atendimento']}
    """
    return info.strip()


@tool
def verificar_exames_pendentes(paciente_id: str) -> str:
    """
    Verifica se há exames pendentes para um paciente.

    Args:
        paciente_id: ID único do paciente no sistema

    Returns:
        Lista de exames pendentes ou mensagem indicando ausência
    """
    exames = db.exames_pendentes.get(paciente_id, [])

    if not exames:
        return f"Não há exames pendentes para o paciente {paciente_id}."

    resultado = f"EXAMES PENDENTES - Paciente {paciente_id}:\n"
    for i, exame in enumerate(exames, 1):
        resultado += f"{i}. {exame['tipo']} - Solicitado em {exame['solicitado_em']}\n"

    return resultado.strip()


@tool
def consultar_protocolo(condicao: str) -> str:
    """
    Consulta o protocolo médico do hospital para uma condição específica.

    Args:
        condicao: Nome da condição médica (ex: "hipertensao", "diabetes")

    Returns:
        Protocolo detalhado ou mensagem de erro
    """
    condicao_lower = condicao.lower().replace(" ", "_")
    protocolo = db.protocolos.get(condicao_lower)

    if not protocolo:
        return f"Protocolo para '{condicao}' não encontrado. Protocolos disponíveis: {', '.join(db.protocolos.keys())}"

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

def criar_assistente_medico():
    """
    Cria o assistente médico virtual com LangChain.
    """

    # Escolha do modelo (trocar para criar_llm_finetuned() quando disponível)
    llm = criar_llm_finetuned()  # ou criar_llm_openai() para desenvolvimento

    # Ferramentas disponíveis para o assistente
    tools = [
        buscar_prontuario,
        verificar_exames_pendentes,
        consultar_protocolo,
        registrar_alerta_equipe
    ]

    # Prompt do sistema - define o comportamento do assistente
    system_message = SystemMessage(content="""
Você é um assistente médico virtual especializado do hospital, treinado com os protocolos e procedimentos internos.

SUAS RESPONSABILIDADES:
1. Auxiliar médicos com condutas clínicas baseadas nos protocolos do hospital
2. Responder dúvidas técnicas sobre procedimentos
3. Sugerir tratamentos conforme diretrizes internas
4. Verificar exames pendentes e alertar a equipe quando necessário
5. Fornecer informações contextualizadas sobre pacientes

DIRETRIZES IMPORTANTES:
- Sempre baseie suas respostas nos protocolos do hospital
- Ao falar sobre um paciente, SEMPRE consulte o prontuário primeiro
- Seja preciso e objetivo nas recomendações
- Em caso de dúvida, sugira consultar um especialista
- Registre alertas quando identificar situações críticas
- NUNCA invente informações - use apenas dados disponíveis nas ferramentas

LIMITAÇÕES:
- Você é um auxiliar, não substitui o julgamento clínico do médico
- Sempre que relevante, mencione a necessidade de avaliação presencial
- Indique quando uma conduta foge do escopo dos protocolos padrão
""")

    # Template do prompt com histórico de conversa
    prompt = ChatPromptTemplate.from_messages([
        system_message,
        MessagesPlaceholder(variable_name="chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad")
    ])

    # Criação do agente
    agent = create_openai_functions_agent(llm, tools, prompt)

    # Executor do agente com memória
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,  # Mostra o raciocínio do agente
        max_iterations=5,  # Limita iterações para evitar loops
        handle_parsing_errors=True
    )

    return agent_executor


# ========== INTERFACE DE USO ==========

def executar_assistente():
    """
    Função principal para executar o assistente médico.
    """
    print("="*70)
    print("🏥 ASSISTENTE MÉDICO VIRTUAL - TECH CHALLENGE")
    print("="*70)
    print("\nInicializando assistente...")

    assistente = criar_assistente_medico()

    print("\n✅ Assistente inicializado com sucesso!")
    print("\nFerramentas disponíveis:")
    print("  • Buscar prontuário de paciente")
    print("  • Verificar exames pendentes")
    print("  • Consultar protocolos médicos")
    print("  • Registrar alertas para equipe")
    print("\nDigite 'sair' para encerrar.\n")

    # Loop de conversação
    while True:
        try:
            pergunta = input("🩺 Médico: ").strip()

            if pergunta.lower() in ['sair', 'exit', 'quit']:
                print("\n👋 Encerrando assistente. Até logo!")
                break

            if not pergunta:
                continue

            print("\n🤖 Assistente processando...\n")

            resposta = assistente.invoke({"input": pergunta})

            print(f"\n💡 Assistente: {resposta['output']}\n")
            print("-" * 70 + "\n")

        except KeyboardInterrupt:
            print("\n\n👋 Encerrando assistente. Até logo!")
            break
        except Exception as e:
            print(f"\n❌ Erro: {str(e)}\n")


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
            resposta = assistente.invoke({"input": pergunta})
            print(f"\n💡 Resposta: {resposta['output']}\n")
        except Exception as e:
            print(f"\n❌ Erro: {str(e)}\n")


if __name__ == "__main__":
    # Descomente a linha que deseja executar:

    # Modo interativo (padrão)
    executar_assistente()

    # Modo demonstração
    # demonstrar_uso()
