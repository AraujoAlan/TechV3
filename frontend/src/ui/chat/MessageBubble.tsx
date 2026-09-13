import type { JSX } from 'react'
import type { Message } from '../../api'
import { formatTime } from '../../lib/time'
import { AlertIcon } from '../primitives/icons'
import { RichText } from '../primitives/RichText'
import { SourceList } from './SourceList'

/**
 * Uma mensagem da conversa.
 *
 * A do médico vira bolha alinhada à direita; a do assistente ocupa a largura
 * do texto, sem caixa, para leitura longa ficar confortável.
 */
export function MessageBubble({ message }: { message: Message }): JSX.Element {
  return message.role === 'user' ? (
    <UserMessage message={message} />
  ) : (
    <AssistantMessage message={message} />
  )
}

function UserMessage({ message }: { message: Message }): JSX.Element {
  return (
    <article className="flex justify-end">
      <div className="max-w-[85%] sm:max-w-[75%]">
        <div className="rounded-2xl rounded-br-md bg-accent px-4 py-2.5 text-accent-ink">
          <p className="text-[0.9375rem] leading-relaxed whitespace-pre-wrap">{message.content}</p>
        </div>
        <time
          className="mt-1 block text-right text-[0.6875rem] text-faint"
          dateTime={new Date(message.createdAt).toISOString()}
        >
          {formatTime(message.createdAt)}
        </time>
      </div>
    </article>
  )
}

function AssistantMessage({ message }: { message: Message }): JSX.Element {
  const empty = message.content.length === 0
  const waiting = empty && message.streaming === true

  return (
    <article className="flex gap-3">
      <Avatar />

      <div className="min-w-0 flex-1 pt-0.5">
        {waiting ? (
          <ThinkingDots />
        ) : (
          <div className="text-[0.9375rem] leading-relaxed text-ink">
            <RichText text={message.content} caret={message.streaming === true} />
          </div>
        )}

        {message.sources && <SourceList sources={message.sources} />}

        {message.alert?.status === 'simulated_recorded' && (
          <p className="mt-2 text-xs text-muted" role="status">
            Alerta clínico simulado registrado para auditoria da demonstração.
          </p>
        )}

        {message.error && (
          <p className="mt-2 flex items-start gap-1.5 text-xs text-danger">
            <AlertIcon className="mt-px size-3.5 shrink-0" />
            {message.error}
          </p>
        )}
      </div>
    </article>
  )
}

function Avatar(): JSX.Element {
  return (
    <div
      aria-hidden="true"
      className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-accent-soft text-[0.625rem] font-semibold tracking-wide text-accent"
    >
      AV
    </div>
  )
}

/** Placeholder enquanto a API ainda não devolveu a resposta. */
function ThinkingDots(): JSX.Element {
  return (
    <p className="flex items-center gap-1 py-1" role="status" aria-label="Gerando resposta">
      {[0, 1, 2].map((index) => (
        <span
          key={index}
          className="size-1.5 animate-bounce rounded-full bg-faint"
          style={{ animationDelay: `${index * 140}ms` }}
        />
      ))}
    </p>
  )
}
