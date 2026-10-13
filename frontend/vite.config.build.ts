// Production build config for the existing Tailwind v3 design system.
// Use Tailwind v3 through PostCSS explicitly so the shipped Docker build always
// includes the application's design-system CSS; the unused Tailwind v4 Vite
// plugin is intentionally not imported here.
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from 'tailwindcss'
import autoprefixer from 'autoprefixer'

export default defineConfig({
  plugins: [react()],
  css: {
    postcss: {
      plugins: [tailwindcss(), autoprefixer()],
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
