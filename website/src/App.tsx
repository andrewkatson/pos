import { Routes, Route } from 'react-router-dom'
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import RequestResetPage from './pages/RequestResetPage'
import VerifyResetPage from './pages/VerifyResetPage'
import ResetPasswordPage from './pages/ResetPasswordPage'
import HomePage from './pages/HomePage'
import PostDetailPage from './pages/PostDetailPage'
import ProfilePage from './pages/ProfilePage'
import AppealsPage from './pages/AppealsPage'
import PrivacyPolicyPage from './pages/PrivacyPolicyPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/request-reset" element={<RequestResetPage />} />
      <Route path="/verify-reset" element={<VerifyResetPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/home" element={<HomePage />} />
      <Route path="/post/:postId" element={<PostDetailPage />} />
      <Route path="/profile/:username" element={<ProfilePage />} />
      <Route path="/appeals" element={<AppealsPage />} />
      <Route path="/privacy-policy" element={<PrivacyPolicyPage />} />
    </Routes>
  )
}

export default App
