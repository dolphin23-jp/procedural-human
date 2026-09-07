import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: '/procedural-human/',
  plugins: [react()],
  resolve: {
    alias: [
      {
        // vtk.js imports xmlbuilder2's Node entry; its published browser bundle
        // includes the required events/URL support. Do not stub those APIs.
        find: /^xmlbuilder2$/,
        replacement: 'xmlbuilder2/lib/xmlbuilder2.min.js',
      },
    ],
  },
});
