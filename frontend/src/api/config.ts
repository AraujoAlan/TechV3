/**
 * Configuração da camada de API.
 *
 * Em desenvolvimento o Vite faz proxy de `/api` para o backend Python
 * (ver `vite.config.ts`), então `BASE_URL` fica vazio e as chamadas são
 * relativas — o mesmo vale em produção, onde o FastAPI serve o `dist/`.
 */

/** Prefixo das rotas. Sobrescreva com `VITE_API_BASE_URL` se a API estiver em outro host. */
export const BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? ''

/**
 * Quando `true`, `streamChat` usa o mock local em vez da rede.
 * Permite desenvolver e demonstrar o frontend sem o backend no ar.
 */
export const USE_MOCK: boolean = import.meta.env.VITE_USE_MOCK !== 'false'

export const ENDPOINTS = {
  chat: `${BASE_URL}/api/chat`,
  health: `${BASE_URL}/api/health`,
} as const
