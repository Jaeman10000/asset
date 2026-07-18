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
    watch: {
      // Rust 빌드 산출물(src-tauri/target)을 감시하면 잠긴 .dll에서 EBUSY로
      // vite가 죽는다 (tauri dev 실패 원인). 감시 대상에서 제외.
      ignored: ['**/src-tauri/**'],
    },
  },
})
