import os
import re

from app.contracts.errors import FinalAnswerModelUnavailable, GeneralLLMUnavailable
from app.contracts.models import AnalysisResult, CritiqueResult, InterpretationResult, Source

FINAL_ANSWER_SYSTEM = (
    "Voce e um assistente clinico de hospital maternidade. Responde a medicos em registro tecnico. "
    "Apoia a decisao clinica; nao a substitui. Nunca prescreva medicamento, dose ou conduta final. "
    "Responda de forma direta e curta (2 a 4 frases). "
    "Use somente fatos presentes no contexto recuperado; nao acrescente complicacoes, farmacos, "
    "sistemas ou condutas que nao estejam no contexto. "
    "Se a pergunta for sobre exames pendentes, diga claramente se ha ou nao exame pendente e qual. "
    "Cite apenas marcadores [S#] listados no pedido. Nao invente marcadores. "
    "Se o contexto indicar sinais de alarme ou gravidade, oriente avaliacao humana imediata."
)


def _usage_details(message, default_model: str) -> dict[str, str | int | None]:
    metadata = message.response_metadata or {}
    usage = message.usage_metadata or metadata.get("token_usage", {})
    return {
        "model": metadata.get("model_name", default_model),
        "input_tokens": usage.get("input_tokens", usage.get("prompt_tokens")),
        "output_tokens": usage.get("output_tokens", usage.get("completion_tokens")),
        "total_tokens": usage.get("total_tokens"),
    }


def allowed_citation_markers(sources: list[Source]) -> list[str]:
    return [f"[S{index}]" for index in range(1, len(sources) + 1)]


def build_final_answer_user_prompt(
    *,
    question: str,
    context: str,
    sources: list[Source],
    revision_violations: list[str],
    revision_attempt: int,
) -> str:
    markers = allowed_citation_markers(sources)
    marker_list = ", ".join(markers) if markers else "(nenhuma fonte recuperada)"
    revision = ""
    if revision_violations:
        revision = (
            f"\nCorrija estas violacoes na tentativa {revision_attempt}: {revision_violations}. "
            f"Use somente as citacoes permitidas: {marker_list}."
        )
    return (
        "Responda a pergunta de forma objetiva, sem divagar.\n"
        f"Citacoes permitidas (use pelo menos uma se houver fontes): {marker_list}.\n"
        f"Pergunta: {question}\n"
        f"Contexto recuperado (unico material permitido):\n{context}"
        f"{revision}"
    )


def sanitize_generated_answer(answer: str) -> str:
    """Remove artefatos comuns de chat template / thinking vazados na geracao."""
    text = answer.strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"</?think>", "", text, flags=re.IGNORECASE)
    # Mantem so o ultimo turno util se o modelo ecoar papeis.
    for marker in ("\nassistant\n", "\nAssistant\n", "\nASSISTANT\n"):
        if marker in text:
            text = text.split(marker)[-1]
    text = re.sub(r"^(assistant|system|user)\s*\n", "", text, flags=re.IGNORECASE)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def normalize_source_citations(answer: str, sources: list[Source]) -> str:
    """Garante que so restem [S#] validos; se faltar citacao, anexa as fontes recuperadas."""
    markers = allowed_citation_markers(sources)
    text = sanitize_generated_answer(answer)
    if not markers:
        return re.sub(r"\s*\[S\d+\]", "", text).strip()

    def _keep_or_drop(match: re.Match[str]) -> str:
        marker = match.group(0)
        return marker if marker in markers else ""

    cleaned = re.sub(r"\[S\d+\]", _keep_or_drop, text)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r" {2,}", " ", cleaned).strip()
    if not any(marker in cleaned for marker in markers):
        cleaned = f"{cleaned} {' '.join(markers)}".strip()
    return cleaned


