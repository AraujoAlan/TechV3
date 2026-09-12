import os
from dataclasses import dataclass

from app.contracts.errors import FinalAnswerModelUnavailable, GeneralLLMUnavailable
from app.contracts.models import AnalysisResult, CritiqueResult, InterpretationResult, Source


class OpenAIGeneralLLM:
    """Adapter sem tools: cada operação retorna somente um schema validado."""
    model_name = "gpt-4.1-mini"

    def __init__(self, api_key: str | None = None):
        try:
            from langchain_openai import ChatOpenAI
            self.client = ChatOpenAI(model=self.model_name, temperature=0, api_key=api_key or os.getenv("OPENAI_API_KEY"))
        except Exception as error:
            raise GeneralLLMUnavailable("Não foi possível configurar o modelo geral") from error

    def _invoke(self, schema, prompt: str):
        try:
            return self.client.with_structured_output(schema).invoke(prompt)
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


class QwenLoraFinalAnswerLLM:
    """Carrega explicitamente o adapter LoRA; não possui fallback para modelo-base."""
    def __init__(self, adapter_path: str | None = None, base_model: str | None = None):
        self.adapter_path = adapter_path or os.getenv("QWEN_LORA_ADAPTER_PATH")
        self.base_model = base_model or os.getenv("QWEN_BASE_MODEL", "Qwen/Qwen3.5-4B")
        self.model = None
        self.tokenizer = None

    def load(self) -> None:
        if not self.adapter_path:
            raise FinalAnswerModelUnavailable("QWEN_LORA_ADAPTER_PATH não configurado")
        try:
            import torch
            from peft import PeftModel
            from transformers import AutoModelForCausalLM, AutoTokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(self.base_model)
            model = AutoModelForCausalLM.from_pretrained(self.base_model, device_map="auto", torch_dtype="auto")
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
            output = self.model.generate(**inputs, max_new_tokens=256, do_sample=False)
            return self.tokenizer.decode(output[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True).strip()
        except Exception as error:
            raise FinalAnswerModelUnavailable("Falha durante geração com adapter") from error

    def smoke_test(self) -> str:
        self.load()
        return f"{self.base_model} + {self.adapter_path}"
