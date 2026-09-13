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


def test_qwen_loader_uses_multimodal_auto_model_for_lora_checkpoint(monkeypatch):
    import peft
    import transformers

    calls = {}

    class LoadedModel:
        def eval(self):
            calls["eval_called"] = True

    def load_base_model(*args, **kwargs):
        calls["base_model"] = args[0]
        calls["base_kwargs"] = kwargs
        return object()

    def load_adapter(base_model, adapter_path):
        calls["adapter_base_model"] = base_model
        calls["adapter_path"] = adapter_path
        return LoadedModel()

    monkeypatch.setattr(
        transformers.AutoTokenizer,
        "from_pretrained",
        staticmethod(lambda model_id: f"tokenizer:{model_id}"),
    )
    monkeypatch.setattr(
        transformers.AutoModelForImageTextToText,
        "from_pretrained",
        staticmethod(load_base_model),
    )
    monkeypatch.setattr(peft.PeftModel, "from_pretrained", staticmethod(load_adapter))

    loader = QwenLoraFinalAnswerLLM(adapter_path="/tmp/adapter", base_model="Qwen/Qwen3.5-4B")
    loader.load()

    assert calls["base_model"] == "Qwen/Qwen3.5-4B"
    assert calls["adapter_path"] == "/tmp/adapter"
    assert calls["eval_called"] is True
