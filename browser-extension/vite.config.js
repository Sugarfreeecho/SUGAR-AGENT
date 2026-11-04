import { defineConfig } from 'vite';
import { resolve } from 'node:path';
import {mainSmoothFollowPlugin} from './scripts/main-smooth-follow.mjs';
export default defineConfig({
  base: './',
  plugins:[mainSmoothFollowPlugin()],
  build: {
    outDir: 'dist', sourcemap: true, reportCompressedSize: false,
    rollupOptions: {
      input: { sidepanel: resolve(import.meta.dirname, 'sidepanel.html'), background: resolve(import.meta.dirname, 'src/background.ts') },
      output: { entryFileNames: '[name].js', chunkFileNames: 'assets/[name]-[hash].js' },
    },
  },
});
