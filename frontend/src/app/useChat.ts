import { useCallback, useRef, useState } from 'react'
import { sendChat, toUserMessage } from '../api'
import type { Message } from '../api'
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
 * Orquestra a conversa: mantém o histórico local, envia só a pergunta
 * corrente à API e preenche uma única mensagem do assistente ao concluir.
 */
export function useChat(): UseChatResult {
  const [messages, setMessages] = useState<Message[]>([])
  const [status, setStatus] = useState<ChatStatus>('idle')
  const [error, setError] = useState<string | null>(null)

  const abortRef = useRef<AbortController | null>(null)
  const conversationRef = useRef<string>(createId('conv'))

  const patchAssistant = useCallback((id: string, patch: (draft: Message) => Message) => {
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

      setMessages((current) => [...current, userMessage, assistantMessage])

      const controller = new AbortController()
      abortRef.current = controller
      setStatus('streaming')

      void (async () => {
        try {
          const response = await sendChat(
            { question: text, conversation_id: conversationRef.current },
            controller.signal,
          )

          patchAssistant(assistantId, (draft) => ({
            ...draft,
            content: response.answer,
            sources: response.sources,
            alert: response.alert,
            outcome: response.outcome,
            streaming: false,
            error: undefined,
          }))
        } catch (cause) {
          const message = toUserMessage(cause)
          const aborted = controller.signal.aborted

          if (!aborted) setError(message)
          patchAssistant(assistantId, (draft) => ({
            ...draft,
            error: aborted ? undefined : message,
            streaming: false,
          }))
        } finally {
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
    setMessages([])
    setError(null)
    setStatus('idle')
  }, [])

  return { messages, status, error, send, stop, reset }
}
