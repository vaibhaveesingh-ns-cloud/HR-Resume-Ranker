import path from 'path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
    // Load env from project root
    const env = loadEnv(mode, process.cwd(), '');
    const API_KEY = env.VITE_GEMINI_API_KEY || env.GEMINI_API_KEY || env.API_KEY || '';
    return {
      plugins: [react()],
      define: {
        // Back-compat define so existing code using process.env.API_KEY works
        'process.env.API_KEY': JSON.stringify(API_KEY),
        'process.env.GEMINI_API_KEY': JSON.stringify(env.GEMINI_API_KEY || ''),
        'import.meta.env.VITE_GEMINI_API_KEY': JSON.stringify(env.VITE_GEMINI_API_KEY || ''),
        'import.meta.env.VITE_API_BASE': JSON.stringify(env.VITE_API_BASE || ''),
      },
      resolve: {
        alias: {
          '@': path.resolve(__dirname, '.'),
        }
      }
    };
});
