package com.charonsecurity.homora.ui.devices

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.repeatOnLifecycle
import com.charonsecurity.homora.AppContainer
import com.charonsecurity.homora.R
import com.charonsecurity.homora.net.Ipv4
import com.charonsecurity.homora.net.Probe
import com.charonsecurity.homora.net.Scanner
import com.charonsecurity.homora.telemetry.Telemetry
import com.charonsecurity.homora.ui.components.DetailScaffold
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

private enum class Watch { STARTING, WATCHING, GONE, CANT_WATCH }

/**
 * "Unplug things one at a time and I'll tell you": watches one device and
 * reports when it stops answering. Runs only while this screen is open.
 */
@Composable
fun IdentifyScreen(container: AppContainer, key: String, onBack: () -> Unit) {
    val app by container.store.state.collectAsStateWithLifecycle()
    val device = remember(key, app.lastScan) { app.lastScan?.devices?.firstOrNull { it.identityKey == key } }
    var watch by remember { mutableStateOf(Watch.STARTING) }
    var naming by remember { mutableStateOf(false) }
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    val scope = rememberCoroutineScope()

    LaunchedEffect(device?.ip) {
        val ip = device?.ip?.let(Ipv4::parse) ?: return@LaunchedEffect
        lifecycle.repeatOnLifecycle(Lifecycle.State.STARTED) {
            // Coming back to the screen after the device went away must keep that result.
            if (watch == Watch.GONE || watch == Watch.CANT_WATCH) return@repeatOnLifecycle
            val port = device.watchablePort() ?: withContext(Dispatchers.IO) {
                Scanner.SWEEP_PORTS.firstOrNull { Probe.tcp(ip, it, 600) != Probe.PortState.NO_ANSWER }
            }
            if (port == null) {
                watch = Watch.CANT_WATCH
                return@repeatOnLifecycle
            }
            watch = Watch.WATCHING
            var misses = 0
            while (watch == Watch.WATCHING) {
                val answered = withContext(Dispatchers.IO) { Probe.tcp(ip, port, 1200) != Probe.PortState.NO_ANSWER }
                misses = if (answered) 0 else misses + 1
                if (misses >= 2) {
                    watch = Watch.GONE
                    Telemetry.identifyHelperUsed(true)
                    break
                }
                delay(3000)
            }
        }
    }

    DetailScaffold(stringResource(R.string.identify_title), onBack) { padding ->
        Column(Modifier.padding(padding).fillMaxSize().padding(24.dp)) {
            if (device == null) return@Column
            val name = deviceName(device, app)
            when (watch) {
                Watch.STARTING, Watch.WATCHING -> {
                    Text(stringResource(R.string.identify_body), style = MaterialTheme.typography.bodyLarge)
                    Spacer(Modifier.height(24.dp))
                    Text(stringResource(R.string.identify_watching, name), style = MaterialTheme.typography.titleMedium)
                    Spacer(Modifier.height(12.dp))
                    LinearProgressIndicator(Modifier.fillMaxWidth())
                }
                Watch.GONE -> {
                    Text(stringResource(R.string.identify_gone), style = MaterialTheme.typography.headlineSmall)
                    Spacer(Modifier.height(8.dp))
                    Text(stringResource(R.string.identify_gone_body), style = MaterialTheme.typography.bodyLarge)
                    Spacer(Modifier.height(24.dp))
                    Button(onClick = { naming = true }) { Text(stringResource(R.string.detail_mark_known)) }
                }
                Watch.CANT_WATCH -> Text(stringResource(R.string.identify_cant_watch), style = MaterialTheme.typography.bodyLarge)
            }
        }
        if (naming && device != null) {
            NameDialog(
                initial = app.known[key]?.label.orEmpty(),
                onDismiss = { naming = false },
                onSave = { label ->
                    naming = false
                    scope.launch { container.store.setKnown(key, label) }
                    Telemetry.deviceMarkedKnown()
                    onBack()
                },
            )
        }
    }
}
