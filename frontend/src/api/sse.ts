/**
 * Parser de Server-Sent Events sobre `fetch`.
 *
 * `EventSource` não serve aqui porque só faz GET — o histórico da conversa
 * vai no corpo de um POST. Então lemos o `ReadableStream` na mão.
 */

/** Quebra um corpo SSE em cada payload `data:`, respeitando chunks parciais. */
export async function* readEventStream(
  body: ReadableStream<Uint8Array>,
  signal?: AbortSignal,
): AsyncGenerator<string> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const onAbort = () => void reader.cancel()
  signal?.addEventListener('abort', onAbort)

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // Eventos são separados por linha em branco. O último pedaço do
      // buffer pode estar incompleto, então fica para a próxima volta.
      const blocks = buffer.split(/\r?\n\r?\n/)
      buffer = blocks.pop() ?? ''

      for (const block of blocks) {
        const data = extractData(block)
        if (data !== null) yield data
      }
    }

    const tail = extractData(buffer)
    if (tail !== null) yield tail
  } finally {
    signal?.removeEventListener('abort', onAbort)
    reader.releaseLock()
  }
}

/** Junta as linhas `data:` de um bloco. Ignora comentários (`:`) e outros campos. */
function extractData(block: string): string | null {
  const lines = block.split(/\r?\n/)
  const parts: string[] = []

  for (const line of lines) {
    if (line.startsWith('data:')) {
      parts.push(line.slice(5).trimStart())
    }
  }

  if (parts.length === 0) return null
  const data = parts.join('\n')
  return data.length > 0 ? data : null
}
