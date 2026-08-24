import type { JSX } from 'react'

interface RichTextProps {
  text: string
  /** Desenha o cursor piscando no fim do texto enquanto os tokens chegam. */
  caret?: boolean
}

/**
 * Renderiza o subconjunto de Markdown que o assistente realmente usa:
 * `**negrito**`, listas numeradas e listas com marcador.
 *
 * É deliberadamente pequeno — nada de `dangerouslySetInnerHTML`, então
 * texto vindo do modelo nunca vira HTML.
 */
export function RichText({ text, caret = false }: RichTextProps): JSX.Element {
  const blocks = text.split(/\n{2,}/)

  return (
    <>
      {blocks.map((block, index) => (
        <Block key={index} text={block} caret={caret && index === blocks.length - 1} />
      ))}
    </>
  )
}

function Block({ text, caret }: { text: string; caret: boolean }): JSX.Element {
  const lines = text.split('\n')
  const isList = lines.every((line) => LIST_ITEM.test(line.trim()))

  if (isList && lines.length > 0) {
    return (
      <ul className="my-2 space-y-1.5 first:mt-0 last:mb-0">
        {lines.map((line, index) => {
          const [, marker, content] = line.trim().match(LIST_ITEM) ?? []
          return (
            <li key={index} className="flex gap-2.5">
              <span className="mt-px shrink-0 text-faint tabular-nums">{marker}</span>
              <span className="min-w-0">
                <Inline text={content ?? ''} />
                {/* O cursor acompanha o último item, não uma linha solta abaixo da lista. */}
                {caret && index === lines.length - 1 && <Caret />}
              </span>
            </li>
          )
        })}
      </ul>
    )
  }

  return (
    <p className="my-2 first:mt-0 last:mb-0">
      {lines.map((line, index) => (
        <span key={index}>
          {index > 0 && <br />}
          <Inline text={line} />
          {caret && index === lines.length - 1 && <Caret />}
        </span>
      ))}
    </p>
  )
}

/** Alterna entre trechos normais e trechos em `**negrito**`. */
function Inline({ text }: { text: string }): JSX.Element {
  const parts = text.split(/(\*\*[^*]+\*\*)/g)

  return (
    <>
      {parts.map((part, index) =>
        part.startsWith('**') && part.endsWith('**') && part.length > 4 ? (
          <strong key={index} className="font-semibold">
            {part.slice(2, -2)}
          </strong>
        ) : (
          part
        ),
      )}
    </>
  )
}

function Caret(): JSX.Element {
  return <span className="stream-caret" aria-hidden="true" />
}

/** `1. item`, `- item`, `• item` — captura o marcador e o conteúdo. */
const LIST_ITEM = /^(\d+\.|[-•*])\s+(.*)$/
