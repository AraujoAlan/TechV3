import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      // Em dev, `/api` vai para o FastAPI. Assim o frontend usa caminhos
      // relativos em qualquer ambiente e não existe CORS para resolver.
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    // O FastAPI serve este diretório em produção (monolito, um processo só).
    outDir: 'dist',
  },
})
