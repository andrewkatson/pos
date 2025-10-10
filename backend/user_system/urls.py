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
    path('logout_user/<str:session_management_token>',
         views.logout_user, name='logout_user'),
    # Deletes the user if they exist
    path('delete_user/<str:session_management_token>',
         views.delete_user, name='delete_user'),
    # Make a post and stores the information about it
    path('make_post/<str:session_management_token>/<str:image_url>/<str:caption>', views.make_post, name='make_post'),
    # Delete a post
    path('delete_post/<str:session_management_token>/<str:post_identifier>',
         views.delete_post, name='delete_post'),
    # Report a post
    path('report_post/<str:session_management_token>/<str:post_identifier>/<str:reason>', views.report_post,
         name='report_post'),
    # Like a post
    path('like_post/<str:session_management_token>/<str:post_identifier>', views.like_post, name='like_post'),
    # Unlike a post
    path('unlike_post/<str:session_management_token>/<str:post_identifier>', views.unlike_post, name='unlike_post'),
    # Get all posts for the user's feed
    path('get_posts_in_feed/<str:session_management_token>/<int:batch>', views.get_posts_in_feed,
         name='get_posts_in_feed'),
    # Get posts for another user
    path('get_posts_for_user/<str:session_management_token>/<str:username>/<int:batch>', views.get_posts_for_user),
    # Gets posts for the user's "Following" feed
    path('get_followed_posts/<str:session_management_token>/<int:batch>',
         views.get_posts_for_followed_users,
         name='get_posts_for_followed_users'),
    # Get the details for a post
    path('get_post_details/<str:post_identifier>', views.get_post_details, name='get_post_details'),
    # Comment directly on a post
    path('comment_on_post/<str:session_management_token>/<str:post_identifier>/<str:comment_text>',
         views.comment_on_post, name='comment_on_post'),
    # Like a comment
    path(
        'like_comment/<str:session_management_token>/<str:post_identifier>/<str:comment_thread_identifier>/<str:comment_identifier>',
        views.like_comment, name='like_comment'),
    # Unlike a comment
    path(
        'unlike_comment/<str:session_management_token>/<str:post_identifier>/<str:comment_thread_identifier>/str:comment_identifier',
        views.unlike_comment, name='unlike_comment'),
    # Delete a comment
    path(
        'delete_comment/<str:session_management_token>/<str:post_identifier>/<str:comment_thread_identifier>/<str:comment_identifier>',
        views.delete_comment, name='delete_comment'),
    # Report a comment
    path(
        'report_comment/<str:session_management_token>/<str:post_identifier>/<str:comment_thread_identifier>/<str:comment_identifier>/<str:reason>',
        views.report_comment, name='report_comment'),
    # Get comments for a post
    path('get_comments_for_post/<str:post_identifier>/<int:batch>', views.get_comments_for_post,
         name='get_comments_for_post'),
    # Get the comments for a comment thread
    path('get_comments_for_thread/<str:comment_thread_identifier>/<int:batch>', views.get_comments_for_thread,
         name='get_comments_for_thread'),
    # Reply to a comment thread. This is basically like commenting a post but instead is underneath a comment
    path(
        'reply_to_comment_thread/<str:session_management_token>/<str:post_identifier>/<str:comment_thread_identifier>/<str:comment_text>',
        views.reply_to_comment_thread, name='reply_to_comment_thread'),
    # Get the users with a username matching the fragment passed
    path('get_users_matching_fragment/<str:session_management_token>/<str:username_fragment>',
         views.get_users_matching_fragment, name='get_users_matching_fragment'),
    # Follow and Unfollow users
    path('follow/<str:session_management_token>/<str:username_to_follow>',
         views.follow_user, name='follow_user'),

    path('unfollow/<str:session_management_token>/<str:username_to_unfollow>',
         views.unfollow_user, name='unfollow_user'),
]
