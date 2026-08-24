/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Host da API, quando ela não está atrás do mesmo domínio. Padrão: vazio. */
  readonly VITE_API_BASE_URL?: string
  /** `'false'` desliga o mock e passa a chamar o backend de verdade. */
  readonly VITE_USE_MOCK?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
