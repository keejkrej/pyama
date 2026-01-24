import { render } from 'preact'
import './index.css'
import { App } from './app.tsx'
import { initializeTheme } from './lib/theme'

// Initialize theme before render to prevent flash
initializeTheme()

render(<App />, document.getElementById('app')!)
