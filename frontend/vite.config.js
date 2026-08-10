import { defineConfig } from 'vite';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const appRoot = process.env.GENERAL_AGENT_DIST_DIR
  ? resolve(process.env.GENERAL_AGENT_DIST_DIR)
  : resolve(__dirname, '..', 'app', 'templates', 'dist');
const mermaidVendorUrl = '/assets/vendor/mermaid.min.js';
const mermaidVendorPath = resolve(__dirname, 'node_modules', 'mermaid', 'dist', 'mermaid.min.js');

function mermaidVendorAssets() {
  return [
    {
      name: 'myagent-mermaid-vendor-build',
      apply: 'build',
      async buildStart() {
        this.emitFile({
          type: 'asset',
          fileName: mermaidVendorUrl.slice(1),
          source: await readFile(mermaidVendorPath),
        });
      },
    },
    {
      name: 'myagent-mermaid-vendor-serve',
      apply: 'serve',
      configureServer(server) {
        server.middlewares.use(async (request, response, next) => {
          const pathname = String(request.url || '').split('?', 1)[0];
          if (pathname !== mermaidVendorUrl) return next();
          try {
            response.statusCode = 200;
            response.setHeader('Content-Type', 'application/javascript; charset=utf-8');
            response.setHeader('Cache-Control', 'no-cache');
            response.end(await readFile(mermaidVendorPath));
          } catch (error) {
            next(error);
          }
        });
      },
    },
  ];
}

export default defineConfig({
  root: __dirname,
  base: '/',
  plugins: mermaidVendorAssets(),
  build: {
    outDir: appRoot,
    emptyOutDir: true,
    reportCompressedSize: false,
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        executionDashboard: resolve(__dirname, 'execution-dashboard.html'),
      },
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
