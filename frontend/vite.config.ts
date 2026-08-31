import { defineConfig } from 'vite'

export default defineConfig({
  server: {
    port: 5173,
    strictPort: true,
    ...(process.env.E2E_API_PROXY_TARGET
      ? {
          proxy: {
            '/api': {
              target: process.env.E2E_API_PROXY_TARGET,
              changeOrigin: true
            }
          }
        }
      : {})
  },
  test: {
    environment: 'jsdom'
  }
})
