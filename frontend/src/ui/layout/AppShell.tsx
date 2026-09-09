import type { JSX, ReactNode } from 'react'

/** Coluna única de altura total: cabeçalho, conteúdo rolável e composer. */
export function AppShell({ children }: { children: ReactNode }): JSX.Element {
  return <div className="mx-auto flex h-full max-w-4xl flex-col bg-canvas">{children}</div>
}
