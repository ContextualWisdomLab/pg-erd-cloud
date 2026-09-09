import { defineConfig, type Plugin } from 'vite'

const STRICT_STYLE_CSP = "style-src 'self'"

// `vite dev` injects HMR styles as inline <style> tags. Relax only the exact
// strict policy shipped by index.html, and fail fast if that policy drifts so a
// broader CSP change cannot be silently reinterpreted as a development rule.
function devCspInlineStyles(): Plugin {
  return {
    name: 'dev-csp-inline-styles',
    apply: 'serve',
    transformIndexHtml(html) {
      if (!html.includes(STRICT_STYLE_CSP)) {
        throw new Error(`dev CSP transform expected ${STRICT_STYLE_CSP}`)
      }
      return html.replace(
        STRICT_STYLE_CSP,
        `${STRICT_STYLE_CSP} 'unsafe-inline'`,
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
