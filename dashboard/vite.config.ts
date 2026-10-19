import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { fileURLToPath } from 'url';
import { defineConfig } from 'vite';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig(() => {
  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      },
    },
    server: {
      // HMR is disabled in AI Studio via DISABLE_HMR env var.
      // Do not modify—file watching is disabled to prevent flickering during agent edits.
      hmr: process.env.DISABLE_HMR !== 'true',
      // Disable file watching when DISABLE_HMR is true to save CPU during agent edits.
      watch: process.env.DISABLE_HMR === 'true' ? null : {},
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
        },
        '/ws': {
          target: 'ws://127.0.0.1:8000',
          ws: true,
          configure: (proxy) => {
            proxy.on('error', (err: any) => {
              if (err?.code === 'ECONNABORTED' || err?.code === 'ECONNRESET') {
                return;
              }
              console.error('[vite] ws proxy error:', err?.message || err);
            });
            proxy.on('proxyReqWs', (_proxyReq, _req, socket: any) => {
              socket.on('error', (err: any) => {
                if (err?.code === 'ECONNABORTED' || err?.code === 'ECONNRESET') {
                  return;
                }
              });
            });
          },
        },
        '/health': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
        },
      },
    },
  };
});
