"""
Sistema de Assistente Médico Virtual usando LangChain
Tech Challenge - Etapa 2: Criação de assistente médico com LangChain

IMPORTANTE: Este código está preparado para integração com modelo fine-tuned.
Para usar o modelo customizado, modifique a seção CONFIGURAÇÃO DO MODELO.
"""

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage
from langgraph.prebuilt import create_react_agent
import os
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

    # Escolha do modelo
    # Use criar_llm_local() para modelo gratuito local
    # Use criar_llm_openai() se tiver créditos na OpenAI
    llm = criar_llm_local()

    # Ferramentas disponíveis para o assistente
    tools = [
        buscar_prontuario,
        verificar_exames_pendentes,
        consultar_protocolo,
        registrar_alerta_equipe
    ]

    # Prompt do sistema - define o comportamento do assistente
    system_message = """
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
"""

    # Adiciona a mensagem do sistema ao modelo
    llm_with_system = llm.bind(system_message=system_message)

    # Criação do agente com langgraph
    agent_executor = create_react_agent(
        model=llm_with_system,
        tools=tools
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

            resposta = assistente.invoke({"messages": [("user", pergunta)]})

            print(f"\n💡 Assistente: {resposta['messages'][-1].content}\n")
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
            resposta = assistente.invoke({"messages": [("user", pergunta)]})
            print(f"\n💡 Resposta: {resposta['messages'][-1].content}\n")
        except Exception as e:
            print(f"\n❌ Erro: {str(e)}\n")


if __name__ == "__main__":
    # Descomente a linha que deseja executar:

    # Modo interativo (padrão)
    executar_assistente()

    # Modo demonstração
    # demonstrar_uso()
