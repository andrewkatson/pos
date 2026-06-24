# Whether a verification report has been run at all
# for a user
NEVER_RUN = "never_run"

# Types of bans that can be applied to a user
BAN_TYPE_OUTRIGHT = "outright"
BAN_TYPE_SHADOW = "shadow"

# Why a post or comment is hidden. Empty string means no hide reason is
# recorded — the content may still be hidden (e.g. report-based hiding that
# predates this field) but without a recorded cause. "reports" is set when
# enough users report it; "classifier" is set when the AI classifier rejected
# it but the rejection is appealable.
HIDDEN_REASON_NONE = ""
HIDDEN_REASON_REPORTS = "reports"
HIDDEN_REASON_CLASSIFIER = "classifier"

# Lifecycle of an appeal a user files against hidden content or a ban.
APPEAL_STATUS_PENDING = "pending"
APPEAL_STATUS_APPROVED = "approved"
APPEAL_STATUS_DENIED = "denied"

# What an appeal can target.
APPEAL_TARGET_POST = "post"
APPEAL_TARGET_COMMENT = "comment"
APPEAL_TARGET_BAN = "ban"
APPEAL_TARGET_TYPES = (APPEAL_TARGET_POST, APPEAL_TARGET_COMMENT, APPEAL_TARGET_BAN)

# Error code returned when an outright-banned user attempts to authenticate
ACCOUNT_BANNED = "account_banned"

# Regex Patterns to check against
class Patterns:
    password = r"^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])(?=.*[@#$%^&+=_])(?=\S+$).{8,}$"
    double = r"^\d{1,100}[.,]{0,1}\d{0,100}$"
    paragraph_of_chars = r"^[\w \n]{5,3000}$"
    alphanumeric = r"^\w{10,500}$"
    short_alphanumeric = r"^\w{3,500}$"
    single_letter = r"^[a-zA-Z]{1}$"
    name = r"^[a-zA-Z]{3,100}$"
    digits_only = r"^\d{1,100}$"
    slash_date = r"[\d+/]{3,100}$"
    digits_and_dashes = r"^[\d-]{3,100}$"
    phone_number = r"^(\+\d{1,2}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}$"
    alphanumeric_with_spaces = r"^[\w ]{5,100}$"
    email = r"^[^@]+@[^@]+\.[^@]+$"
    uuid4 = r"^[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{15}\Z$"
    boolean = r"^(?i)(true|false)$"
    json_dict_of_upper_and_lower_case_chars = r"^[\]\[{}:\"\\, a-zA-Z]{2,5000}$"
    ipv6 = r"(([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(:[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(ffff(:0{1,4}){0,1}:){0,1}((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])|([0-9a-fA-F]{1,4}:){1,4}:((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9]))"
    ipv4 = r"^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)\.?\b){4}$"
    image_url = (
        r"^https://(?:(?:[A-Za-z0-9.-]+)\.s3(?:[.-][a-z0-9-]+)?\.amazonaws\.com/"
        r"|s3(?:[.-][a-z0-9-]+)?\.amazonaws\.com/[A-Za-z0-9.-]+/)[^\s?#]+(?:\?[^\s#]*)?$"
    )
    alphanumeric_with_special_chars = r"^[\w\W]+$"

class Params:
    username = "USERNAME"
    email = "EMAIL"
    password = "PASSWORD"
    username_or_email = f"{username}_OR_{email}"
    user_id = "USER_ID"
    image_url = "IMAGE_URL"
    comment = "COMMENT"
    reset_token = "RESET_TOKEN"
    verification_token = "VERIFICATION_TOKEN"
    ip = "IP"
    session_management_token = "SESSION_MANAGEMENT_TOKEN"
    series_identifier = "SERIES_IDENTIFIER"
    login_cookie_token = "LOGIN_COOKIE_TOKEN"
    remember_me = "REMEMBER_ME"
    caption = "CAPTION"
    image = "IMAGE_URL"
    post_identifier = "POST_IDENTIFIER"
    reason = "REASON"
    comment_text = "COMMENT_TEXT"
    comment_thread_identifier = "COMMENT_THREAD_IDENTIFIER"
    comment_identifier = "COMMENT_IDENTIFIER"
    username_fragment = "USERNAME_FRAGMENT"

class Fields:
    is_adult = 'is_adult'
    user_id = "user_id"
    series_identifier = "series_identifier"
    login_cookie_token = "login_cookie_token"
    session_management_token = "session_management_token"
    post_identifier = "post_identifier"
    image_url = "image_url"
    caption = "caption"
    post_likes = "post_likes"
    comment_thread_identifier = "comment_thread_identifier"
    comment_identifier = "comment_identifier"
    username = "username"
    post_count = "post_count"
    following_count = "following_count"
    follower_count = "follower_count"
    is_following = "is_following"
    is_liked = "is_liked"
    author_username = "author_username"
    email = "email"
    password = "password"
    remember_me = "remember_me"
    ip = "ip"
    username_or_email = "username_or_email"
    reason = "reason"
    comment_text = "comment_text"
    body = "body"
    creation_time = "creation_time"
    updated_time = "updated_time"
    comment_likes = "comment_likes"
    identity_is_verified = "identity_is_verified"
    reset_token = "reset_token"
    verification_token = "verification_token"
    hidden = "hidden"
    hidden_reason = "hidden_reason"
    appeal_identifier = "appeal_identifier"
    status = "status"
    resolution_note = "resolution_note"
    resolved_time = "resolved_time"
    content_snapshot = "content_snapshot"
    target_type = "target_type"
    target_identifier = "target_identifier"
    has_appeal = "has_appeal"

# Lengths of things
LEN_LOGIN_COOKIE_TOKEN = 32
LEN_SESSION_MANAGEMENT_TOKEN = 32

# Size of post batches
POST_BATCH_SIZE = 10

# Size of comment batches
COMMENT_BATCH_SIZE = 30

# Size of comment thread batches
COMMENT_THREAD_BATCH_SIZE = 10

# Maximum lengths for user-authored text, counted as unicode code points
# (Python's len() on a str is code-point based, so these limits are unicode
# aware rather than restricted to ASCII bytes).
MAX_CAPTION_LENGTH = 125
MAX_COMMENT_LENGTH = 500
MAX_APPEAL_REASON_LENGTH = 1000

# Number of reports before hiding
MAX_BEFORE_HIDING_POST = 10
MAX_BEFORE_HIDING_COMMENT = 5

# verify_reset lockout: lock the account after this many consecutive failures
VERIFY_RESET_MAX_ATTEMPTS = 5
VERIFY_RESET_LOCKOUT_MINUTES = 15
