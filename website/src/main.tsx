import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { apiClient } from './api/client'
import './index.css'

// Restore the session token persisted at login so a page reload keeps the user
// authenticated (the ApiClient otherwise only holds the token in memory).
const storedToken = localStorage.getItem('session_token')
if (storedToken) {
  apiClient.setToken(storedToken)
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
