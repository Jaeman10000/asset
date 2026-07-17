import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // 개발 중 프론트(5173)에서 /api 호출을 로컬 백엔드(8787)로 프록시.
    // 프로덕션 Tauri 빌드에서는 VITE_API_BASE로 직접 지정 (api/client.ts 참고).
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8787',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ''),
      },
    },
  },
})
