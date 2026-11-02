package com.charonsecurity.homora.data

import android.content.Context
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** Small settings, kept in SharedPreferences and exposed as flows for the UI. */
class Prefs(context: Context) {
    private val sp = context.getSharedPreferences("homora_prefs", Context.MODE_PRIVATE)

    private val _onboarded = MutableStateFlow(sp.getBoolean(ONBOARDED, false))
    private val _analytics = MutableStateFlow(sp.getBoolean(ANALYTICS, false))
    private val _alerts = MutableStateFlow(sp.getBoolean(ALERTS, false))
    private val _sound = MutableStateFlow(sp.getBoolean(SOUND, false))

    val onboarded: StateFlow<Boolean> = _onboarded.asStateFlow()
    val analytics: StateFlow<Boolean> = _analytics.asStateFlow()
    val newDeviceAlerts: StateFlow<Boolean> = _alerts.asStateFlow()
    val meterSound: StateFlow<Boolean> = _sound.asStateFlow()

    fun setOnboarded() = put(ONBOARDED, _onboarded, true)
    fun setAnalytics(on: Boolean) = put(ANALYTICS, _analytics, on)
    fun setNewDeviceAlerts(on: Boolean) = put(ALERTS, _alerts, on)
    fun setMeterSound(on: Boolean) = put(SOUND, _sound, on)

    private fun put(key: String, flow: MutableStateFlow<Boolean>, value: Boolean) {
        flow.value = value
        sp.edit().putBoolean(key, value).apply() // apply() writes on a background thread
    }

    private companion object {
        const val ONBOARDED = "onboarded"
        const val ANALYTICS = "analytics"
        const val ALERTS = "new_device_alerts"
        const val SOUND = "meter_sound"
    }
}
