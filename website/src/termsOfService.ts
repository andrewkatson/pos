/**
 * The terms of service, in one place (issue #493).
 *
 * Google's OAuth consent screen — and both app stores — require a publicly
 * reachable terms URL, so this text is rendered by the unauthenticated
 * /terms-of-service page as well as the in-app Settings modal. Keeping it here
 * means the two can never drift, exactly as `privacyPolicy.ts` does for the
 * privacy policy.
 */

export interface TermsSection {
  heading: string
  body: string
}

/** Shown on the page so a reader can tell which version they agreed to. */
export const TERMS_OF_SERVICE_LAST_UPDATED = 'August 13, 2026'

export const TERMS_OF_SERVICE_SECTIONS: TermsSection[] = [
  {
    heading: 'Agreeing to these terms',
    body:
      'Good Vibes Only is a positivity-only social network. By creating an account, signing in — including with Google — or otherwise using the website or the mobile apps, you agree to these terms. If you do not agree to them, please do not use the service.',
  },
  {
    heading: 'Who can use Good Vibes Only',
    body:
      'You must be at least 16 years old. Accounts belonging to 16- and 17-year-olds are kept in a separate visibility band from adult accounts, and the two never see each other’s posts, comments, or profiles. Give us accurate information, keep one account per person, and keep your password and any second factor to yourself — anything done from your account is treated as done by you. Tell us if you think someone else has got in.',
  },
  {
    heading: 'What you may post',
    body:
      'Every post, comment, username, bio, and photo has to be positive or neutral: no swearing, nudity, sexually suggestive material, gore, hate speech, harassment, bullying, or misinformation, and no photos of babies, children, or anyone under 18. Content that starts sad but ends on a happy or hopeful note is welcome. You must hold the rights to whatever you upload, and you may not impersonate anyone, spam, run bots, or try to break, overload, or reverse-engineer the service.',
  },
  {
    heading: 'How we moderate',
    body:
      'Submissions are checked automatically before they go up, and other users can report content and accounts. Anything that fails the guidelines is refused or hidden, and an account that breaks them can be warned, suspended for a time, banned permanently, or have its content hidden from other people without being told, where telling the holder would only help them evade enforcement. You can ask us to look again at anything of yours we hid from the “Hidden Content & Appeals” screen. Moderation is automated and imperfect in both directions, and the final call on what stays up is ours.',
  },
  {
    heading: 'Your content stays yours',
    body:
      'You keep ownership of everything you post. You give us permission to store, reproduce, and display it for the purpose of running the service and showing it to the audience you chose. That permission ends when the content is deleted, apart from copies still sitting in backups or anything we are required to keep by law.',
  },
  {
    heading: 'Signing in with Google',
    body:
      'If you sign in with Google, we receive the Google account’s verified email address and a permanent account identifier, and use them only to create or find your Good Vibes Only account. We never see your Google password and we ask for nothing else from your Google account. Your use of Google’s own services remains governed by Google’s terms and privacy policy; deleting your Good Vibes Only account ends the connection on our side.',
  },
  {
    heading: 'Ending your account',
    body:
      'You can delete your account at any time from Settings, or from the account & data deletion page on the website without opening an app. Deleting removes your posts and their images, comments, likes, saved posts, follows, blocks, appeals, and sessions, and cannot be undone. We may suspend or terminate an account that breaks these terms or the content guidelines.',
  },
  {
    heading: 'The service is provided as is',
    body:
      'Good Vibes Only is offered free of charge and as is, with no warranty of any kind. We may change, suspend, or discontinue any part of it, and to the fullest extent the law allows we are not liable for lost content or for any indirect or consequential loss. Nothing here takes away rights you have that cannot be given up under the law where you live.',
  },
  {
    heading: 'Changes to these terms',
    body:
      'These terms will change as the service does. The date above marks the current version, and continuing to use Good Vibes Only after an update means you accept the updated terms.',
  },
  {
    heading: 'Contact',
    body:
      'Questions about these terms, or anything else, can go to katsonsoftware@gmail.com.',
  },
]
