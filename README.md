# Assistente Clínico Materno-Infantil

Assistente que apoia profissionais de saúde de um hospital maternidade, sobre um
banco de 10 mil prontuários sintéticos derivados do SIH/SUS. Responde em registro
médico-a-médico com um modelo Qwen3.5-4B ajustado por fine-tuning, consulta o
banco por SQL, aciona a equipe quando o caso é crítico e deixa rastro auditável
de cada turno.

Tech Challenge — Fase 3.

---

## Começar

Você precisa de **Docker** e de **uma chave da z.ai** (o modelo que decide quais
consultas fazer). Nada mais: Python, CUDA e o modelo fine-tunado vêm nos
containers.

```bash
cp .env.example .env        # e coloque sua Z_API_KEY
docker compose up --build
```

Abra **http://localhost:8000**. A interface e a API saem da mesma origem.

> **Na primeira subida** o llama-server baixa ~2,8 GB do modelo GGUF. São alguns
> minutos, e a interface já abre antes disso — perguntar cedo devolve um aviso
> explicado, não um erro cru. O download fica num volume; da segunda vez em
> diante a subida é imediata.

---

## Escolha como rodar

O único serviço sensível a hardware é o `modelo`. Escolha a linha da sua máquina:

| Sua máquina | Comando | O que esperar |
|---|---|---|
| **GPU NVIDIA, 6 GB+** | `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build` | Melhor experiência. ~3 GB de VRAM, geração a ~63 tokens/s |
| **GPU NVIDIA, 4 GB** | idem, mas veja *GPU pequena* abaixo | Funciona com parte das camadas na GPU |
| **Sem GPU** | `docker compose up --build` | Funciona. Respostas longas levam ~1–2 min |
| **Já tem o GGUF em disco** | acrescente `-f docker-compose.local.yml` | Pula os 2,8 GB de download |

Os overrides combinam:

```bash
docker compose -f docker-compose.yml \
               -f docker-compose.local.yml \
               -f docker-compose.gpu.yml up --build
```

### Quanto a GPU ajuda, de verdade

Medido nesta implementação, numa RTX 4060 Laptop:

| Pergunta | CPU | GPU |
|---|---|---|
| Clínica pura, sem consulta ao banco | 15,4 s | 16,6 s |
| Com consulta ao banco (6 ferramentas) | 53,0 s | 34,5 s |

A pergunta simples **não fica mais rápida**, e isso não é defeito: boa parte do
tempo de um turno é a ida ao roteador na nuvem, que a GPU não encurta. Ela acelera
a redação da resposta — que é onde o ganho aparece nos turnos longos.

Ou seja: **rodar sem GPU é perfeitamente viável** para demonstrar o trabalho.

### GPU pequena (4 GB, como uma RTX 2050)

O modelo em Q4_K_M ocupa ~3 GB, e com o contexto de 8k a placa de 4 GB fica no
limite. Em vez de `--n-gpu-layers 999`, coloque um número menor no
`docker-compose.gpu.yml` — comece em `20` e suba até a VRAM encher:

```yaml
command: >
  ...
  --n-gpu-layers 20
```

As camadas restantes ficam na CPU. É mais lento que a GPU inteira, e bem mais
rápido que só CPU.

---

## Configuração

Só uma variável é obrigatória:

| Variável | Para quê |
|---|---|
| `Z_API_KEY` | Chave da z.ai, do modelo que decide quais consultas fazer |

O resto tem padrão que funciona — veja `.env.example`. Duas que talvez você queira
mexer:

| Variável | Padrão | Efeito |
|---|---|---|
| `MAX_LINHAS_CONSULTA` | `20` | Teto de linhas por consulta ao banco |
| `MAX_REVISOES` | `0` | Reescritas permitidas quando a validação reprova. Acima de zero, a resposta deixa de aparecer letra a letra: ela só vai à tela depois de aprovada |

---

## Experimente

Cada pergunta abaixo exercita um caminho diferente do fluxo:

```
o que é pré-eclâmpsia?
```
Nenhuma ferramenta é chamada. O modelo fine-tunado responde direto — o assistente
não consulta o banco quando a pergunta não depende dele.

```
resuma o prontuário do PAC00000001
```
Busca o prontuário, e a resposta vem com a fonte citada na interface.

```
quais os diagnósticos mais frequentes em obstetrícia?
```
O roteador confere o esquema do banco e escreve o SQL sobre as 10 mil linhas.

```
avalie o caso do PAC00000029
```
**Caso crítico.** A regra determinística classifica (pré-eclâmpsia, CID O14), um
alerta é registrado antes da resposta, e o texto sai com orientação de acionar a
equipe.

Outros pacientes que disparam alerta, um por regra:

| Paciente | Regra | Motivo |
|---|---|---|
| `PAC00000029` | `MAT-OBS-001` | Emergência hipertensiva (CID O14) |
| `PAC00002456` | `MAT-OBS-002` | Hemorragia pós-parto (CID O72) |
| `PAC00000003` | `MAT-OBS-003` | Gestação de alto risco |
| `PAC00000368` | `MAT-PED-001` | Asfixia perinatal (CID P21) |
| `PAC00000151` | `MAT-PED-002` | Infecção neonatal (CID P36) |
| `PAC00000064` | `MAT-GIN-001` | Sangramento com dor pélvica intensa |

