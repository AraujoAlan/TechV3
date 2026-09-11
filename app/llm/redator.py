"""O modelo fine-tunado, que escreve a resposta ao médico.

É o adapter LoRA sobre `Qwen3.5-4B` treinado nos notebooks `04`–`06`, servido em
GGUF pelo `llama-server` do llama.cpp, que expõe API compatível com a da OpenAI
— daí o `ChatOpenAI` apontando para outro host.

Ele recebe a pergunta já acompanhada do que as ferramentas trouxeram e responde
no registro médico-a-médico em que foi ajustado. É aqui que o fine-tuning
aparece para o usuário: o roteador poderia ter chamado as mesmas ferramentas com
qualquer modelo, mas o texto final é o que a loss de validação melhorou de 2,216
para 1,305.
"""

from langchain_openai import ChatOpenAI

from app import config

# Marca os tokens deste modelo no stream do grafo, para a camada de transmissão
# saber quais mandar para a tela.
ETIQUETA_REDATOR = "redator"


def criar_redator() -> ChatOpenAI:
    return ChatOpenAI(
        model=config.REDATOR_MODELO,
        base_url=config.REDATOR_BASE_URL,
        # O llama-server não valida chave nenhuma, mas o cliente exige o campo.
        api_key=config.REDATOR_API_KEY,
        temperature=config.REDATOR_TEMPERATURA,
        max_tokens=config.REDATOR_MAX_TOKENS,
        # `streaming=True` faz o cliente consumir a resposta token a token mesmo
        # quando o agente chama `invoke`. É o que permite à camada de transmissão
        # capturar os tokens pelo stream do grafo.
        streaming=True,
        # A etiqueta separa estes tokens dos do roteador no stream. Sem ela, a
        # fala que o GLM produz antes da troca de modelo vazaria para a tela.
        tags=[ETIQUETA_REDATOR],
        timeout=120,
        max_retries=1,
    )


class FiltroPensamento:
    """Remove o bloco `<think></think>` da frente da resposta, durante o stream.

    O chat template do Qwen3.5 abre todo turno do assistente com um bloco de
    raciocínio, vazio quando a resposta é direta. O notebook `05` documenta isso
    — e o modelo foi treinado com o bloco dentro do alvo, então ele o reproduz na
    geração. Sem filtro, o médico vê `<think></think>` antes de cada resposta.

    Filtrar no stream, e não no fim, é o que preserva o efeito de digitação: os
    tokens seguem saindo à medida que chegam. O filtro só segura o começo, até
    ter caracteres suficientes para decidir se aquilo é um bloco de pensamento ou
    já é a resposta.
    """

    ABERTURA = "<think>"
    FECHAMENTO = "</think>"

    def __init__(self) -> None:
        self._buffer = ""
        self._liberado = False
        self._dentro_do_bloco = False
        self._emitiu = False

    def _emitir(self, texto: str) -> str:
        """Segura o espaço em branco que antecede o primeiro caractere real.

        Sem isso, a quebra de linha que o modelo põe depois de `</think>` vira o
        primeiro token da resposta, e a interface abre a bolha com uma linha
        vazia.
        """
        if not self._emitiu:
            texto = texto.lstrip()
            if texto:
                self._emitiu = True
        return texto

    def processar(self, pedaco: str) -> str:
        """Recebe um pedaço do stream e devolve o que pode ser exibido agora."""
        if self._liberado:
            return self._emitir(pedaco)

        self._buffer += pedaco

        if self._dentro_do_bloco:
            fim = self._buffer.find(self.FECHAMENTO)
            if fim == -1:
                return ""  # bloco ainda aberto, continua engolindo
            texto = self._buffer[fim + len(self.FECHAMENTO) :]
            self._buffer = ""
            self._liberado = True
            self._dentro_do_bloco = False
            return self._emitir(texto)

        inicio = self._buffer.lstrip()

        if not inicio:
            return ""  # só espaço em branco até agora

        if inicio.startswith(self.ABERTURA):
            self._dentro_do_bloco = True
            self._buffer = inicio
            return self.processar("")

        if self.ABERTURA.startswith(inicio):
            return ""  # pode ser o começo de "<think>", espera mais

        # Não é bloco de pensamento: libera tudo e sai do caminho.
        self._liberado = True
        texto = self._buffer
        self._buffer = ""
        return self._emitir(texto)

    def finalizar(self) -> str:
        """O que sobrou no buffer quando o stream terminou."""
        if self._liberado or self._dentro_do_bloco:
            # Bloco aberto que nunca fechou é raciocínio incompleto: descartar é
            # melhor que mostrar `<think>` solto ao médico.
            return ""
        texto = self._buffer
        self._buffer = ""
        self._liberado = True
        return self._emitir(texto)
