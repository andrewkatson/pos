from django.urls import path
import logging
from . import views

logger = logging.getLogger(__name__)
logger.info("Initializing user_system URL routes")

urlpatterns = [
    # =========================================================================
    # AUTHENTICATION
    # =========================================================================
    # POST /register/
    path('register/', views.register, name='register'),

    # POST /verify-identity/ (Token in header)
    path('verify-identity/', views.verify_identity, name='verify_identity'),

    # POST /verify-email/
    path('verify-email/', views.verify_email, name='verify_email'),

    # POST /resend-verification-email/
    path('resend-verification-email/', views.resend_verification_email, name='resend_verification_email'),


    # POST /login/
    path('login/', views.login_user, name='login_user'),

    # POST /login/remember/
    path('login/remember/', views.login_user_with_remember_me, name='login_user_with_remember_me'),

    # POST /login/2fa/
    path('login/2fa/', views.login_user_2fa, name='login_user_2fa'),

    # POST /2fa/totp/setup/ (Token in header)
    path('2fa/totp/setup/', views.setup_totp, name='setup_totp'),

    # POST /2fa/totp/confirm/ (Token in header)
    path('2fa/totp/confirm/', views.confirm_totp, name='confirm_totp'),

    # POST /2fa/disable/ (Token in header)
    path('2fa/disable/', views.disable_totp, name='disable_totp'),

    # POST /logout/ (Token in header)
    path('logout/', views.logout_user, name='logout_user'),

    # POST /user/delete/ (Token in header)
    path('user/delete/', views.delete_user, name='delete_user'),

    # =========================================================================
    # PASSWORD RESET
    # =========================================================================
    # POST /password/request-reset/
    path('password/request-reset/', views.request_reset, name='request_reset'),

    # POST /password/verify-reset/
    path('password/verify-reset/', views.verify_reset, name='verify_reset'),

    # POST /password/reset/
    path('password/reset/', views.reset_password, name='reset_password'),

    # =========================================================================
    # POSTS
    # =========================================================================
    # POST /posts/upload-url/ (Token in header)
    path('posts/upload-url/', views.create_upload_url, name='create_upload_url'),

    # POST /posts/create/ (Token in header)
    path('posts/create/', views.make_post, name='make_post'),

    # GET /posts/<uuid:post_identifier>/status/ (Token in header)
    path('posts/<uuid:post_identifier>/status/', views.get_post_status, name='get_post_status'),

    # POST /posts/<uuid:post_identifier>/delete/ (Token in header)
    path('posts/<uuid:post_identifier>/delete/', views.delete_post, name='delete_post'),

    # POST /posts/<uuid:post_identifier>/report/ (Token in header)
    path('posts/<uuid:post_identifier>/report/', views.report_post, name='report_post'),

    # POST /posts/<uuid:post_identifier>/report/retract/ (Token in header)
    path('posts/<uuid:post_identifier>/report/retract/', views.retract_report_post, name='retract_report_post'),

    # POST /posts/<uuid:post_identifier>/like/ (Token in header)
    path('posts/<uuid:post_identifier>/like/', views.like_post, name='like_post'),

    # POST /posts/<uuid:post_identifier>/unlike/ (Token in header)
    path('posts/<uuid:post_identifier>/unlike/', views.unlike_post, name='unlike_post'),

    # =========================================================================
    # FEEDS & POST RETRIEVAL
    # =========================================================================
    # GET /feed/<int:batch>/ (Token in header)
    path('feed/<int:batch>/', views.get_posts_in_feed, name='get_posts_in_feed'),

    # GET /feed/followed/<int:batch>/ (Token in header)
    path('feed/followed/<int:batch>/', views.get_posts_for_followed_users, name='get_posts_for_followed_users'),

    # GET /users/<str:username>/posts/<int:batch>/ (Token in header)
    path('users/<str:username>/posts/<int:batch>/', views.get_posts_for_user, name='get_posts_for_user'),

    # GET /posts/<uuid:post_identifier>/details/
    path('posts/<uuid:post_identifier>/details/', views.get_post_details, name='get_post_details'),

    # =========================================================================
    # COMMENTS
    # =========================================================================
    # POST /posts/<uuid:post_identifier>/comment/ (Token in header)
    path('posts/<uuid:post_identifier>/comment/', views.comment_on_post, name='comment_on_post'),

    # POST /posts/<uuid:post_identifier>/threads/<uuid:comment_thread_identifier>/reply/ (Token in header)
    path('posts/<uuid:post_identifier>/threads/<uuid:comment_thread_identifier>/reply/',
         views.reply_to_comment_thread, name='reply_to_comment_thread'),

    # GET /posts/<uuid:post_identifier>/comments/<int:batch>/ (Token in header)
    path('posts/<uuid:post_identifier>/comments/<int:batch>/', views.get_comments_for_post,
         name='get_comments_for_post'),

    # GET /threads/<uuid:comment_thread_identifier>/comments/<int:batch>/ (Token in header)
    path('threads/<uuid:comment_thread_identifier>/comments/<int:batch>/', views.get_comments_for_thread,
         name='get_comments_for_thread'),

    # POST /.../comments/<uuid:comment_identifier>/like/ (Token in header)
    path(
        'posts/<uuid:post_identifier>/threads/<uuid:comment_thread_identifier>/comments/<uuid:comment_identifier>/like/',
        views.like_comment, name='like_comment'),

    # POST /.../comments/<uuid:comment_identifier>/unlike/ (Token in header)
    path(
        'posts/<uuid:post_identifier>/threads/<uuid:comment_thread_identifier>/comments/<uuid:comment_identifier>/unlike/',
        views.unlike_comment, name='unlike_comment'),

    # POST /.../comments/<uuid:comment_identifier>/delete/ (Token in header)
    path(
        'posts/<uuid:post_identifier>/threads/<uuid:comment_thread_identifier>/comments/<uuid:comment_identifier>/delete/',
        views.delete_comment, name='delete_comment'),

    # POST /.../comments/<uuid:comment_identifier>/report/ (Token in header)
    path(
        'posts/<uuid:post_identifier>/threads/<uuid:comment_thread_identifier>/comments/<uuid:comment_identifier>/report/',
        views.report_comment, name='report_comment'),

    # POST /.../comments/<uuid:comment_identifier>/report/retract/ (Token in header)
    path(
        'posts/<uuid:post_identifier>/threads/<uuid:comment_thread_identifier>/comments/<uuid:comment_identifier>/report/retract/',
        views.retract_report_comment, name='retract_report_comment'),

    # =========================================================================
    # USER & PROFILE
    # =========================================================================
    # GET /users/search/<str:username_fragment>/ (Token in header)
    path('users/search/<str:username_fragment>/', views.get_users_matching_fragment,
         name='get_users_matching_fragment'),

    # POST /users/<str:username_to_follow>/follow/ (Token in header)
    path('users/<str:username_to_follow>/follow/', views.follow_user, name='follow_user'),

    # POST /users/<str:username_to_unfollow>/unfollow/ (Token in header)
    path('users/<str:username_to_unfollow>/unfollow/', views.unfollow_user, name='unfollow_user'),

    # POST /users/<str:username_to_toggle_block>/block/ (Token in header)
    path('users/<str:username_to_toggle_block>/block/', views.toggle_block, name='toggle_block'),

    # GET /users/blocked/ (Token in header)
    path('users/blocked/', views.get_blocked_users, name='get_blocked_users'),

    # GET /users/followers/ (Token in header) — the requester's own followers
    path('users/followers/', views.get_followers, name='get_followers'),

    # GET /users/following/ (Token in header) — the requester's own following
    path('users/following/', views.get_following, name='get_following'),

    # GET /users/<str:username>/profile/ (Token in header)
    path('users/<str:username>/profile/', views.get_profile_details, name='get_profile_details'),

    # =========================================================================
    # APPEALS
    # =========================================================================
    # GET /appeals/hidden/posts/<int:batch>/ (Token in header)
    path('appeals/hidden/posts/<int:batch>/', views.get_hidden_posts, name='get_hidden_posts'),

    # GET /appeals/hidden/comments/<int:batch>/ (Token in header)
    path('appeals/hidden/comments/<int:batch>/', views.get_hidden_comments, name='get_hidden_comments'),

    # GET /appeals/mine/<int:batch>/ (Token in header)
    path('appeals/mine/<int:batch>/', views.get_my_appeals, name='get_my_appeals'),

    # POST /appeals/submit/ (Token in header)
    path('appeals/submit/', views.submit_appeal, name='submit_appeal'),
]