---

## Como funciona

Dois modelos, cada um no que treinou:

- **Roteador** (`glm-5.3-flash`, na nuvem) decide quais consultas fazer e escreve
  o SQL. Modelo generalista grande sabe montar chamada de ferramenta com
  argumento correto.
- **Redator** (Qwen3.5-4B + LoRA, local) escreve a resposta ao médico. Foi
  ajustado em pares pergunta-resposta clínicos, sem nenhum exemplo de tool
  calling — pedir que ele escolhesse ferramentas seria usá-lo fora do que
  aprendeu.

Em volta deles, um `StateGraph` que garante o que não pode depender de o modelo
ter lembrado:

```
inicializar → identificar → recuperar → coletar → criticidade → [alerta]
   → gerar → escalonamento → validar → fim
                    ↓ (qualquer falha de serviço)
                limitacao
```

- **`recuperar`** é o roteador com as 7 ferramentas. É o único nó probabilístico.
- **`criticidade`** avalia por regra sobre o registro estruturado do paciente,
  com código e versão de regra. Nunca por LLM.
- **`alerta`** dispara sozinho quando a regra acusa — não depende de o modelo
  pedir.
- **`escalonamento`** garante que todo caso crítico oriente acionar a equipe.
- **`validar`** barra resposta vazia, caso crítico sem escalonamento e protocolo
  citado sem consulta.
- **`limitacao`** é a saída segura: qualquer falha de serviço vira uma resposta
  honesta, nunca uma bolha vazia.

---

## Onde ficam as evidências

Duas trilhas em JSONL, `logs/auditoria.jsonl` e `logs/alertas.jsonl`, montadas
para serem lidas sem subir infraestrutura nenhuma:

```bash
# O caminho percorrido no grafo, nó a nó, no último turno
python3 -c "
import json
d=[json.loads(l) for l in open('logs/auditoria.jsonl')][-1]
print(d['pergunta'], '->', d['duracao_s'], 's')
for e in d['eventos']: print(' ', e['no'], e['evento'], e.get('detalhes',''))"

# Os alertas emitidos, com a regra que disparou cada um
python3 -c "
import json
for l in open('logs/alertas.jsonl'):
    d=json.loads(l)
    print(d['id'], d['codigo_regra'], d['origem'], d['validado_por_humano'])"
```

Com `jq` instalado, `jq -c '.eventos[]' logs/auditoria.jsonl` dá o mesmo.

Cada turno vira uma linha com pergunta, ferramentas chamadas, fontes, resposta,
criticidade, violações, latência e os eventos por nó. Se uma conduta for
questionada depois, dá para reconstruir o turno sem reexecutá-lo.

Todo alerta nasce com `validado_por_humano: false`. Ele é sugestão do assistente
até alguém da equipe confirmar — registrar isso é o que impede que seja lido
depois como decisão clínica tomada.

---

## Testes

```bash
uv sync                 # inclui o grupo dev
uv run pytest -q
```

Cobrem o acesso somente-leitura ao banco, as regras de criticidade, os limites de
atuação e as garantias do grafo com os modelos substituídos por dublês — o que
está sob teste são justamente as garantias que não dependem do modelo ter
acertado.

---

## Fine-tuning

Os notebooks `04`–`07` preparam o dataset, treinam o adapter LoRA, avaliam contra
o modelo base e montam o banco. As dependências de treino não são instaladas por
padrão, para não levarem torch e CUDA para dentro da imagem da API:

```bash
uv sync --group treino
```

O adapter treinado é publicado em GGUF e é o que o compose baixa.

---

## Problemas comuns

**A interface abre mas toda pergunta demora muito.** Provavelmente o modelo ainda
está baixando. Confira com `docker compose logs -f modelo`.

**`Z_API_KEY` não definida.** O compose recusa subir sem ela. Confira que o `.env`
existe e que a linha não tem espaço antes do `=`.

**Quer conferir se está mesmo na GPU.**

```bash
docker compose ps modelo    # a imagem deve terminar em -cuda
nvidia-smi                  # ~3 GB em uso pelo processo do llama-server
```

**A resposta não cita o número que você esperava.** O redator parafraseia o que a
ferramenta trouxe. O dado exato da consulta está no artefato registrado em
`logs/auditoria.jsonl` — é lá que se confere a procedência.

---

## Limites

Os prontuários são **sintéticos**, derivados de dados agregados e públicos do
SIH/SUS: não há dado pessoal real. Os protocolos internos são fictícios, escritos
para este trabalho.

O assistente **apoia** a decisão clínica e não a substitui. Ele não prescreve como
determinação final, e o alerta à equipe é simulado — num hospital real, chamaria o
sistema de notificação de plantão. O que o trabalho demonstra é o gatilho e o
rastro.
