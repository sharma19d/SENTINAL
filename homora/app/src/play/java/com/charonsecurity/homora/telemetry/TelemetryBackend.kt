package com.charonsecurity.homora.telemetry

import android.content.Context
import android.os.Bundle
import com.google.firebase.analytics.FirebaseAnalytics
import com.google.firebase.crashlytics.FirebaseCrashlytics

internal object TelemetryBackend {
    @Volatile
    private var analytics: FirebaseAnalytics? = null

    fun init(context: Context) {
        analytics = FirebaseAnalytics.getInstance(context)
    }

    fun setEnabled(on: Boolean) {
        analytics?.setAnalyticsCollectionEnabled(on)
        FirebaseCrashlytics.getInstance().isCrashlyticsCollectionEnabled = on
    }

    fun log(event: String, params: Map<String, String>) {
        val a = analytics ?: return
        a.logEvent(event, Bundle().apply { params.forEach { (k, v) -> putString(k, v) } })
    }
}
