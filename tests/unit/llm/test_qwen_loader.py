from app.llm.factory import QwenLoraFinalAnswerLLM


def test_qwen_loader_uses_4bit_qlora_configuration():
    config = QwenLoraFinalAnswerLLM.quantization_config()

    assert config.load_in_4bit is True
    assert config.bnb_4bit_quant_type == "nf4"
    assert config.bnb_4bit_use_double_quant is True


def test_qwen_loader_defaults_to_the_training_base_model(monkeypatch):
    monkeypatch.delenv("QWEN_BASE_MODEL", raising=False)

    loader = QwenLoraFinalAnswerLLM(adapter_path="/tmp/adapter")

    assert loader.base_model == "unsloth/Qwen3.5-4B"
