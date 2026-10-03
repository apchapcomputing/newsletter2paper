import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  // Source files in this repo contain JSX inside .js files (Next.js allows it; Vite does not by default).
  esbuild: { loader: 'jsx', include: /\.jsx?$/, exclude: /node_modules/ },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./tests/setup.js'],
    include: ['tests/**/*.test.{js,jsx}'],
    restoreMocks: true,
    unstubEnvs: true,
    unstubGlobals: true,
  },
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './')
    }
  }
})
