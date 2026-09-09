import { defineConfig, type Plugin } from 'vite'

// Dev-only CSP relaxation (issue #1108): `vite dev` injects HMR styles as
// inline <style> tags, which the strict `style-src 'self'` meta in
// index.html drops, leaving the app unstyled under the dev server.
// Production builds emit external CSS files that satisfy 'self', so the
// shipped header stays strict. `apply: 'serve'` keeps this out of builds.
function devCspInlineStyles(): Plugin {
  return {
    name: 'dev-csp-inline-styles',
    apply: 'serve',
    transformIndexHtml(html) {
      return html.replace(
        "style-src 'self'",
        "style-src 'self' 'unsafe-inline'",
      )
    },
  }
}

export default defineConfig({
  server: {
    port: 5173,
    strictPort: true
  },
  plugins: [devCspInlineStyles()],
  test: {
    environment: 'jsdom'
  }
})
