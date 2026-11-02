package com.charonsecurity.homora.work

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.charonsecurity.homora.HomoraApp
import com.charonsecurity.homora.MainActivity
import com.charonsecurity.homora.R
import com.charonsecurity.homora.data.ScanRepository
import com.charonsecurity.homora.net.Ipv4
import com.charonsecurity.homora.net.Scanner
import java.util.concurrent.TimeUnit

/**
 * The app's only background work, off unless the user turns on new-device
 * alerts. Runs at most once a day, and only on Wi-Fi while charging, so
 * Android schedules it when it costs the battery nothing.
 */
class NewDeviceWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val c = (applicationContext as HomoraApp).container
        if (!c.prefs.newDeviceAlerts.value) return Result.success()
        val lan = c.wifi.lanInfo() ?: return Result.success()
        if (!Ipv4.isPrivate(lan.selfIp)) return Result.success()
        c.store.awaitLoaded()
        val before = c.store.state.value
        if (before.lastScan == null) return Result.success() // nothing to compare against yet
        val outcome = try {
            Scanner(c.wifi::bindToWifi).scan(lan)
        } catch (_: Exception) {
            return Result.retry()
        }
        val newOnes = outcome.devices.filter { !it.isSelf && !it.isGateway && it.identityKey !in before.seenKeys && it.identityKey !in before.known }
        val report = com.charonsecurity.homora.checks.Checks.evaluate(outcome.devices, before.lastScan.wifi)
        c.store.update { ScanRepository.applyScan(it, outcome, report.findings, before.lastScan.wifi) }
        val blockedBack = outcome.devices.count { it.identityKey in before.blocked }
        if (newOnes.isNotEmpty()) notify(NOTIFICATION_ID, ctxPlural(R.plurals.notif_new_devices_title, newOnes.size), applicationContext.getString(R.string.notif_new_devices_text))
        if (blockedBack > 0) notify(BLOCKED_ID, ctxPlural(R.plurals.notif_blocked_title, blockedBack), applicationContext.getString(R.string.notif_blocked_text))
        return Result.success()
    }

    private fun ctxPlural(id: Int, n: Int) = applicationContext.resources.getQuantityString(id, n, n)

    private fun notify(id: Int, title: String, text: String) {
        val ctx = applicationContext
        if (android.os.Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) return
        val open = PendingIntent.getActivity(
            ctx, id, Intent(ctx, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP),
            PendingIntent.FLAG_IMMUTABLE,
        )
        val n = NotificationCompat.Builder(ctx, CHANNEL)
            .setSmallIcon(R.drawable.ic_stat_homora)
            .setContentTitle(title)
            .setContentText(text)
            .setContentIntent(open)
            .setAutoCancel(true)
            .build()
        try {
            NotificationManagerCompat.from(ctx).notify(id, n)
        } catch (_: SecurityException) {
        }
    }

    companion object {
        private const val NAME = "new-device-check"
        const val CHANNEL = "new_devices"
        private const val NOTIFICATION_ID = 1
        private const val BLOCKED_ID = 2

        fun createChannel(context: Context) {
            val ch = NotificationChannel(CHANNEL, context.getString(R.string.notif_channel_name), NotificationManager.IMPORTANCE_DEFAULT)
            context.getSystemService(NotificationManager::class.java).createNotificationChannel(ch)
        }

        fun schedule(context: Context, enabled: Boolean) {
            val wm = WorkManager.getInstance(context)
            if (!enabled) {
                wm.cancelUniqueWork(NAME)
                return
            }
            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.UNMETERED)
                .setRequiresCharging(true)
                .setRequiresBatteryNotLow(true)
                .build()
            val req = PeriodicWorkRequestBuilder<NewDeviceWorker>(1, TimeUnit.DAYS).setConstraints(constraints).build()
            wm.enqueueUniquePeriodicWork(NAME, ExistingPeriodicWorkPolicy.KEEP, req)
        }
    }
}
