from xml.dom.expatbuilder import TEXT_NODE

username = 'andrewkatson'
invalid_username = '?'
email = 'andrewkatson'
invalid_email = '?'
password = 'somepassword%9A'
invalid_password = ''
invalid_bool = '?'
ip = '127.0.0.1'
invalid_ip = '?'
false = False
true = True

FAIL = 400
SUCCESS = 200
FORBIDDEN = 404

LOGIN_USER = 'login_user'
LOGIN_USER_WITH_REMEMBER_ME = 'login_user_with_remember_me'

# These paths must match the import locations in views.py file
IMAGE_CLASSIFIER_PATH = 'user_system.views.image_classifier'
TEXT_CLASSIFIER_PATH = 'user_system.views.text_classifier'

# This is the path to the feed_algorithm imported in views.py
FEED_ALGORITHM_PATH = 'user_system.views.feed_algorithm'

# Fields of a user
class UserFields:
    USERNAME = 'username'
    PASSWORD = 'password'
    EMAIL = 'email'
    SESSION_MANAGEMENT_TOKEN = 'session_management_token'
    SERIES_IDENTIFIER = 'series_identifier'
    LOGIN_COOKIE_TOKEN = 'login_cookie_token'
    POSTS = 'posts'
    TOKEN = 'token'
