from types import SimpleNamespace

from app.llm.factory import OpenAIGeneralLLM


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
