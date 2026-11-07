import java.time.Duration

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
}

// google-services.json is kept out of git (see README). Without it the app
// still builds and runs; analytics, crash reports and feedback are disabled.
val hasFirebaseConfig = file("google-services.json").exists()
if (hasFirebaseConfig) {
    apply(plugin = "com.google.gms.google-services")
    apply(plugin = "com.google.firebase.crashlytics")
}

android {
    namespace = "com.charonsecurity.homora"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.charonsecurity.homora"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0"
    }

    flavorDimensions += "distribution"
    productFlavors {
        // Google Play / sideload build: Firebase analytics, crash reports and feedback.
        create("play") {
            dimension = "distribution"
            buildConfigField("boolean", "FIREBASE", hasFirebaseConfig.toString())
        }
        // F-Droid build: no Google or other proprietary libraries, no network features.
        create("foss") {
            dimension = "distribution"
            buildConfigField("boolean", "FIREBASE", "false")
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            // There is no upload key in the repo, so the optimised build is signed with the
            // debug key and can be installed straight from CI for testing. Swap in your
            // Play upload key before publishing to the store.
            signingConfig = signingConfigs.getByName("debug")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    testOptions {
        unitTests {
            isReturnDefaultValues = true
            isIncludeAndroidResources = true
            all {
                // Screenshots of real screens (SnapshotTest) are written only on request:
                //   ./gradlew testPlayDebugUnitTest -Psnapshots
                it.systemProperty("roborazzi.test.record", project.hasProperty("snapshots").toString())
                it.systemProperty("robolectric.pixelCopyRenderMode", "hardware")
                // Name each test in the log and fail a stuck run instead of hanging CI.
                it.testLogging { events("started", "passed", "failed", "skipped") }
                it.timeout.set(Duration.ofMinutes(15))
            }
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}

// Flavor + build-type configurations are only created after configuration, so declare this one up front.
configurations.maybeCreate("playDebugImplementation")

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.core.splashscreen)
    implementation(libs.androidx.profileinstaller)
    implementation(libs.androidx.activity.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.material.icons)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.navigation.compose)
    implementation(libs.androidx.work.runtime)
    implementation(libs.kotlinx.coroutines.android)
    "playImplementation"(libs.kotlinx.coroutines.play.services)
    implementation(libs.kotlinx.serialization.json)

    "playImplementation"(platform(libs.firebase.bom))
    "playImplementation"(libs.firebase.analytics)
    "playImplementation"(libs.firebase.crashlytics)
    "playImplementation"(libs.firebase.firestore)
    "playImplementation"(libs.firebase.auth)
    "playImplementation"(libs.firebase.appcheck.playintegrity)
    "playDebugImplementation"(libs.firebase.appcheck.debug)

    debugImplementation(libs.androidx.compose.ui.tooling)
    testImplementation(libs.junit)
    testImplementation(libs.kotlinx.coroutines.test)
    testImplementation(libs.robolectric)
    testImplementation(libs.roborazzi)
    testImplementation(libs.roborazzi.compose)
    testImplementation(libs.androidx.test.ext.junit)
    testImplementation(platform(libs.androidx.compose.bom))
    testImplementation(libs.androidx.compose.ui.test.junit4)
    debugImplementation(libs.androidx.compose.ui.test.manifest)
}
