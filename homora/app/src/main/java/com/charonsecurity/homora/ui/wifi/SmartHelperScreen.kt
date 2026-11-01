package com.charonsecurity.homora.ui.wifi

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.charonsecurity.homora.AppContainer
import com.charonsecurity.homora.R
import com.charonsecurity.homora.ui.components.DetailScaffold
import com.charonsecurity.homora.ui.components.PlainCard
import com.charonsecurity.homora.wifi.Band
import com.charonsecurity.homora.wifi.WifiAnalysis
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext

@Composable
fun SmartHelperScreen(container: AppContainer, onBack: () -> Unit) {
    var report by remember { mutableStateOf<WifiAnalysis.SmartDeviceReport?>(null) }
    var noData by remember { mutableStateOf(false) }
    var refresh by remember { mutableIntStateOf(0) }

    LaunchedEffect(refresh) {
        report = null
        val (conn, aps) = withContext(Dispatchers.IO) {
            container.wifi.requestScan()
            delay(3000) // results arrive asynchronously; Android throttles scans anyway
            container.wifi.connection() to container.wifi.accessPoints()
        }
        noData = aps.isEmpty()
        report = conn?.let { WifiAnalysis.smartDevice(it, aps) }
    }

    DetailScaffold(stringResource(R.string.smart_title), onBack) { padding ->
        Column(Modifier.padding(padding).fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(stringResource(R.string.smart_intro), style = MaterialTheme.typography.bodyLarge)
            val r = report
            if (r == null) {
                CircularProgressIndicator()
                return@Column
            }
            Point(
                if (r.currentBand == Band.GHZ_2_4) stringResource(R.string.smart_band_24)
                else stringResource(R.string.smart_band_high, r.currentBand.label),
            )
            when (r.sharedNameAcrossBands) {
                true -> Point(stringResource(R.string.smart_shared_name))
                false -> Point(stringResource(R.string.smart_separate_names))
                null -> {}
            }
            val ours = r.neighboursOnOurChannel
            val quiet = r.quietestChannel
            val quietCount = r.quietestCount
            if (noData) {
                Point(stringResource(R.string.smart_no_data))
            } else if (ours != null && r.ourChannel24 != null && quiet != null && quietCount != null && ours >= 4 && quietCount < ours - 2 && quiet != r.ourChannel24) {
                Point(pluralStringResource(R.plurals.smart_crowded, ours, ours, r.ourChannel24, quiet, quietCount))
            } else if (ours != null) {
                Point(stringResource(R.string.smart_not_crowded))
            }
            Spacer(Modifier.height(8.dp))
            OutlinedButton(onClick = { refresh++ }) { Text(stringResource(R.string.smart_refresh)) }
        }
    }
}

@Composable
private fun Point(text: String) {
    PlainCard {
        Text(text, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(16.dp))
    }
}
