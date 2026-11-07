package com.charonsecurity.homora.feedback

import android.os.Build
import com.charonsecurity.homora.BuildConfig

/**
 * Sends a feature idea or problem report to Firestore. The user is signed in
 * anonymously (no account, no login screen); only the text they typed, an
 * optional e-mail, and the app/Android version are stored. Firestore rules
 * (firestore.rules) let users create feedback but never read it back.
 */
class FeedbackRepository {

    val isAvailable: Boolean get() = BuildConfig.FIREBASE

    suspend fun send(isProblem: Boolean, text: String, email: String?): Result<Unit> = runCatching {
        check(BuildConfig.FIREBASE) { "Feedback is not configured in this build" }
        val trimmed = text.trim()
        require(trimmed.length in MIN_LENGTH..MAX_LENGTH)
        val doc = buildMap<String, Any> {
            put("type", if (isProblem) "problem" else "idea")
            put("text", trimmed)
            email?.trim()?.takeIf { it.isNotEmpty() }?.let { put("email", it.take(120)) }
            put("appVersion", BuildConfig.VERSION_NAME)
            put("androidSdk", Build.VERSION.SDK_INT)
        }
        FeedbackBackend.submit(doc)
    }

    companion object {
        const val MIN_LENGTH = 5
        const val MAX_LENGTH = 1000
    }
}
