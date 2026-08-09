import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import '@fontsource/inter/latin-400.css'
import '@fontsource/inter/latin-500.css'
import '@fontsource/inter/latin-700.css'
import './designTokens.css'
import './styles.css'
import '@xyflow/react/dist/style.css'

if (typeof window.matchMedia === 'function') {
  const colorScheme = window.matchMedia('(prefers-color-scheme: dark)')
  const applyColorScheme = (matches: boolean) => {
    document.documentElement.dataset.theme = matches ? 'dark' : 'light'
  }
  applyColorScheme(colorScheme.matches)
  colorScheme.addEventListener('change', (event) => applyColorScheme(event.matches))
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
