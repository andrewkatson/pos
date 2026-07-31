plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
}

android {
    namespace = "com.example.positiveonlysocial"
    compileSdk = 36

    defaultConfig {
        applicationId = "io.github.andrewkatson.positiveonlysocial"
        minSdk = 26
        targetSdk = 36
        versionCode = 7
        versionName = "1.01.06"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        // FCM-for-Android push (issues #342/#343). These are the (public)
        // Firebase project identifiers; supply them via -P/gradle.properties to
        // enable push. When any is empty the app initializes no FirebaseApp and
        // push is a no-op — so no google-services.json (and no google-services
        // plugin) is required to build, and CI stays green without one.
        buildConfigField("String", "FCM_PROJECT_ID", "\"${project.findProperty("FCM_PROJECT_ID") ?: ""}\"")
        buildConfigField("String", "FCM_APPLICATION_ID", "\"${project.findProperty("FCM_APPLICATION_ID") ?: ""}\"")
        buildConfigField("String", "FCM_API_KEY", "\"${project.findProperty("FCM_API_KEY") ?: ""}\"")
        buildConfigField("String", "FCM_SENDER_ID", "\"${project.findProperty("FCM_SENDER_ID") ?: ""}\"")
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            resValue("string", "is_debug", "false")
        }
        debug {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            resValue("string", "is_debug", "true")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
    kotlinOptions {
        jvmTarget = "11"
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    testOptions {
        unitTests.isReturnDefaultValues = true
    }
}

dependencies {

    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.ui)
    implementation(libs.androidx.ui.graphics)
    implementation(libs.androidx.ui.tooling.preview)
    implementation(libs.androidx.material3)
    implementation(libs.gson)
    implementation(libs.retrofit)
    implementation(libs.converter.gson)
    implementation(libs.androidx.security.crypto)
    implementation(libs.kotlinx.coroutines.core)
    implementation(libs.androidx.navigation.compose)
    implementation(platform(libs.firebase.bom))
    implementation(libs.firebase.messaging)
    implementation(libs.io.coil.compose)
    implementation(libs.zxing.core)
    implementation(libs.androidx.material.icons.extended)
    testImplementation(libs.junit)
    testImplementation(libs.mockito.core)
    testImplementation(libs.mockito.kotlin)
    testImplementation(libs.byte.buddy)
    testImplementation(libs.kotlinx.coroutines.test)
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.ui.test.junit4)
    debugImplementation(libs.androidx.ui.tooling)
    debugImplementation(libs.androidx.ui.test.manifest)
}