class OpenAIGeneralLLM:
    """Adapter sem tools: cada operação retorna somente um schema validado."""
    model_name = "gpt-4.1-mini"

    def __init__(self, api_key: str | None = None):
        try:
            from langchain_openai import ChatOpenAI
            self.client = ChatOpenAI(model=self.model_name, temperature=0, api_key=api_key or os.getenv("OPENAI_API_KEY"))
            self.last_usage: dict[str, str | int | None] | None = None
        except Exception as error:
            raise GeneralLLMUnavailable("Não foi possível configurar o modelo geral") from error

    def _invoke(self, schema, prompt: str):
        try:
            response = self.client.with_structured_output(schema, include_raw=True).invoke(prompt)
            if response["parsing_error"] is not None:
                raise response["parsing_error"]
            raw = response["raw"]
            self.last_usage = _usage_details(raw, self.model_name)
            return response["parsed"]
        except Exception as error:
            raise GeneralLLMUnavailable("Modelo geral indisponível ou resposta inválida") from error

    def interpret(self, *, question: str) -> InterpretationResult:
        return self._invoke(InterpretationResult, f"Extraia intenção, ID candidato e condição candidata. Não invente valores. Pergunta: {question}")

    def analyze(self, *, question: str, context: str, sources: list[Source]) -> AnalysisResult:
        return self._invoke(AnalysisResult, f"Sintetize apenas fatos do contexto delimitado. Cite source_ids fornecidos.\nFontes: {[s.id for s in sources]}\nContexto:\n{context}\nPergunta: {question}")

    def critique(self, *, question: str, answer: str, sources: list[Source], has_individual_context: bool, is_critical: bool) -> CritiqueResult:
        return self._invoke(CritiqueResult, f"Aponte possíveis inconsistências, citações inválidas ou recomendações indevidas. Não aprove nem roteie. Fontes: {[s.id for s in sources]}. Resposta: {answer}")

    def smoke_test(self) -> str:
        self.interpret(question="Pergunta geral sobre puerpério.")
        return self.model_name


class OpenAIFinalAnswerLLM:
    """Provider opcional para validar o fluxo sem carregar o Qwen local."""

    def __init__(self, api_key: str | None = None, model_name: str | None = None):
        self.model_name = model_name or os.getenv("OPENAI_FINAL_MODEL", "gpt-4.1-mini")
        try:
            from langchain_openai import ChatOpenAI
            self.client = ChatOpenAI(model=self.model_name, temperature=0, api_key=api_key or os.getenv("OPENAI_API_KEY"))
            self.last_usage: dict[str, str | int | None] | None = None
        except Exception as error:
            raise FinalAnswerModelUnavailable("Não foi possível configurar o modelo final OpenAI") from error

    def generate(self, *, question: str, context: str, sources: list[Source], revision_violations: list[str], revision_attempt: int) -> str:
        user_prompt = build_final_answer_user_prompt(
            question=question,
            context=context,
            sources=sources,
            revision_violations=revision_violations,
            revision_attempt=revision_attempt,
        )
        prompt = f"{FINAL_ANSWER_SYSTEM}\n\n{user_prompt}"
        try:
            response = self.client.invoke(prompt)
            self.last_usage = _usage_details(response, self.model_name)
            text = response.content if isinstance(response.content, str) else str(response.content)
            return normalize_source_citations(text, sources)
        except Exception as error:
            raise FinalAnswerModelUnavailable("Modelo final OpenAI indisponível ou resposta inválida") from error

    def smoke_test(self) -> str:
        self.generate(question="Teste de disponibilidade.", context="[S1] Fonte sintética.", sources=[], revision_violations=[], revision_attempt=0)
        return self.model_name


