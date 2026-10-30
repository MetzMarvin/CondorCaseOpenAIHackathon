import { defineConfig, loadEnv } from 'vite';
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  return {
    server: { proxy: { '/api': env.API_PROXY_TARGET || 'http://127.0.0.1:8000' } },
    test: { environment: 'jsdom' },
  };
});
