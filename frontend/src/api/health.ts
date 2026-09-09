import { ENDPOINTS, USE_MOCK } from './config'

export type BackendStatus = 'mock' | 'online' | 'offline'

/**
 * Verifica se a API está no ar. O indicador no cabeçalho deixa explícito
 * durante a demo se as respostas vêm do mock ou do agent real.
 */
export async function checkHealth(signal?: AbortSignal): Promise<BackendStatus> {
  if (USE_MOCK) return 'mock'

  try {
    const response = await fetch(ENDPOINTS.health, { signal })
    return response.ok ? 'online' : 'offline'
  } catch {
    return 'offline'
  }
}
