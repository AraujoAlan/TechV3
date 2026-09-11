"""O modelo que decide quais consultas fazer.

É o GLM, via API da z.ai — o mesmo modelo que reescreveu o dataset no notebook
`03`. Ele não escreve a resposta ao médico: escolhe ferramentas, monta os
argumentos e para quando tem o suficiente.

Por que não usar o próprio modelo fine-tunado para isso: ele foi ajustado em
pares pergunta-resposta clínicos, sem um único exemplo de tool calling. Pedir
que ele emita JSON de chamada de função é pedir exatamente o que não treinamos.
"""

from langchain_openai import ChatOpenAI

from app import config


def criar_roteador() -> ChatOpenAI:
    if not config.ROTEADOR_API_KEY:
        raise RuntimeError(
            "Z_API_KEY ausente. O roteador usa a API da z.ai — defina a chave no "
            ".env ou no ambiente do container."
        )

    return ChatOpenAI(
        model=config.ROTEADOR_MODELO,
        base_url=config.ROTEADOR_BASE_URL,
        api_key=config.ROTEADOR_API_KEY,
        # Escolha de ferramenta é decisão, não redação: temperatura 0 para que a
        # mesma pergunta leve às mesmas consultas, o que a auditoria agradece.
        temperature=0,
        timeout=60,
        max_retries=2,
    )
