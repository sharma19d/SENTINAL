package com.charonsecurity.homora.telemetry

import android.content.Context

internal object TelemetryBackend {
    @Suppress("UNUSED_PARAMETER")
    fun init(context: Context) = Unit

    @Suppress("UNUSED_PARAMETER")
    fun setEnabled(on: Boolean) = Unit

    @Suppress("UNUSED_PARAMETER")
    fun log(event: String, params: Map<String, String>) = Unit
}