class QwenLoraFinalAnswerLLM:
    """Carrega o Qwen multimodal 4-bit usado no treino antes de aplicar o LoRA."""
    def __init__(self, adapter_path: str | None = None, base_model: str | None = None):
        self.adapter_path = adapter_path or os.getenv("QWEN_LORA_ADAPTER_PATH")
        self.base_model = base_model or os.getenv("QWEN_BASE_MODEL", "unsloth/Qwen3.5-4B")
        self.cpu_offload = os.getenv("QWEN_ENABLE_CPU_OFFLOAD", "").lower() in {"1", "true", "yes"}
        self.cpu_offload_max_memory = os.getenv("QWEN_CPU_OFFLOAD_MAX_MEMORY")
        self.max_new_tokens = self._max_new_tokens_from_env()
        self.model = None
        self.tokenizer = None

    @staticmethod
    def _max_new_tokens_from_env() -> int:
        value = os.getenv("QWEN_MAX_NEW_TOKENS", "256")
        try:
            max_new_tokens = int(value)
        except ValueError as error:
            raise FinalAnswerModelUnavailable("QWEN_MAX_NEW_TOKENS deve ser um inteiro positivo") from error
        if max_new_tokens < 1:
            raise FinalAnswerModelUnavailable("QWEN_MAX_NEW_TOKENS deve ser um inteiro positivo")
        return max_new_tokens

    @staticmethod
    def quantization_config(*, cpu_offload: bool = False):
        """Configuração QLoRA compatível com o carregamento 4-bit do treino."""
        import torch
        from transformers import BitsAndBytesConfig

        return BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.float16,
            # Para módulos que o device_map levar à CPU, BitsAndBytes mantém
            # os pesos em FP32. Isso é opt-in porque aumenta RAM e latência.
            llm_int8_enable_fp32_cpu_offload=cpu_offload,
        )

    def load(self) -> None:
        if not self.adapter_path:
            raise FinalAnswerModelUnavailable("QWEN_LORA_ADAPTER_PATH não configurado")
        try:
            from peft import PeftModel
            # O checkpoint LoRA foi salvo sobre Qwen3_5ForConditionalGeneration.
            # AutoModelForCausalLM cria somente o modelo de texto (``model.layers``),
            # enquanto o adapter referencia ``model.language_model.layers``. Usar a
            # auto-classe multimodal preserva essa estrutura e permite aplicar os
            # pesos do adapter aos módulos corretos.
            from transformers import AutoModelForImageTextToText, AutoTokenizer
            # Tokenizer do adapter traz o chat_template alinhado ao treino/demo.
            self.tokenizer = AutoTokenizer.from_pretrained(self.adapter_path)
            model_kwargs = {
                "device_map": "auto",
                "quantization_config": self.quantization_config(cpu_offload=self.cpu_offload),
            }
            # Sem um teto de RAM explícito, Accelerate pode descarregar módulos
            # para disco. PEFT não consegue aplicar este adapter 4-bit a tensores
            # meta que permanecem no disco; para o teste híbrido, use só GPU+CPU.
            if self.cpu_offload and self.cpu_offload_max_memory:
                model_kwargs["max_memory"] = {"cpu": self.cpu_offload_max_memory}

            model = AutoModelForImageTextToText.from_pretrained(
                self.base_model,
                **model_kwargs,
            )
            self.model = PeftModel.from_pretrained(model, self.adapter_path)
            self.model.eval()
        except Exception as error:
            raise FinalAnswerModelUnavailable("Falha ao carregar Qwen3.5-4B com adapter LoRA") from error

    def generate(self, *, question: str, context: str, sources: list[Source], revision_violations: list[str], revision_attempt: int) -> str:
        if self.model is None or self.tokenizer is None:
            self.load()
        user_prompt = build_final_answer_user_prompt(
            question=question,
            context=context,
            sources=sources,
            revision_violations=revision_violations,
            revision_attempt=revision_attempt,
        )
        messages = [
            {"role": "system", "content": FINAL_ANSWER_SYSTEM},
            {"role": "user", "content": user_prompt},
        ]
        try:
            if getattr(self.tokenizer, "chat_template", None):
                prompt = self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                )
            else:
                prompt = f"{FINAL_ANSWER_SYSTEM}\n\n{user_prompt}"
            inputs = self.tokenizer(prompt, return_tensors="pt")
            device = next(self.model.parameters()).device
            inputs = {key: value.to(device) for key, value in inputs.items()}
            output = self.model.generate(**inputs, max_new_tokens=self.max_new_tokens, do_sample=False)
            text = self.tokenizer.decode(
                output[0][inputs["input_ids"].shape[-1] :],
                skip_special_tokens=True,
            ).strip()
            return normalize_source_citations(text, sources)
        except Exception as error:
            raise FinalAnswerModelUnavailable("Falha durante geração com adapter") from error

    def smoke_test(self) -> str:
        self.load()
        return f"{self.base_model} + {self.adapter_path}"
