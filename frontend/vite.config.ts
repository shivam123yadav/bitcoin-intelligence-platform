import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';

// The frontend services call relative paths such as `/api/v1/dataset/meta`
// (see src/services/config.ts -> API_BASE_URL defaults to '/api/v1').
//
// Without the proxy below, the Vite dev server answers those requests with its
// SPA fallback (index.html, status 200, content-type text/html), so
// `res.json()` throws:
//   Uncaught (in promise) SyntaxError: Unexpected token '<', "<!doctype "... is not valid JSON
//
// FastAPI already serves its routes under `/api` (health) and `/api/v1/...`
// (everything else), so `/api` is forwarded verbatim — no path rewrite needed.
// Override the target with VITE_BACKEND_ORIGIN (in .env or the OS environment).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const backendOrigin =
    env.VITE_BACKEND_ORIGIN || process.env.VITE_BACKEND_ORIGIN || 'http://127.0.0.1:8000';

  const apiProxy = {
    '/api': {
      target: backendOrigin,
      changeOrigin: true,
      secure: false,
    },
  };

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    // Let Vite pre-bundle lucide-react. Excluding it forces the browser to walk
    // the entire Lucide ESM icon graph and can trigger incorrect .js fallback
    // requests and excessive memory use with lucide-react 1.47.x.
    optimizeDeps: {
      include: ['lucide-react'],
    },
    server: {
      port: 5173,
      proxy: apiProxy,
    },
    preview: {
      port: 4173,
      proxy: apiProxy,
    },
  };
});
