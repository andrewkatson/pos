package com.example.positiveonlysocial

import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.positiveonlysocial.api.StatefulStubbedAPI
import com.example.positiveonlysocial.di.DependencyProvider
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class StubbedApiConfigurationTest {
    @Test
    fun instrumentationUsesStubbedApi() {
        assertTrue(DependencyProvider.api is StatefulStubbedAPI)
    }
}
