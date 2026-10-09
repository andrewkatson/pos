# Age and identity

The service is closed to under-16s, and adults and permitted minors are kept
apart. Age comes from a date of birth supplied at registration or later via
identity verification (`verify_identity`); the model keeps two derived flags
rather than the raw date — `identity_is_verified` (an age was given) and
`is_adult` (that age was 18 or older). The age thresholds live in
`backend/user_system/constants.py` (`MINIMUM_AGE = 16`, `ADULT_AGE = 18`).

Three rules follow from this:

1. **No under-16s (issue #337).** Registration and `verify_identity` refuse
   anyone who supplies a date of birth showing an age below `MINIMUM_AGE`:
   register returns `403` with `reason_code: "age_restricted"` and creates no
   account; `verify_identity` returns the same and leaves the account
   unverified. Because under-16s are turned away here, any account that *is*
   identity-verified but not an adult is necessarily 16 or 17 — a "permitted
   minor". A date of birth is still optional at registration; an account
   created without one is simply left unverified (and treated as an adult for
   the segregation below, since its age is unknown).

2. **Adults and minors are mutually invisible (issue #329).** Permitted minors
   (16-17) form one visibility band and everyone else — adults plus
   unverified accounts — forms the other. The two bands never see each other's
   posts, comments, profiles, or search results, and cannot follow across the
   divide. This is enforced centrally in
   `backend/user_system/visibility.py` (`is_minor` / `in_same_age_band` and the
   `visible_posts` / `visible_comments` / `searchable_users` / `can_view_post`
   helpers), so every content path inherits it; cross-band profile and follow
   attempts return the same "not found" / "does not exist" response as a
   genuinely missing user so neither side can confirm the other by name. An
   account always sees its own content.

3. **No photos of babies or children (issue #336).** Even a permitted adult may
   not post images of minors. This is content rule 9
   (`backend/user_system/classifiers/classifier_constants.py`): the image
   classifier rejects photos or images of babies, children, or anyone under 18,
   reported to the author with `reason_code: "minors"`.
