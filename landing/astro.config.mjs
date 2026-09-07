import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://azrael.vercel.app',
  trailingSlash: 'ignore',
  build: {
    inlineStylesheets: 'auto',
  },
  compressHTML: true,
});
