import { createId } from '../lib/id'
import { sleep } from '../lib/time'
import type { ChatRequest, Source, StreamEvent } from './types'

/**
 * Backend falso que emite exatamente os mesmos `StreamEvent` do FastAPI real.
 *
 * Serve para desenvolver a UI e gravar a demo antes da API existir. Quando o
 * backend subir, basta `VITE_USE_MOCK=false` — nenhum componente muda.
 */
export async function* mockStreamChat(
  request: ChatRequest,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent> {
  const question = request.messages.at(-1)?.content ?? ''
  const scenario = pickScenario(question)

  await sleep(280, signal)

  for (const tool of scenario.tools) {
    const toolId = createId('tool')
    yield { type: 'tool_start', id: toolId, name: tool.name, input: tool.input }
    await sleep(520, signal)
    yield { type: 'tool_end', id: toolId, output: tool.output }
    await sleep(180, signal)
  }

  // Emite palavra a palavra para reproduzir a sensação do token streaming.
  for (const chunk of chunkText(scenario.answer)) {
    yield { type: 'token', content: chunk }
    await sleep(18, signal)
  }

  if (scenario.sources.length > 0) {
    yield { type: 'sources', sources: scenario.sources }
  }

  yield { type: 'done', messageId: createId('msg'), conversationId: request.conversationId }
}

interface Scenario {
  tools: Array<{ name: string; input: Record<string, unknown>; output: string }>
  answer: string
  sources: Source[]
}

/** Escolhe a resposta pelas palavras-chave, espelhando as tools do `main.py`. */
function pickScenario(question: string): Scenario {
  const text = question.toLowerCase()
  const patientId = question.match(/\b\d{4,}\b/)?.[0] ?? '12345'

  if (text.includes('exame')) {
    return {
      tools: [
        {
          name: 'verificar_exames_pendentes',
          input: { paciente_id: patientId },
          output: '2 exames pendentes: Hemoglobina glicada (solicitado 12/03), Ultrassom transvaginal (solicitado 20/03).',
        },
      ],
      answer:
        `A paciente ${patientId} tem **2 exames pendentes**:\n\n` +
        '1. Hemoglobina glicada — solicitado em 12/03, sem coleta registrada.\n' +
        '2. Ultrassom transvaginal — solicitado em 20/03, sem agendamento.\n\n' +
        'O ultrassom está pendente há mais tempo que o previsto no protocolo de acompanhamento. ' +
        'Vale confirmar o agendamento antes da próxima consulta.',
      sources: [
        {
          id: createId('src'),
          title: `Prontuário ${patientId} — Solicitações`,
          kind: 'exame',
          snippet: 'Hemoglobina glicada (12/03) · Ultrassom transvaginal (20/03) — ambos sem resultado.',
        },
      ],
    }
  }

  if (text.includes('protocolo') || text.includes('conduta') || text.includes('tratamento')) {
    return {
      tools: [
        {
          name: 'consultar_protocolo',
          input: { condicao: extractCondition(text) },
          output: 'Protocolo interno v2.1 localizado — 4 etapas de conduta.',
        },
      ],
      answer:
        'Segundo o protocolo interno do hospital, a conduta se organiza em quatro etapas:\n\n' +
        '1. **Confirmação diagnóstica** com exame clínico e laboratorial.\n' +
        '2. **Estratificação de risco** conforme idade, histórico e comorbidades.\n' +
        '3. **Conduta inicial** de acordo com a faixa de risco identificada.\n' +
        '4. **Reavaliação** em 30 dias, com ajuste conforme resposta.\n\n' +
        '⚠️ Esta é uma orientação baseada em protocolo. A prescrição depende da sua avaliação clínica.',
      sources: [
        {
          id: createId('src'),
          title: 'Protocolo Interno — Ginecologia v2.1',
          kind: 'protocolo',
          snippet: 'Seção 3: estratificação de risco e conduta inicial por faixa.',
        },
      ],
    }
  }

  if (text.includes('prontuário') || text.includes('prontuario') || text.includes('paciente')) {
    return {
      tools: [
        {
          name: 'buscar_prontuario',
          input: { paciente_id: patientId },
          output: 'Prontuário encontrado: 34 anos, G2P1A0, sem alergias registradas.',
        },
        {
          name: 'verificar_exames_pendentes',
          input: { paciente_id: patientId },
          output: '2 exames pendentes.',
        },
      ],
      answer:
        `**Paciente ${patientId}** — 34 anos, G2P1A0, sem alergias registradas.\n\n` +
        '**Histórico recente:** acompanhamento de rotina, última consulta em 08/02. ' +
        'Queixa registrada de ciclo irregular nos últimos três meses.\n\n' +
        '**Pendências:** 2 exames solicitados e ainda sem resultado.\n\n' +
        'Quer que eu detalhe os exames pendentes ou o protocolo de investigação para ciclo irregular?',
      sources: [
        {
          id: createId('src'),
          title: `Prontuário Eletrônico ${patientId}`,
          kind: 'prontuario',
          snippet: 'Última atualização em 08/02 — consulta de rotina.',
        },
      ],
    }
  }

  return {
    tools: [],
    answer:
      'Consigo ajudar com consulta a prontuários, exames pendentes e protocolos internos do hospital.\n\n' +
      'Você pode perguntar, por exemplo:\n\n' +
      '• "Mostre o prontuário da paciente 12345"\n' +
      '• "Quais exames estão pendentes para a 12345?"\n' +
      '• "Qual o protocolo para ciclo irregular?"\n\n' +
      'Lembrando que sou um apoio à decisão — não substituo sua avaliação clínica.',
    sources: [],
  }
}

/** Heurística boba, só para o mock devolver um input de tool plausível. */
function extractCondition(text: string): string {
  const known = ['hipertensão', 'diabetes', 'ciclo irregular', 'endometriose', 'gestação']
  return known.find((condition) => text.includes(condition)) ?? 'consulta geral'
}

/** Quebra o texto preservando os espaços, para o stream não colar as palavras. */
function chunkText(text: string): string[] {
  return text.match(/\S+\s*/g) ?? []
}
