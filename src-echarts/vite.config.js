import { defineConfig } from 'vite';

export default defineConfig({
  base: './',
  build: {
    // 编译为一个单独的文件，方便被 PySide6 加载
    rollupOptions: {
      output: {
        entryFileNames: `assets/[name].js`,
        chunkFileNames: `assets/[name].js`,
        assetFileNames: `assets/[name].[ext]`
      }
    }
  }
});