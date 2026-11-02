package com.charonsecurity.homora

import android.app.Application
import com.charonsecurity.homora.data.Prefs
import com.charonsecurity.homora.data.ScanRepository
import com.charonsecurity.homora.data.Store
import com.charonsecurity.homora.feedback.FeedbackRepository
import com.charonsecurity.homora.telemetry.Telemetry
import com.charonsecurity.homora.wifi.WifiReader
import com.charonsecurity.homora.work.NewDeviceWorker

/** Hand-wired dependencies; the app is small enough not to need a DI framework. */
class AppContainer(app: Application) {
    val prefs = Prefs(app)
    val store = Store(app)
    val wifi = WifiReader(app)
    val scans = ScanRepository(store, wifi)
    val feedback = FeedbackRepository()
}

class HomoraApp : Application() {
    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
        // None of this is needed for the first frame, so it runs off the main thread
        // instead of delaying the app's start.
        Thread({
            runCatching {
                if (BuildConfig.FIREBASE) AppCheckSetup.install()
                Telemetry.init(this) { container.prefs.analytics.value }
            }
            runCatching { NewDeviceWorker.createChannel(this) }
        }, "homora-init").apply { priority = Thread.NORM_PRIORITY - 1 }.start()
    }
}
