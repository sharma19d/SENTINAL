package com.charonsecurity.homora.ui.onboarding

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Insights
import androidx.compose.material.icons.outlined.LocationOn
import androidx.compose.material.icons.outlined.Lock
import androidx.compose.material.icons.outlined.Wifi
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.charonsecurity.homora.AppContainer
import com.charonsecurity.homora.R
import com.charonsecurity.homora.telemetry.Telemetry
import com.charonsecurity.homora.ui.components.hasWifiDetailPermission
import com.charonsecurity.homora.ui.components.wifiDetailPermissions

@Composable
fun OnboardingScreen(container: AppContainer) {
    val context = LocalContext.current
    var page by rememberSaveable { mutableIntStateOf(0) }
    var granted by rememberSaveable { mutableStateOf(hasWifiDetailPermission(context)) }
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) {
        granted = hasWifiDetailPermission(context)
        page = 2
    }

    fun finish(shareUsage: Boolean) {
        container.prefs.setAnalytics(shareUsage)
        Telemetry.setConsent(shareUsage)
        Telemetry.onboardingDone(granted)
        container.prefs.setOnboarded()
    }

    Surface(Modifier.fillMaxSize()) {
        Column(Modifier.safeDrawingPadding().padding(24.dp).fillMaxSize()) {
            Column(Modifier.weight(1f).verticalScroll(rememberScrollState())) {
                Spacer(Modifier.height(48.dp))
                when (page) {
                    0 -> {
                        Page(Icons.Outlined.Wifi, stringResource(R.string.onb1_title), stringResource(R.string.onb1_body))
                        Spacer(Modifier.height(32.dp))
                        Page(Icons.Outlined.Lock, stringResource(R.string.onb_privacy_title), stringResource(R.string.onb_privacy_body), small = true)
                    }
                    1 -> Page(Icons.Outlined.LocationOn, stringResource(R.string.onb2_title), stringResource(R.string.onb2_body))
                    else -> Page(Icons.Outlined.Insights, stringResource(R.string.onb3_title), stringResource(R.string.onb3_body))
                }
            }
            Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                when (page) {
                    0 -> Button(onClick = { page = if (granted) 2 else 1 }, modifier = Modifier.fillMaxWidth()) {
                        Text(stringResource(R.string.onb_continue))
                    }
                    1 -> {
                        Button(onClick = { launcher.launch(wifiDetailPermissions()) }, modifier = Modifier.fillMaxWidth()) {
                            Text(stringResource(R.string.onb2_allow))
                        }
                        TextButton(onClick = { page = 2 }, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.onb2_skip)) }
                    }
                    else -> {
                        Button(onClick = { finish(true) }, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.onb3_yes)) }
                        TextButton(onClick = { finish(false) }, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.onb3_no)) }
                    }
                }
            }
        }
    }
}

@Composable
private fun Page(icon: ImageVector, title: String, body: String, small: Boolean = false) {
    Icon(icon, null, Modifier.size(if (small) 28.dp else 40.dp), tint = MaterialTheme.colorScheme.primary)
    Spacer(Modifier.height(16.dp))
    Text(title, style = if (small) MaterialTheme.typography.titleMedium else MaterialTheme.typography.headlineSmall)
    Spacer(Modifier.height(8.dp))
    Text(body, style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
}
