import { Routes, Route } from 'react-router'
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import CheckEmailPage from './pages/CheckEmailPage'
import VerifyEmailPage from './pages/VerifyEmailPage'
import VerifyEmailChangePage from './pages/VerifyEmailChangePage'
import RequestResetPage from './pages/RequestResetPage'
import VerifyResetPage from './pages/VerifyResetPage'
import ResetPasswordPage from './pages/ResetPasswordPage'
import HomePage from './pages/HomePage'
import PostDetailPage from './pages/PostDetailPage'
import ProfilePage from './pages/ProfilePage'
import TagPage from './pages/TagPage'
import AppealsPage from './pages/AppealsPage'
import BlockedUsersPage from './pages/BlockedUsersPage'
import SavedPostsPage from './pages/SavedPostsPage'
import FollowListPage from './pages/FollowListPage'
import FollowRequestsPage from './pages/FollowRequestsPage'
import PrivacyPolicyPage from './pages/PrivacyPolicyPage'
import TermsOfServicePage from './pages/TermsOfServicePage'
import SupportPage from './pages/SupportPage'
import DeleteAccountPage from './pages/DeleteAccountPage'
import PrivacyPolicyReacceptGate from './components/PrivacyPolicyReacceptGate'

function App() {
  return (
    // Asks a signed-in user to re-accept the privacy policy (issue #620), and
    // keeps the page behind it inert until they answer.
    <PrivacyPolicyReacceptGate>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/check-email" element={<CheckEmailPage />} />
        <Route path="/verify-email" element={<VerifyEmailPage />} />
        <Route path="/verify-email-change" element={<VerifyEmailChangePage />} />
        <Route path="/request-reset" element={<RequestResetPage />} />
        <Route path="/verify-reset" element={<VerifyResetPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/home" element={<HomePage />} />
        <Route path="/post/:postId" element={<PostDetailPage />} />
        <Route path="/profile/:username" element={<ProfilePage />} />
        <Route path="/tags/:tag" element={<TagPage />} />
        <Route path="/appeals" element={<AppealsPage />} />
        <Route path="/blocked" element={<BlockedUsersPage />} />
        <Route path="/saved" element={<SavedPostsPage />} />
        <Route path="/followers" element={<FollowListPage mode="followers" />} />
        <Route path="/following" element={<FollowListPage mode="following" />} />
        <Route path="/follow-requests" element={<FollowRequestsPage />} />
        <Route path="/privacy-policy" element={<PrivacyPolicyPage />} />
        <Route path="/terms-of-service" element={<TermsOfServicePage />} />
        {/* Apple's App Store listing needs a Support URL that works signed out. */}
        <Route path="/support" element={<SupportPage />} />
        <Route path="/delete-account" element={<DeleteAccountPage />} />
      </Routes>
    </PrivacyPolicyReacceptGate>
  )
}

export default App
