import { defineConfig } from 'vite';
import { resolve } from 'node:path';

const appRoot = process.env.GENERAL_AGENT_DIST_DIR
  ? resolve(process.env.GENERAL_AGENT_DIST_DIR)
  : resolve(__dirname, '..', 'app', 'templates', 'dist');

export default defineConfig({
  root: __dirname,
  base: '/',
  build: {
    outDir: appRoot,
    emptyOutDir: true,
    rollupOptions: {
      input: resolve(__dirname, 'index.html'),
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/sessions': { target: 'http://127.0.0.1:8192', changeOrigin: true },
      '/api': { target: 'http://127.0.0.1:8192', changeOrigin: true },
    },
  },
});
