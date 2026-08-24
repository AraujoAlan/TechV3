import type { JSX, RefObject } from 'react'
import type { Message } from '../../api'
import { AlertIcon } from '../primitives/icons'
import { Composer } from './Composer'
import { EmptyState } from './EmptyState'
import { MessageList } from './MessageList'

interface ChatViewProps {
  messages: Message[]
  streaming: boolean
  error: string | null
  input: string
  inputRef: RefObject<HTMLTextAreaElement | null>
  onInputChange: (value: string) => void
  onSend: (text: string) => void
  onStop: () => void
  onPickSuggestion: (text: string) => void
}

/**
 * Composição da tela de chat. É puramente apresentacional: recebe estado e
 * callbacks, não conhece a camada de API.
 */
export function ChatView({
  messages,
  streaming,
  error,
  input,
  inputRef,
  onInputChange,
  onSend,
  onStop,
  onPickSuggestion,
}: ChatViewProps): JSX.Element {
  return (
    <>
      {messages.length === 0 ? (
        <EmptyState onPick={onPickSuggestion} />
      ) : (
        <MessageList messages={messages} />
      )}

      {error && (
        <div
          role="alert"
          className="mx-auto flex w-full max-w-2xl items-start gap-2 px-4 pb-2 text-xs text-danger sm:px-6"
        >
          <AlertIcon className="mt-px size-3.5 shrink-0" />
          {error}
        </div>
      )}

      <Composer
        value={input}
        onChange={onInputChange}
        onSend={onSend}
        onStop={onStop}
        streaming={streaming}
        inputRef={inputRef}
      />
    </>
  )
}
