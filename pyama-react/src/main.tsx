import { createRoot } from 'react-dom/client'
import './index.css'
import { App } from './app.tsx'
import { initializeTheme } from './lib/theme'

// Initialize theme before render to prevent flash
initializeTheme()

createRoot(document.getElementById('app')!).render(<App />)
