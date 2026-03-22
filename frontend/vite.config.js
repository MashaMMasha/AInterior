import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      },
      '/auth': 'http://localhost:8001',
      '/upload_model': 'http://localhost:8001',
      '/uploaded_models': 'http://localhost:8001',
      '/generated_models': 'http://localhost:8001',
      '/generate': 'http://localhost:8001',
      '/projects': 'http://localhost:8001',
      '/health': 'http://localhost:8001'
    }
  }
})
