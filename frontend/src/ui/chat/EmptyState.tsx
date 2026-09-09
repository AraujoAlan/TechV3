import type { JSX } from 'react'

const SUGGESTIONS = [
  'Mostre o prontuário da paciente 12345',
  'Quais exames estão pendentes para a 12345?',
  'Qual o protocolo para ciclo irregular?',
] as const

/** Primeira tela: o que o assistente faz e três perguntas para começar. */
export function EmptyState({ onPick }: { onPick: (text: string) => void }): JSX.Element {
  return (
    <div className="flex flex-1 items-center justify-center px-4 py-10">
      <div className="w-full max-w-lg text-center">
        <h2 className="text-xl font-medium text-ink">Como posso ajudar na conduta?</h2>
        <p className="mx-auto mt-2 max-w-sm text-sm leading-relaxed text-muted">
          Consulto prontuários, exames pendentes e os protocolos internos do hospital para apoiar
          a sua decisão clínica.
        </p>

        <ul className="mt-7 space-y-2">
          {SUGGESTIONS.map((suggestion) => (
            <li key={suggestion}>
              <button
                type="button"
                onClick={() => onPick(suggestion)}
                className="w-full rounded-xl border border-line bg-surface px-4 py-2.5 text-left text-sm text-muted transition-colors hover:border-accent/40 hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
              >
                {suggestion}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
