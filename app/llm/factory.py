import os
from dataclasses import dataclass

from app.contracts.errors import FinalAnswerModelUnavailable, GeneralLLMUnavailable
from app.contracts.models import AnalysisResult, CritiqueResult, InterpretationResult, Source


def _usage_details(message, default_model: str) -> dict[str, str | int | None]:
    metadata = message.response_metadata or {}
    usage = message.usage_metadata or metadata.get("token_usage", {})
    return {
        "model": metadata.get("model_name", default_model),
        "input_tokens": usage.get("input_tokens", usage.get("prompt_tokens")),
        "output_tokens": usage.get("output_tokens", usage.get("completion_tokens")),
        "total_tokens": usage.get("total_tokens"),
    }


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
        prompt = (
            "Responda somente com base nos fatos e fontes fornecidos. Não prescreva. "
            "Inclua pelo menos uma citação [S#] existente para cada fato clínico. "
            "Se o contexto indicar gravidade ou sinais de alarme, oriente busca imediata de avaliação humana.\n"
            f"Pergunta: {question}\nContexto:\n{context}\n"
            f"Violações a corrigir na tentativa {revision_attempt}: {revision_violations}"
        )
        try:
            response = self.client.invoke(prompt)
            self.last_usage = _usage_details(response, self.model_name)
            return response.content if isinstance(response.content, str) else str(response.content)
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
            self.tokenizer = AutoTokenizer.from_pretrained(self.base_model)
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
        if self.model is None or self.tokenizer is None: self.load()
        prompt = f"Responda somente com base nos fatos e fontes. Não prescreva. Cite [S#].\nPergunta: {question}\nContexto:\n{context}\nViolações a corrigir: {revision_violations}"
        try:
            import torch
            inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
            output = self.model.generate(**inputs, max_new_tokens=self.max_new_tokens, do_sample=False)
            return self.tokenizer.decode(output[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True).strip()
        except Exception as error:
            raise FinalAnswerModelUnavailable("Falha durante geração com adapter") from error

    def smoke_test(self) -> str:
        self.load()
        return f"{self.base_model} + {self.adapter_path}"
