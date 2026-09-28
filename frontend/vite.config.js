import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Local development mirrors Vercel: the page calls /api/..., which Vite forwards to the backend
// started with:  uvicorn api.index:app --port 8000
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': 'http://localhost:8000' } },
  build: { chunkSizeWarningLimit: 1200 },
})
