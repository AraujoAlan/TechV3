import { useState, type JSX } from 'react'
import type { ToolCall } from '../../api'
import { ChevronIcon, ToolIcon } from '../primitives/icons'
import { cn } from '../../lib/cn'

/**
 * Trilha das tools executadas pelo agent LangGraph.
 *
 * Fica recolhida por padrão para não poluir a leitura, mas deixa o caminho
 * da decisão auditável — é o requisito de rastreabilidade da entrega.
 */
export function ToolTrace({ calls }: { calls: ToolCall[] }): JSX.Element | null {
  const [open, setOpen] = useState(false)
  if (calls.length === 0) return null

  const running = calls.some((call) => call.status === 'running')
  const label = running
    ? `Consultando ${formatName(calls.at(-1)!.name)}…`
    : `${calls.length} ${calls.length === 1 ? 'consulta realizada' : 'consultas realizadas'}`

  return (
    <div className="mb-2.5">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className={cn(
          'group flex items-center gap-1.5 rounded-full border border-line px-2.5 py-1',
          'text-xs text-muted transition-colors hover:border-accent/40 hover:text-ink',
          'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent',
        )}
      >
        <ToolIcon className={cn('size-3.5 shrink-0', running && 'animate-pulse text-accent')} />
        <span>{label}</span>
        <ChevronIcon
          className={cn('size-3.5 shrink-0 transition-transform', open && 'rotate-180')}
        />
      </button>

      {open && (
        <ol className="mt-2 space-y-2 border-l border-line pl-3">
          {calls.map((call) => (
            <li key={call.id} className="text-xs">
              <div className="flex items-center gap-2">
                <span className="font-mono text-ink">{call.name}</span>
                <StatusDot status={call.status} />
              </div>

              {call.input && Object.keys(call.input).length > 0 && (
                <p className="mt-0.5 font-mono text-faint">
                  {Object.entries(call.input)
                    .map(([key, value]) => `${key}: ${String(value)}`)
                    .join(' · ')}
                </p>
              )}

              {call.output && <p className="mt-1 text-muted">{call.output}</p>}
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

function StatusDot({ status }: { status: ToolCall['status'] }): JSX.Element {
  const styles = {
    running: 'bg-accent animate-pulse',
    done: 'bg-accent/50',
    error: 'bg-danger',
  } as const

  const labels = { running: 'Em execução', done: 'Concluída', error: 'Falhou' } as const

  return <span className={cn('size-1.5 rounded-full', styles[status])} title={labels[status]} />
}

/** `buscar_prontuario` → `buscar prontuario`, para caber numa frase. */
function formatName(name: string): string {
  return name.replaceAll('_', ' ')
}
