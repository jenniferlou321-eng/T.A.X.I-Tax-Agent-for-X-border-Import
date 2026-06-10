// Build-only Vite config. The tailwindcss plugin is omitted because Tailwind
// v4 requires Node 20+ and this box has Node 16. Tailwind classes in the
// source will simply be unstyled (the app still works, just plain).
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
