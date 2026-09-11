"""
Script para testar carregamento do modelo fine-tuned isoladamente.
"""

import sys
import io

# Configurar encoding UTF-8 no Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

print("="*70)
print("🧪 TESTE DE CARREGAMENTO DO MODELO FINE-TUNED")
print("="*70)

print("\n1️⃣  Testando imports do HuggingFace...")
try:
    from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
    import torch
    print("   ✅ Imports OK")
except Exception as e:
    print(f"   ❌ Erro nos imports: {e}")
    print("\n💡 Solução:")
    print("   pip install transformers torch accelerate --upgrade")
    sys.exit(1)

print("\n2️⃣  Verificando disponibilidade de GPU/CPU...")
if torch.cuda.is_available():
    print(f"   ✅ GPU disponível: {torch.cuda.get_device_name(0)}")
    print(f"   💾 VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
    device = "cuda"
else:
    print("   ⚠️  GPU não disponível - usando CPU")
    print("   ⏱️  Carregamento será mais lento (~5-10 min)")
    device = "cpu"

print("\n3️⃣  Tentando carregar modelo do HuggingFace...")
print("   📦 Modelo: emidiosouza/assistente-maternidade")
print("   ⏳ Aguarde... (primeira vez pode demorar ~5 min)\n")

try:
    model_id = "emidiosouza/assistente-maternidade"

    print("   [1/3] Carregando tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    print("   ✅ Tokenizer carregado")

    print("   [2/3] Carregando modelo...")
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        device_map="auto",
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        low_cpu_mem_usage=True
    )
    print("   ✅ Modelo carregado")

    print("   [3/3] Criando pipeline...")
    pipe = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
        max_new_tokens=128,  # Reduzido para teste rápido
        temperature=0.3,
        do_sample=True
    )
    print("   ✅ Pipeline criado")

except Exception as e:
    print(f"\n   ❌ ERRO ao carregar modelo: {e}")
    print("\n📊 Diagnóstico:")
    import traceback
    traceback.print_exc()

    print("\n💡 Possíveis soluções:")
    print("   1. Memória insuficiente:")
    print("      - Feche outros programas")
    print("      - Modelo precisa de ~8GB RAM")
    print("   2. Problema de conexão:")
    print("      - Verifique internet")
    print("      - Modelo será baixado do HuggingFace (~2GB)")
    print("   3. Usar Ollama em vez disso:")
    print("      - python main.py  (sem --finetuned)")
    sys.exit(1)

print("\n4️⃣  Testando geração de texto...")
try:
    test_prompt = "Teste de funcionamento do modelo."
    print(f"   💬 Prompt: {test_prompt}")

    result = pipe(test_prompt)
    generated = result[0]['generated_text']

    print(f"   ✅ Geração OK")
    print(f"   📝 Texto gerado: {generated[:100]}...")

except Exception as e:
    print(f"   ❌ Erro na geração: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*70)
print("✅ MODELO FINE-TUNED FUNCIONANDO PERFEITAMENTE!")
print("="*70)
print("\n🎬 Pode executar:")
print("   python main.py --finetuned")
print("\n")
