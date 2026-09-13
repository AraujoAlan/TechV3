from types import SimpleNamespace

from app.llm.factory import OpenAIFinalAnswerLLM, OpenAIGeneralLLM


class StructuredOutput:
    def invoke(self, prompt):
        return {
            "raw": SimpleNamespace(
                usage_metadata={"input_tokens": 12, "output_tokens": 8, "total_tokens": 20},
                response_metadata={"model_name": "gpt-4.1-mini"},
            ),
            "parsed": "parsed-result",
            "parsing_error": None,
        }


class Client:
    def with_structured_output(self, schema, *, include_raw):
        assert include_raw is True
        return StructuredOutput()


def test_openai_general_llm_keeps_token_usage_from_raw_response():
    llm = OpenAIGeneralLLM.__new__(OpenAIGeneralLLM)
    llm.client = Client()
    llm.model_name = "gpt-4.1-mini"

    result = llm._invoke(object, "prompt")

    assert result == "parsed-result"
    assert llm.last_usage == {
        "model": "gpt-4.1-mini",
        "input_tokens": 12,
        "output_tokens": 8,
        "total_tokens": 20,
    }


class TextClient:
    def invoke(self, prompt):
        return SimpleNamespace(
            content="Resposta [S1].",
            usage_metadata={"input_tokens": 10, "output_tokens": 4, "total_tokens": 14},
            response_metadata={"model_name": "gpt-4.1-mini"},
        )


def test_openai_final_answer_llm_returns_text_and_usage():
    llm = OpenAIFinalAnswerLLM.__new__(OpenAIFinalAnswerLLM)
    llm.client = TextClient()
    llm.model_name = "gpt-4.1-mini"

    result = llm.generate(question="Pergunta", context="[S1] Fonte.", sources=[], revision_violations=[], revision_attempt=0)

    assert result == "Resposta [S1]."
    assert llm.last_usage["total_tokens"] == 14
