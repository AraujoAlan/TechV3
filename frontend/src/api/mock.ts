import { createId } from '../lib/id'
import { sleep } from '../lib/time'
import type { ChatRequest, ChatResponse, Source } from './types'

/**
 * Backend falso que devolve o mesmo `ChatResponse` da API real.
 *
 * Mantém a UI utilizável sem o FastAPI. Com `VITE_USE_MOCK=false` o caminho
 * de rede assume o contrato JSON.
 */
export async function mockSendChat(
  request: ChatRequest,
  signal?: AbortSignal,
): Promise<ChatResponse> {
  await sleep(420, signal)
  const scenario = pickScenario(request.question)
  return {
    audit_id: createId('audit'),
    outcome: scenario.outcome,
    answer: scenario.answer,
    sources: scenario.sources,
    alert: scenario.alert,
  }
}

interface Scenario {
  outcome: ChatResponse['outcome']
  answer: string
  sources: Source[]
  alert: ChatResponse['alert']
}

function pickScenario(question: string): Scenario {
  const text = question.toLowerCase()

  if (text.includes('p-999')) {
    return {
      outcome: 'limited',
      answer:
        'Não foi possível fornecer uma resposta clínica segura nesta execução. Procure avaliação de um profissional de saúde.',
      sources: [],
      alert: null,
    }
  }

  if (text.includes('exame') || text.includes('p-042') || text.includes('hipertens')) {
    return {
      outcome: 'completed',
      answer:
        'Com base no prontuário sintético, a paciente P-042 possui exame pendente de avaliação de pressão grave [S1][S2]. ' +
        'Há sinais de alarme no contexto de hipertensão gestacional [S3]. Procure avaliação humana imediata.',
      sources: [
        {
          id: 'record:P-042:v1',
          title: 'Prontuário sintético',
          kind: 'prontuario',
          snippet: 'Gestante sintética com hipertensão gestacional e sinais de alarme documentados.',
        },
        {
          id: 'exam:EX-042-1:v1',
          title: 'Exame sintético',
          kind: 'exame',
          snippet: 'Avaliação de pressão grave pendente',
        },
        {
          id: 'protocol:hipertensao-gestacional:v1',
          title: 'Protocolo sintético',
          kind: 'protocolo',
          snippet: 'Sinais de alarme exigem avaliação humana imediata.',
        },
      ],
      alert: { status: 'simulated_recorded' },
    }
  }

  if (text.includes('protocolo') || text.includes('conduta') || text.includes('puerper')) {
    return {
      outcome: 'completed',
      answer:
        'Segundo o protocolo sintético de acompanhamento no puerpério, a reavaliação clínica periódica é recomendada [S1]. ' +
        'Esta é uma orientação de apoio — a conduta depende da sua avaliação.',
      sources: [
        {
          id: 'protocol:puerperio:v1',
          title: 'Protocolo sintético',
          kind: 'protocolo',
          snippet: 'Protocolo sintético de acompanhamento no puerpério.',
        },
      ],
      alert: null,
    }
  }

  return {
    outcome: 'limited',
    answer:
      'Não foi possível fornecer uma resposta clínica segura nesta execução. Procure avaliação de um profissional de saúde.',
    sources: [],
    alert: null,
  }
}
