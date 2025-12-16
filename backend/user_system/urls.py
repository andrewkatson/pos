from django.urls import path
from . import views

urlpatterns = [
    # =========================================================================
    # AUTHENTICATION
    # =========================================================================
    # POST /register/
    path('register/', views.register, name='register'),

    # POST /verify-identity/ (Token in header)
    path('verify-identity/', views.verify_identity, name='verify_identity'),


    # POST /login/
    path('login/', views.login_user, name='login_user'),

    # POST /login/remember/
    path('login/remember/', views.login_user_with_remember_me, name='login_user_with_remember_me'),

    # POST /logout/ (Token in header)
    path('logout/', views.logout_user, name='logout_user'),

    # POST /user/delete/ (Token in header)
    path('user/delete/', views.delete_user, name='delete_user'),

    # =========================================================================
    # PASSWORD RESET
    # =========================================================================
    # POST /password/request-reset/
    path('password/request-reset/', views.request_reset, name='request_reset'),

    # GET /password/verify-reset/<username_or_email>/<reset_id>/
    path('password/verify-reset/<str:username_or_email>/<int:reset_id>/', views.verify_reset, name='verify_reset'),

    # POST /password/reset/
    path('password/reset/', views.reset_password, name='reset_password'),

    # =========================================================================
    # POSTS
    # =========================================================================
    # POST /posts/create/ (Token in header)
    path('posts/create/', views.make_post, name='make_post'),

    # POST /posts/<uuid:post_identifier>/delete/ (Token in header)
    path('posts/<uuid:post_identifier>/delete/', views.delete_post, name='delete_post'),

    # POST /posts/<uuid:post_identifier>/report/ (Token in header)
    path('posts/<uuid:post_identifier>/report/', views.report_post, name='report_post'),

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

    # GET /users/<str:username>/profile/ (Token in header)
    path('users/<str:username>/profile/', views.get_profile_details, name='get_profile_details'),
]