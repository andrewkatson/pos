plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
}

android {
    namespace = "com.example.positiveonlysocial"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.example.positiveonlysocial"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
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
    implementation(libs.s3)
    implementation(libs.cognitoidentity)
    implementation(libs.kotlinx.coroutines.core)
    implementation(libs.androidx.navigation.compose)
    implementation(libs.io.coil.compose)
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

val generateGvoConstants by tasks.registering {
    val headerFile = file("../../../ios/Positive Only Social/Positive Only Social/MultiPlatform/GVOConstants.h")
    val outputFile = file("src/main/java/gvo_constants/GvoConstants.kt")

    inputs.file(headerFile)
    outputs.file(outputFile)

    doLast {
        val lines = headerFile.readLines()
        val constants = mutableListOf<String>()

        val regexString = """static const char\* const (GVO_\w+)\s*=\s*"([^"]*)";""".toRegex()
        val regexInt = """static const int (GVO_\w+)\s*=\s*(\d+);""".toRegex()

        lines.forEach { line ->
            regexString.find(line)?.let { match ->
                constants.add("val ${match.groupValues[1]} = \"${match.groupValues[2]}\"")
            }
            regexInt.find(line)?.let { match ->
                constants.add("val ${match.groupValues[1]} = ${match.groupValues[2]}")
            }
        }

        outputFile.parentFile.mkdirs()
        outputFile.writeText("""
package gvo_constants

// GENERATED FROM GVOConstants.h - DO NOT EDIT MANUALLY

${constants.joinToString("\n")}
        """.trimIndent())
    }
}

tasks.withType<org.jetbrains.kotlin.gradle.tasks.KotlinCompile>().configureEach {
    dependsOn(generateGvoConstants)
}
