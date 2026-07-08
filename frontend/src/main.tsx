import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { LazyMotion, domMax, MotionConfig } from 'framer-motion'
import './styles/tokens.css'
import './styles/global.css'
import './styles/ui.css'
import App from './App'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <MotionConfig reducedMotion="user">
      <LazyMotion features={domMax}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </LazyMotion>
    </MotionConfig>
  </StrictMode>,
)
