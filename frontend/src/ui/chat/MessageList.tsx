import { useEffect, useRef, type JSX } from 'react'
import type { Message } from '../../api'
import { MessageBubble } from './MessageBubble'

/**
 * Lista rolável das mensagens.
 *
 * Acompanha o final do stream automaticamente, mas para de puxar se o médico
 * rolou para cima para reler algo — nada mais irritante que a tela fugindo.
 */
export function MessageList({ messages }: { messages: Message[] }): JSX.Element {
  const viewportRef = useRef<HTMLDivElement>(null)
  const stickToBottom = useRef(true)

  // Atualiza o scroll quando chega conteúdo ou fontes da última mensagem.
  const tail = messages.at(-1)

  useEffect(() => {
    const viewport = viewportRef.current
    if (!viewport || !stickToBottom.current) return
    viewport.scrollTop = viewport.scrollHeight
  }, [messages.length, tail?.content, tail?.sources?.length])

  function handleScroll(): void {
    const viewport = viewportRef.current
    if (!viewport) return
    const distance = viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight
    stickToBottom.current = distance < 80
  }

  return (
    <div
      ref={viewportRef}
      onScroll={handleScroll}
      className="subtle-scroll flex-1 overflow-y-auto overscroll-contain"
    >
      <div
        className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-4 py-6 sm:px-6"
        role="log"
        aria-live="polite"
        aria-label="Conversa com o assistente"
      >
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
      </div>
    </div>
  )
}
