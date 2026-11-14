/**
 * Support contact details, in one place.
 *
 * Apple requires every App Store listing to carry a Support URL, and the page
 * behind it has to work for someone who is not signed in — a suspended user,
 * or somebody deciding whether to install the app at all. So this text is
 * rendered by the unauthenticated /support page as well as the in-app Settings
 * "Contact Us" row, the same way `termsOfService.ts` backs both the
 * /terms-of-service page and the in-app modal.
 */

/** Support address shown under "Contact Us" for feedback and help (issue #194). */
export const SUPPORT_EMAIL = 'katsonsoftware@gmail.com'

export interface SupportSection {
  heading: string
  body: string
}

export const SUPPORT_SECTIONS: SupportSection[] = [
  {
    heading: 'What to tell us',
    body:
      'Your username, which app you were using (iPhone, Android, or the website), and what you expected to happen instead. If something looks wrong on screen, a screenshot usually saves a round of questions. You do not need an account — or a working login — to write to us.',
  },
  {
    heading: 'Reporting a post or a comment',
    body:
      'Every post, comment, username, bio, and profile photo is checked by automated moderation before anyone else can see it, but nothing is perfect. If something got through, report it from the post or comment itself in any of the apps. A report sends that content back through moderation on its own merits; it is not a vote, so a single report is enough and piling on changes nothing. You can retract a report later.',
  },
  {
    heading: 'If your post or comment was hidden',
    body:
      'Most hidden content can be appealed from Appeals in the app: pick the hidden post or comment and say why you think it fits the guidelines. Anything still being checked has not been decided yet and will not be listed, and content moderation turned down outright is final and cannot be appealed. Each item gets one appeal, and you are emailed either way. An approved appeal puts the content back; when an appeal is denied, a post is deleted for good and a comment stays hidden.',
  },
  {
    heading: 'If your account was suspended',
    body:
      'The suspension email explains why, says whether it is temporary, and tells you how to reply to appeal it. Reply to that email, or write to the support address above from the address on the account.',
  },
  {
    heading: 'Account and data questions',
    body:
      'You can delete your account and everything attached to it yourself from the account and data deletion page. It signs you in first — username or email and password, plus your two-factor code if you use one — so that nobody else can delete an account that is not theirs. That sign-in is refused while an account is suspended or its email address was never verified, so if you are in either position, write to the support address above from the account’s own email and we will take care of the deletion for you. Write to us as well if you want to know what we hold about you or want a copy of it.',
  },
]
