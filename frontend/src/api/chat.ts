import { ENDPOINTS, USE_MOCK } from './config'
import { ApiError } from './errors'
import { mockStreamChat } from './mock'
import { readEventStream } from './sse'
import type { ChatRequest, StreamEvent } from './types'

/**
 * Envia o histórico para o assistente e devolve os eventos do stream.
 *
 * Enquanto o backend HTTP não existir, `VITE_USE_MOCK` mantém a UI viva com
 * o mock local — a assinatura é a mesma, então plugar o real não muda nada
 * acima desta função.
 */
export async function* streamChat(
  request: ChatRequest,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent> {
  if (USE_MOCK) {
    yield* mockStreamChat(request, signal)
    return
  }

  const response = await fetch(ENDPOINTS.chat, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(request),
    signal,
  })

  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status)
  }
  if (!response.body) {
    throw new ApiError('O servidor respondeu sem corpo de stream.', response.status)
  }

  for await (const data of readEventStream(response.body, signal)) {
    // Sentinela opcional, usada por alguns servidores SSE para fechar o turno.
    if (data === '[DONE]') return

    const event = parseEvent(data)
    if (event) yield event
  }
}

/** Descarta payloads malformados em vez de derrubar a conversa inteira. */
function parseEvent(data: string): StreamEvent | null {
  try {
    const parsed: unknown = JSON.parse(data)
    if (parsed && typeof parsed === 'object' && 'type' in parsed) {
      return parsed as StreamEvent
    }
  } catch {
    // Ignora: um evento corrompido não deve interromper o stream.
  }
  return null
}

/** Extrai a mensagem de erro do backend, com fallback no status HTTP. */
async function describeFailure(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (body && typeof body === 'object') {
      const detail = (body as Record<string, unknown>).detail ?? (body as Record<string, unknown>).message
      if (typeof detail === 'string' && detail.length > 0) return detail
    }
  } catch {
    // Corpo não era JSON.
  }
  return `A API respondeu ${response.status} ${response.statusText}.`
}
