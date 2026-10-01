plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("com.google.devtools.ksp")
}

android {
    namespace = "com.focusforge"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.focusforge"
        minSdk = 26
        targetSdk = 35
        versionCode = providers.environmentVariable("FOCUSFORGE_VERSION_CODE").map { it.toInt() }.orElse(1).get()
        versionName = providers.environmentVariable("FOCUSFORGE_VERSION_NAME").orElse("0.1.0").get()
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables.useSupportLibrary = true

        val backendUrl = providers.gradleProperty("focusforge.backendUrl")
            .orElse(providers.environmentVariable("FOCUSFORGE_BACKEND_URL"))
            .orElse("http://localhost:8080")
            .get()
            .replace("\"", "\\\"")
        buildConfigField("String", "BACKEND_BASE_URL", "\"$backendUrl\"")
    }

    signingConfigs {
        create("releaseEnv") {
            val storeFilePath = providers.environmentVariable("FOCUSFORGE_KEYSTORE").orNull
            val storePasswordValue = providers.environmentVariable("FOCUSFORGE_KEYSTORE_PASSWORD").orNull
            val keyAliasValue = providers.environmentVariable("FOCUSFORGE_KEY_ALIAS").orNull
            val keyPasswordValue = providers.environmentVariable("FOCUSFORGE_KEY_PASSWORD").orNull
            if (storeFilePath != null && storePasswordValue != null &&
                keyAliasValue != null && keyPasswordValue != null
            ) {
                storeFile = file(storeFilePath)
                storePassword = storePasswordValue
                keyAlias = keyAliasValue
                keyPassword = keyPasswordValue
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            signingConfig = signingConfigs.getByName("releaseEnv")
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions { jvmTarget = "17" }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    packaging.resources.excludes += "/META-INF/{AL2.0,LGPL2.1}"
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.12.01")
    implementation(composeBom)
    androidTestImplementation(composeBom)
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.navigation:navigation-compose:2.8.5")
    implementation("androidx.room:room-runtime:2.6.1")
    implementation("androidx.room:room-ktx:2.6.1")
    ksp("androidx.room:room-compiler:2.6.1")
    implementation("androidx.datastore:datastore-preferences:1.1.1")
    implementation("androidx.work:work-runtime-ktx:2.10.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.1")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.10.1")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}
