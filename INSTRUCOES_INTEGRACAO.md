# 📋 Instruções de Integração - Modelo Fine-Tuned

## Como Integrar o Modelo Fine-Tuned da Etapa 1

Após concluir o fine-tuning do modelo com os dados médicos do hospital (Etapa 1), siga os passos abaixo para integrar com este sistema LangChain.

---

## 🔧 Opções de Integração

### Opção 1: Modelo Local via Ollama (Recomendado)

**Quando usar**: Se você fez fine-tuning de LLaMA, Falcon ou similar e quer rodar localmente.

#### Passos:

1. **Instale o Ollama**
   ```bash
   # Baixe de https://ollama.ai
   ```

2. **Importe seu modelo fine-tuned**
   ```bash
   # Crie um Modelfile
   echo 'FROM ./seu-modelo-finetuned.gguf' > Modelfile

   # Importe para o Ollama
   ollama create assistente-medico -f Modelfile
   ```

3. **Modifique o arquivo `main.py`**

   Localize a função `criar_llm_finetuned()` (linha ~42) e substitua por:

   ```python
   def criar_llm_finetuned():
       from langchain_community.llms import Ollama
       return Ollama(
           model="assistente-medico",  # Nome do modelo que você criou
           temperature=0.3
       )
   ```

4. **Instale dependências**
   ```bash
   pip install langchain-community
   ```

---

### Opção 2: Modelo via HuggingFace

**Quando usar**: Se seu modelo está no HuggingFace Hub ou local em formato HuggingFace.

#### Passos:

1. **Instale dependências**
   ```bash
   pip install transformers torch accelerate
   ```

2. **Modifique o arquivo `main.py`**

   Localize a função `criar_llm_finetuned()` e substitua por:

   ```python
   def criar_llm_finetuned():
       from langchain_community.llms import HuggingFacePipeline
       from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline

       # Caminho para seu modelo (local ou HuggingFace Hub)
       model_id = "seu-usuario/llama2-medical-finetuned"  # ou caminho local

       tokenizer = AutoTokenizer.from_pretrained(model_id)
       model = AutoModelForCausalLM.from_pretrained(
           model_id,
           device_map="auto",  # Distribui automaticamente entre CPU/GPU
           torch_dtype="auto"
       )

       pipe = pipeline(
           "text-generation",
           model=model,
           tokenizer=tokenizer,
           max_new_tokens=512,
           temperature=0.3,
           do_sample=True
       )

       return HuggingFacePipeline(pipeline=pipe)
   ```

---

### Opção 3: API Customizada

**Quando usar**: Se você criou sua própria API para servir o modelo fine-tuned.

#### Passos:

1. **Certifique-se que sua API está rodando**
   ```bash
   # Exemplo: sua API em http://localhost:5000
   ```

2. **Modifique o arquivo `main.py`**

   Localize a função `criar_llm_finetuned()` e substitua por:

   ```python
   def criar_llm_finetuned():
       from langchain_community.llms import TextGen
       return TextGen(
           model_url="http://localhost:5000/api/generate",
           temperature=0.3
       )
   ```

   Ou crie um wrapper customizado:

   ```python
   from langchain.llms.base import LLM
   from typing import Optional, List
   import requests

   class CustomMedicalLLM(LLM):
       api_url: str = "http://localhost:5000/api/generate"

       @property
       def _llm_type(self) -> str:
           return "custom_medical"

       def _call(self, prompt: str, stop: Optional[List[str]] = None) -> str:
           response = requests.post(
               self.api_url,
               json={"prompt": prompt, "temperature": 0.3, "max_tokens": 512}
           )
           return response.json()["text"]

   def criar_llm_finetuned():
       return CustomMedicalLLM()
   ```

---

## 🧪 Testando a Integração

Após modificar o código conforme uma das opções acima:

1. **Instale as dependências**
   ```bash
   pip install -r requirements.txt
   ```

2. **Teste o modelo**
   ```bash
   python main.py
   ```

3. **Faça uma pergunta simples**
   ```
   Médico: Qual o protocolo para hipertensão?
   ```

4. **Verifique se o modelo responde corretamente**

---

## 📊 Comparação das Opções

| Característica | Ollama | HuggingFace | API Customizada |
|----------------|--------|-------------|-----------------|
| **Facilidade** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Performance** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Flexibilidade** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Custo** | Grátis | Grátis | Depende |

---

## 🔍 Verificação da Integração

Para verificar se o modelo fine-tuned está sendo usado corretamente:

1. **Faça perguntas específicas** dos protocolos do hospital que você usou no fine-tuning
2. **Compare as respostas** com o que você esperaria do modelo treinado
3. **Verifique os logs** - o LangChain mostra qual modelo está sendo usado

---

## ⚠️ Troubleshooting

### Erro: "Model not found"
- Verifique se o caminho/nome do modelo está correto
- Certifique-se que o modelo foi carregado corretamente

### Erro: "Out of memory"
- Reduza o tamanho do contexto (`max_new_tokens`)
- Use quantização (ex: modelos `.gguf` de 4-bit)
- Configure `device_map="auto"` no HuggingFace

### Respostas genéricas (não parecem do fine-tuning)
- Verifique se o modelo certo está sendo carregado
- Ajuste a `temperature` (valores mais baixos = mais determinístico)
- Revise os prompts do sistema

---

## 📝 Próximos Passos

1. ✅ Integre o modelo fine-tuned usando uma das opções acima
2. ✅ Teste com casos reais do hospital
3. ✅ Ajuste os prompts do sistema conforme necessário
4. ✅ Adicione mais ferramentas (tools) se necessário
5. ✅ Conecte com banco de dados real do hospital

---

## 💡 Dicas Importantes

- **Sempre teste** o modelo standalone antes de integrar com LangChain
- **Documente** qual versão do modelo está usando
- **Mantenha backups** das configurações que funcionam
- **Monitore** a qualidade das respostas após integração
