# Whether a verification report has been run at all
# for a user
NEVER_RUN = "never_run"

# Regex Patterns to check against
class Patterns:
    password = r"^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])(?=.*[@#$%^&+=_])(?=\S+$).{8,}$"
    double = r"^\d{1,100}[.,]{0,1}\d{0,100}$"
    paragraph_of_chars = r"^[\w \n]{5,3000}$"
    alphanumeric = r"^\w{10,500}$"
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
    reset_id = r"^\d{6}$"
    ipv6 = r"(([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(:[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(ffff(:0{1,4}){0,1}:){0,1}((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])|([0-9a-fA-F]{1,4}:){1,4}:((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9]))"
    ipv4 = r"^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)\.?\b){4}$"
    sql_injection = r"/[\t\r\n]|(--[^\r\n]*)|(\/\*[\w\W]*?(?=\*)\*\/)/gi"
    image_url = r"\.(jpg|jpeg|png|gif)$"

class Params:
    username = "USERNAME"
    email = "EMAIL"
    password = "PASSWORD"
    username_or_email = f"{username}_OR_{email}"
    user_id = "USER_ID"
    image_url = "IMAGE_URL"
    comment = "COMMENT"
    reset_id = "RESET_ID"
    ip = "IP"
    session_management_token = "SESSION_MANAGEMENT_TOKEN"
    series_identifier = "SERIES_IDENTIFIER"
    login_cookie_token = "LOGIN_COOKIE_TOKEN"
    remember_me = "REMEMBER_ME"
    caption = "CAPTION"
    image = "IMAGE_URL"
    post_identifier = "POST_IDENTIFIER"

class Fields:
    series_identifier = "series_identifier"
    login_cookie_token = "login_cookie_token"
    session_management_token = "session_management_token"

# Lengths of things
LEN_LOGIN_COOKIE_TOKEN = 32
LEN_SESSION_MANAGEMENT_TOKEN = 32
