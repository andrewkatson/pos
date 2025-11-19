package com.example.positiveonlysocial.api

import com.example.positiveonlysocial.data.model.*
import retrofit2.Response
import retrofit2.http.*

interface PositiveOnlySocialAPI {

    // =============================================================================
    // AUTHENTICATION
    // =============================================================================

    @POST("register")
    suspend fun register(@Body request: RegisterRequest): Response<AuthResponse>

    ): Response<List<CommentThreadDto>>

    @GET("get_comments_for_thread/{thread_identifier}")
    suspend fun getCommentsForThread(
        @Path("thread_identifier") threadId: String,
        @Query("batch") batch: Int
    ): Response<List<CommentDto>>

    // =============================================================================
    // USER / PROFILE
    // =============================================================================

    @GET("get_users_matching_fragment/{fragment}")
    @GET("get_users_matching_fragment/{fragment}")
    suspend fun searchUsers(
        @Header("Authorization") token: String,
        @Path("fragment") fragment: String
    ): Response<List<UserSearchDto>>

    @POST("follow_user/{username}")
    @POST("follow_user/{username}")
    suspend fun followUser(
        @Header("Authorization") token: String,
        @Path("username") username: String
    ): Response<GenericResponse>

    @POST("unfollow_user/{username}")
    @POST("unfollow_user/{username}")
    suspend fun unfollowUser(
        @Header("Authorization") token: String,
        @Path("username") username: String
    ): Response<GenericResponse>

    @GET("get_profile_details/{username}")
    @GET("get_profile_details/{username}")
    suspend fun getProfileDetails(
        @Header("Authorization") token: String,
        @Path("username") username: String
    ): Response<ProfileDto>
}