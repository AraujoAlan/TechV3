import type { JSX } from 'react'
import type { Source } from '../../api'
import { SourceIcon } from '../primitives/icons'

/**
 * Fontes citadas na resposta — o requisito de explainability da Fase 3:
 * o médico precisa saber de onde veio cada informação.
 */
export function SourceList({ sources }: { sources: Source[] }): JSX.Element | null {
  if (sources.length === 0) return null

  return (
    <section className="mt-3 border-t border-line pt-2.5">
      <h3 className="mb-1.5 text-[0.6875rem] font-medium tracking-wide text-faint uppercase">
        Fontes consultadas
      </h3>

      <ul className="space-y-1.5">
        {sources.map((source) => (
          <li key={source.id} className="flex gap-2 text-xs">
            <SourceIcon className="mt-px size-3.5 shrink-0 text-faint" />
            <div className="min-w-0">
              <p className="text-ink">{source.title}</p>
              {source.snippet && <p className="mt-0.5 text-muted">{source.snippet}</p>}
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
