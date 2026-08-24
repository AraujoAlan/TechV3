import type { JSX } from 'react'
import type { BackendStatus } from '../../api'
import { cn } from '../../lib/cn'
import { NewChatIcon } from '../primitives/icons'

interface HeaderProps {
  status: BackendStatus
  onReset: () => void
  canReset: boolean
}

/** Cabeçalho fixo: identidade, origem das respostas e reinício da conversa. */
export function Header({ status, onReset, canReset }: HeaderProps): JSX.Element {
  return (
    <header className="border-b border-line bg-canvas/85 backdrop-blur-sm">
      <div className="mx-auto flex w-full max-w-2xl items-center gap-3 px-4 py-3 sm:px-6">
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-sm font-medium text-ink">Assistente Virtual · Ginecologia</h1>
          <BackendBadge status={status} />
        </div>

        <button
          type="button"
          onClick={onReset}
          disabled={!canReset}
          className={cn(
            'flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1.5 text-xs transition-colors',
            'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent',
            canReset
              ? 'text-muted hover:border-accent/40 hover:text-ink'
              : 'cursor-not-allowed text-faint',
          )}
        >
          <NewChatIcon className="size-3.5" />
          Nova conversa
        </button>
      </div>
    </header>
  )
}

/**
 * Deixa explícito de onde vêm as respostas. Durante a apresentação, evita a
 * dúvida de estar demonstrando o mock achando que é o agent real.
 */
function BackendBadge({ status }: { status: BackendStatus }): JSX.Element {
  const config = {
    mock: { label: 'Dados simulados', dot: 'bg-faint' },
    online: { label: 'API conectada', dot: 'bg-accent' },
    offline: { label: 'API indisponível', dot: 'bg-danger' },
  } as const

  const { label, dot } = config[status]

  return (
    <p className="mt-0.5 flex items-center gap-1.5 text-[0.6875rem] text-faint">
      <span className={cn('size-1.5 rounded-full', dot)} aria-hidden="true" />
      {label}
    </p>
  )
}
