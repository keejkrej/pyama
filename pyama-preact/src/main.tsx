import { render } from 'preact'
import './index.css'
import { App } from './app.tsx'
import { initTheme } from './lib/theme.ts'

// Initialize theme
initTheme()

render(<App />, document.getElementById('app')!)
