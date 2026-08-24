/** Erro normalizado da camada de API, para a UI não lidar com `unknown`. */
export class ApiError extends Error {
  readonly status?: number

  constructor(message: string, status?: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** Converte qualquer coisa lançada em uma mensagem legível para o médico. */
export function toUserMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof DOMException && error.name === 'AbortError') {
    return 'Resposta interrompida.'
  }
  if (error instanceof TypeError) {
    return 'Não foi possível falar com o servidor. Verifique se a API está no ar.'
  }
  return error instanceof Error ? error.message : 'Erro inesperado.'
}
