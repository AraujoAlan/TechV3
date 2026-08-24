import {
  useEffect,
  useRef,
  type FormEvent,
  type JSX,
  type KeyboardEvent,
  type RefObject,
} from 'react'
import { cn } from '../../lib/cn'
import { SendIcon, StopIcon } from '../primitives/icons'

interface ComposerProps {
  value: string
  onChange: (value: string) => void
  onSend: (text: string) => void
  onStop: () => void
  streaming: boolean
  /** Permite que o `App` devolva o foco ao campo após uma sugestão. */
  inputRef?: RefObject<HTMLTextAreaElement | null>
}

/**
 * Campo de entrada: cresce com o texto, envia no Enter e vira botão de parar
 * enquanto a resposta está sendo transmitida.
 *
 * O texto é controlado pelo `App` para que as sugestões da tela inicial
 * possam preenchê-lo sem efeito colateral.
 */
export function Composer({
  value,
  onChange,
  onSend,
  onStop,
  streaming,
  inputRef,
}: ComposerProps): JSX.Element {
  const fallbackRef = useRef<HTMLTextAreaElement>(null)
  const textareaRef = inputRef ?? fallbackRef

  // Sincroniza a altura do textarea com o conteúdo, até um teto de ~6 linhas.
  useEffect(() => {
    const textarea = textareaRef.current
    if (!textarea) return
    textarea.style.height = 'auto'
    textarea.style.height = `${Math.min(textarea.scrollHeight, 168)}px`
  }, [value, textareaRef])

  function submit(): void {
    const text = value.trim()
    if (text.length === 0 || streaming) return
    onSend(text)
  }

  function handleSubmit(event: FormEvent): void {
    event.preventDefault()
    submit()
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>): void {
    // Enter envia; Shift+Enter quebra linha.
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  const canSend = value.trim().length > 0

  return (
    <form onSubmit={handleSubmit} className="border-t border-line bg-canvas">
      <div className="mx-auto w-full max-w-2xl px-4 pt-3 pb-4 sm:px-6">
        <div className="flex items-end gap-2 rounded-2xl border border-line bg-surface p-2 transition-colors focus-within:border-accent/50">
          <label htmlFor="composer" className="sr-only">
            Mensagem para o assistente
          </label>
          <textarea
            id="composer"
            ref={textareaRef}
            rows={1}
            value={value}
            onChange={(event) => onChange(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Pergunte sobre um prontuário, exame ou protocolo…"
            className="max-h-42 flex-1 resize-none bg-transparent px-2 py-1.5 text-[0.9375rem] leading-relaxed text-ink placeholder:text-faint focus:outline-none"
          />

          {streaming ? (
            <button
              type="button"
              onClick={onStop}
              aria-label="Parar resposta"
              className="flex size-9 shrink-0 items-center justify-center rounded-xl border border-line text-muted transition-colors hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            >
              <StopIcon className="size-4" />
            </button>
          ) : (
            <button
              type="submit"
              disabled={!canSend}
              aria-label="Enviar mensagem"
              className={cn(
                'flex size-9 shrink-0 items-center justify-center rounded-xl transition-colors',
                'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent',
                canSend
                  ? 'bg-accent text-accent-ink hover:opacity-90'
                  : 'bg-raised text-faint cursor-not-allowed',
              )}
            >
              <SendIcon className="size-4" />
            </button>
          )}
        </div>

        <p className="mt-2 text-center text-[0.6875rem] leading-relaxed text-faint">
          Apoio à decisão clínica. Não prescreve nem substitui a sua avaliação.
        </p>
      </div>
    </form>
  )
}
