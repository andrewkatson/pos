from django.urls import path

from . import views

urlpatterns = [
    # Creates a user if does not exist
    path('register/<str:username>/<str:email>/<str:password>/<str:remember_me>/<str:ip>', views.register,
         name='register'),
    # Logs the user in if they exist
    path('login_user/<str:username_or_email>/<str:password>/<str:remember_me>/<str:ip>', views.login_user,
         name='login_user'),
    # Logs the user in with remember me set if the user's series identifier and login cookie token exist and match
    # what is on record
    path(
        'login_user_with_remember_me/<str:session_management_token>/<str:series_identifier>/<str:login_cookie_token>/<str:ip>',
        views.login_user,
        name='login_user_with_remember_me'),
    # Resets the user's password to the passed one. Assumes it has already been confirmed as the desired password.
    path('reset_password/<str:username>/<str:email>/<str:password>/', views.reset_password, name='reset_password'),
    # Requests a password reset and sends the user an email.
    path('request_reset/<str:username_or_email>/', views.request_reset, name='request_reset'),
    # Verify reset by checking that the reset identifier matches what was sent in the email.
    path('verify_reset/<str:username_or_email>/<int:reset_id>/', views.verify_reset, name='verify_reset'),
    # Logs the user out if they exist
    path('logout_user/<str:session_management_token>/<str:series_identifier>/<str:login_cookie_token>',
         views.logout_user, name='logout_user'),
    # Deletes the user if they exist
    path('delete_user/<str:session_management_token>/<str:series_identifier>/<str:login_cookie_token>',
         views.delete_user, name='delete_user'),
]
