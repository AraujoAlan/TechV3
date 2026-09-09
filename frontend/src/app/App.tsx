import { useEffect, useRef, useState, type JSX } from 'react'
import { checkHealth, type BackendStatus } from '../api'
import { ChatView } from '../ui/chat/ChatView'
import { AppShell } from '../ui/layout/AppShell'
import { Header } from '../ui/layout/Header'
import { useChat } from './useChat'

/** Raiz da aplicação: liga o estado da conversa à árvore de componentes. */
export function App(): JSX.Element {
  const { messages, status, error, send, stop, reset } = useChat()
  const [backend, setBackend] = useState<BackendStatus>('mock')
  const [input, setInput] = useState('')
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const controller = new AbortController()
    void checkHealth(controller.signal).then(setBackend)
    return () => controller.abort()
  }, [])

  function handleSend(text: string): void {
    setInput('')
    send(text)
  }

  function handleReset(): void {
    reset()
    setInput('')
  }

  /** Sugestão da tela inicial: preenche o campo e devolve o foco. */
  function handlePickSuggestion(text: string): void {
    setInput(text)
    inputRef.current?.focus()
  }

  return (
    <AppShell>
      <Header status={backend} onReset={handleReset} canReset={messages.length > 0} />
      <ChatView
        messages={messages}
        streaming={status === 'streaming'}
        error={error}
        input={input}
        inputRef={inputRef}
        onInputChange={setInput}
        onSend={handleSend}
        onStop={stop}
        onPickSuggestion={handlePickSuggestion}
      />
    </AppShell>
  )
}
