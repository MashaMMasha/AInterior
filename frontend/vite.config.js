import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/__obllomov_render__': {
        target: 'http://127.0.0.1:8088',
        changeOrigin: true,
        rewrite: (path) => {
          const stripped = path.replace(/^\/__obllomov_render__\/?/, '') || '/'
          return stripped.startsWith('/') ? stripped : `/${stripped}`
        }
      },
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
      '/projects': 'http://localhost:8004',
      '/chat': 'http://localhost:8003',
      '/health': 'http://localhost:8001'
    }
  }
})
