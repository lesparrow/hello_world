import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// En développement dans un navigateur, /rpc est relayé vers la passerelle Python
// (engine/statpfe/rpc/devbridge.py). L'application Tauri n'utilise jamais ce chemin.
const devToken = process.env.STATPFE_DEV_TOKEN ?? '';
const devPort = process.env.STATPFE_DEV_PORT ?? '8765';

export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/rpc': {
        target: `http://127.0.0.1:${devPort}`,
        headers: { 'X-Statpfe-Token': devToken },
      },
    },
  },
  build: {
    target: 'es2022',
    outDir: 'dist',
  },
  test: {
    environment: 'node',
  },
} as any);
