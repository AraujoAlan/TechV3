import { useCallback, useRef, useState } from 'react'
import { streamChat, toUserMessage } from '../api'
import type { Message, StreamEvent, ToolCall } from '../api'
import { createId } from '../lib/id'

export type ChatStatus = 'idle' | 'streaming'

export interface UseChatResult {
  messages: Message[]
  status: ChatStatus
  error: string | null
  send: (content: string) => void
  stop: () => void
  reset: () => void
}

/**
 * Orquestra a conversa: mantém o histórico, consome o stream da API e
 * traduz cada `StreamEvent` em atualização de estado.
 *
 * É a única ponte entre `api/` e `ui/` — os componentes só recebem dados
 * prontos e callbacks.
 */
export function useChat(): UseChatResult {
  const [messages, setMessages] = useState<Message[]>([])
  const [status, setStatus] = useState<ChatStatus>('idle')
  const [error, setError] = useState<string | null>(null)

  const abortRef = useRef<AbortController | null>(null)
  const conversationRef = useRef<string>(createId('conv'))
  // Espelho do histórico, legível de forma síncrona. `send` precisa montar o
  // corpo da requisição no mesmo tick em que é chamado, e o estado do React só
  // fica disponível no render seguinte.
  const historicoRef = useRef<Message[]>([])

  /** Aplica uma alteração na mensagem do assistente que está sendo montada. */
  const patchAssistant = useCallback((id: string, patch: (draft: Message) => Message) => {
    // O ref acompanha o estado para que o próximo turno mande a resposta que o
    // assistente realmente deu, e não a bolha vazia em que ela começou.
    historicoRef.current = historicoRef.current.map((message) =>
      message.id === id ? patch(message) : message,
    )
    setMessages((current) =>
      current.map((message) => (message.id === id ? patch(message) : message)),
    )
  }, [])

  const send = useCallback(
    (content: string) => {
      const text = content.trim()
      if (text.length === 0 || abortRef.current) return

      setError(null)

      const userMessage: Message = {
        id: createId('msg'),
        role: 'user',
        content: text,
        createdAt: Date.now(),
      }
      const assistantId = createId('msg')
      const assistantMessage: Message = {
        id: assistantId,
        role: 'assistant',
        content: '',
        createdAt: Date.now(),
        streaming: true,
      }

      // O histórico enviado à API é o que existia + a pergunta nova.
      //
      // Sai do ref, e não do updater do `setMessages`: o updater só roda no
      // render seguinte, então ler o histórico de dentro dele devolvia lista
      // vazia para a requisição que parte agora — e a API recusa um corpo sem
      // nenhuma mensagem.
      const anteriores = historicoRef.current
      const history = [...anteriores, userMessage].map(({ role, content: body }) => ({
        role,
        content: body,
      }))

      historicoRef.current = [...anteriores, userMessage, assistantMessage]
      setMessages((current) => [...current, userMessage, assistantMessage])

      const controller = new AbortController()
      abortRef.current = controller
      setStatus('streaming')

      void (async () => {
        try {
          const stream = streamChat(
            { messages: history, conversationId: conversationRef.current },
            controller.signal,
          )

          for await (const event of stream) {
            applyEvent(event, assistantId, patchAssistant, conversationRef)
          }
        } catch (cause) {
          const message = toUserMessage(cause)
          const aborted = controller.signal.aborted

          if (!aborted) setError(message)
          patchAssistant(assistantId, (draft) => ({
            ...draft,
            error: aborted ? undefined : message,
          }))
        } finally {
          patchAssistant(assistantId, (draft) => ({ ...draft, streaming: false }))
          abortRef.current = null
          setStatus('idle')
        }
      })()
    },
    [patchAssistant],
  )

  const stop = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  const reset = useCallback(() => {
    abortRef.current?.abort()
    conversationRef.current = createId('conv')
    historicoRef.current = []
    setMessages([])
    setError(null)
    setStatus('idle')
  }, [])

  return { messages, status, error, send, stop, reset }
}

/** Traduz um evento do stream na mutação correspondente da mensagem. */
function applyEvent(
  event: StreamEvent,
  assistantId: string,
  patch: (id: string, fn: (draft: Message) => Message) => void,
  conversation: { current: string },
): void {
  switch (event.type) {
    case 'token':
      patch(assistantId, (draft) => ({ ...draft, content: draft.content + event.content }))
      break

    case 'tool_start': {
      const call: ToolCall = {
        id: event.id,
        name: event.name,
        input: event.input,
        status: 'running',
      }
      patch(assistantId, (draft) => ({
        ...draft,
        toolCalls: [...(draft.toolCalls ?? []), call],
      }))
      break
    }

    case 'tool_end':
      patch(assistantId, (draft) => ({
        ...draft,
        toolCalls: draft.toolCalls?.map((call) =>
          call.id === event.id ? { ...call, output: event.output, status: 'done' } : call,
        ),
      }))
      break

    case 'sources':
      patch(assistantId, (draft) => ({ ...draft, sources: event.sources }))
      break

    case 'done':
      if (event.conversationId) conversation.current = event.conversationId
      break

    case 'error':
      patch(assistantId, (draft) => ({ ...draft, error: event.message }))
      break
  }
}
