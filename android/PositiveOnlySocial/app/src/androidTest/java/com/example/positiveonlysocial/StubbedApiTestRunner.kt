package com.example.positiveonlysocial

import android.app.Application
import android.content.Context
import androidx.test.runner.AndroidJUnitRunner
import com.example.positiveonlysocial.di.DependencyProvider

class StubbedApiTestRunner : AndroidJUnitRunner() {
    override fun newApplication(cl: ClassLoader?, className: String?, context: Context?): Application {
        DependencyProvider.isUITesting = true
        return super.newApplication(cl, className, context)
    }
}
