package com.charonsecurity.homora.feedback

internal object FeedbackBackend {
    @Suppress("UNUSED_PARAMETER", "RedundantSuspendModifier")
    suspend fun submit(doc: Map<String, Any>) {
        error("Feedback is not available in the F-Droid build")
    }
}
