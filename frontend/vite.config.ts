import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
//
// - `server.port = 9000` and `host: true` (= 0.0.0.0) so the dev server is
//   reachable from outside the container/host, e.g. behind a public tunnel.
// - `server.proxy` forwards /api (REST + WebSocket), /docs, /openapi.json and
//   /health to the FastAPI backend on port 8765. With the proxy in place the
//   frontend can default to a same-origin API base — and the WS handshake
//   `Upgrade` header is preserved (`ws: true`).
// - For production (`vite build` → `vite preview`) the same defaults are
//   applied so a one-line `npm run preview -- --port 9000 --host` also works.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    port: 9000,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8765',
        changeOrigin: true,
        ws: true,
      },
      '/docs': {
        target: 'http://127.0.0.1:8765',
        changeOrigin: true,
      },
      '/openapi.json': {
        target: 'http://127.0.0.1:8765',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://127.0.0.1:8765',
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: true,
    port: 9000,
    strictPort: true,
  },
})
