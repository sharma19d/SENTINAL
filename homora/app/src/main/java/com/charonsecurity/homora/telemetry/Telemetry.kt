package com.charonsecurity.homora.telemetry

import android.content.Context
import android.os.Bundle
import com.charonsecurity.homora.BuildConfig
import com.charonsecurity.homora.checks.FindingType
import com.google.firebase.analytics.FirebaseAnalytics
import com.google.firebase.crashlytics.FirebaseCrashlytics

/**
 * The only way the app reports usage. Every function takes counts or enums,
 * never strings, so a device name, address or network name cannot be logged
 * by accident. Counts are sent as ranges ("6-15"), not exact numbers.
 * Nothing is sent unless the user has opted in.
 */
object Telemetry {
    @Volatile
    private var analytics: FirebaseAnalytics? = null

    /** Runs on a background thread at startup; [consent] is read once Firebase is ready. */
    fun init(context: Context, consent: () -> Boolean) {
        if (!BuildConfig.FIREBASE) return
        analytics = FirebaseAnalytics.getInstance(context)
        setConsent(consent())
    }

    fun setConsent(on: Boolean) {
        if (!BuildConfig.FIREBASE) return
        analytics?.setAnalyticsCollectionEnabled(on)
        FirebaseCrashlytics.getInstance().isCrashlyticsCollectionEnabled = on
    }

    enum class ScanFailure { NO_WIFI, NOT_PRIVATE_NETWORK, ERROR }
    enum class Screen { DEVICES, SECURITY, WIFI, SETTINGS }

    fun onboardingDone(permissionGranted: Boolean) = log("onboarding_done", "permission" to permissionGranted.toString())

    fun permissionResult(granted: Boolean) = log("permission_result", "granted" to granted.toString())

    fun scanCompleted(durationMs: Long, devices: Int, unidentified: Int, findings: Int) = log(
        "scan_completed",
        "duration" to durationBucket(durationMs),
        "devices" to countBucket(devices),
        "unidentified" to countBucket(unidentified),
        "findings" to countBucket(findings),
    )

    fun scanFailed(reason: ScanFailure) = log("scan_failed", "reason" to reason.name.lowercase())

    fun findingShown(type: FindingType) = log("finding_shown", "type" to type.name.lowercase(), "severity" to type.severity.name.lowercase())
    fun findingDisputed(type: FindingType) = log("finding_disputed", "type" to type.name.lowercase())
    fun fixGuideOpened(type: FindingType) = log("fix_guide_opened", "type" to type.name.lowercase())
    fun guideHelpful(type: FindingType, helpful: Boolean) = log("guide_feedback", "type" to type.name.lowercase(), "helpful" to helpful.toString())

    fun deviceMarkedKnown() = log("device_marked_known")
    fun identifyHelperUsed(found: Boolean) = log("identify_helper", "found" to found.toString())
    fun lockoutGuideOpened() = log("lockout_guide_opened")

    fun meterSession(durationMs: Long, spotsSaved: Int, soundUsed: Boolean) = log(
        "meter_session", "duration" to durationBucket(durationMs), "spots" to countBucket(spotsSaved), "sound" to soundUsed.toString(),
    )
    fun smartHelperOpened() = log("smart_helper_opened")

    fun newDeviceAlerts(enabled: Boolean) = log("new_device_alerts", "enabled" to enabled.toString())
    fun feedbackSent(isProblem: Boolean) = log("feedback_sent", "type" to if (isProblem) "problem" else "idea")

    internal fun countBucket(n: Int): String = when {
        n <= 0 -> "0"
        n <= 5 -> "1-5"
        n <= 15 -> "6-15"
        n <= 30 -> "16-30"
        n <= 60 -> "31-60"
        else -> "60+"
    }

    internal fun durationBucket(ms: Long): String = when {
        ms < 10_000 -> "<10s"
        ms < 30_000 -> "10-30s"
        ms < 60_000 -> "30-60s"
        ms < 300_000 -> "1-5m"
        else -> "5m+"
    }

    private fun log(event: String, vararg params: Pair<String, String>) {
        val a = analytics ?: return
        a.logEvent(event, Bundle().apply { params.forEach { (k, v) -> putString(k, v) } })
    }
}
