package com.charonsecurity.homora.ui.devices

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.KeyboardArrowRight
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.charonsecurity.homora.AppContainer
import com.charonsecurity.homora.R
import com.charonsecurity.homora.net.Device
import com.charonsecurity.homora.telemetry.Telemetry
import com.charonsecurity.homora.ui.components.DetailScaffold
import com.charonsecurity.homora.ui.components.PlainCard
import com.charonsecurity.homora.ui.components.StatusDot
import com.charonsecurity.homora.ui.components.identitySource
import com.charonsecurity.homora.ui.components.label
import com.charonsecurity.homora.ui.components.portName
import com.charonsecurity.homora.ui.components.text
import com.charonsecurity.homora.ui.theme.LocalStatusColors
import kotlinx.coroutines.launch

@Composable
fun DeviceDetailScreen(container: AppContainer, key: String, onBack: () -> Unit, onIdentify: () -> Unit, onFinding: (String) -> Unit) {
    val app by container.store.state.collectAsStateWithLifecycle()
    val device = app.lastScan?.devices?.firstOrNull { it.identityKey == key }
    val scope = rememberCoroutineScope()
    var naming by rememberSaveable { mutableStateOf(false) }

    DetailScaffold(device?.let { deviceName(it, app) } ?: "", onBack) { padding ->
        if (device == null) return@DetailScaffold
        val known = app.known[key]
        val findings = app.lastScan?.findings.orEmpty().filter { it.deviceKey == key }
        Column(Modifier.padding(padding).fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp)) {
            if (!device.isSelf && !device.isGateway) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (known == null) {
                        Button(onClick = { naming = true }) { Text(stringResource(R.string.detail_mark_known)) }
                    } else {
                        OutlinedButton(onClick = { naming = true }) { Text(stringResource(R.string.detail_rename)) }
                        TextButton(onClick = { scope.launch { container.store.forget(key) } }) { Text(stringResource(R.string.detail_forget)) }
                    }
                    OutlinedButton(onClick = onIdentify) { Text(stringResource(R.string.detail_find)) }
                }
                Spacer(Modifier.height(16.dp))
            }

            PlainCard {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Field(stringResource(R.string.detail_type), stringResource(device.kind.label()))
                    Field(stringResource(R.string.detail_ip), device.ip)
                    device.manufacturer?.let { Field(stringResource(R.string.detail_maker), it) }
                    device.model?.let { Field(stringResource(R.string.detail_model), it) }
                    if (!device.isSelf) Field(stringResource(R.string.detail_seen_as), stringResource(device.identitySource()))
                    if (!device.isSelf) {
                        Field(
                            stringResource(R.string.detail_open_services),
                            device.openPorts.sorted().joinToString("\n") { portName(it) }.ifEmpty { stringResource(R.string.detail_none) },
                        )
                    }
                }
            }

            if (findings.isNotEmpty()) {
                Spacer(Modifier.height(16.dp))
                Text(stringResource(R.string.detail_issues), style = MaterialTheme.typography.titleSmall)
                Spacer(Modifier.height(8.dp))
                val status = LocalStatusColors.current
                findings.forEach { f ->
                    Row(
                        Modifier.clickable { onFinding(f.id) }.padding(vertical = 10.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        StatusDot(if (f.type.severity.ordinal == 0) status.high else status.medium)
                        Spacer(Modifier.width(12.dp))
                        Text(stringResource(f.type.text().title), Modifier.weight(1f))
                        Icon(Icons.AutoMirrored.Outlined.KeyboardArrowRight, null)
                    }
                }
            }

            if (!device.isSelf && device.bestName == null) {
                Spacer(Modifier.height(16.dp))
                PlainCard {
                    Column(Modifier.padding(16.dp)) {
                        Text(stringResource(R.string.detail_why_unknown_title), style = MaterialTheme.typography.titleSmall)
                        Spacer(Modifier.height(4.dp))
                        Text(stringResource(R.string.detail_why_unknown_body), style = MaterialTheme.typography.bodyMedium)
                    }
                }
            }
        }
        if (naming) {
            NameDialog(
                initial = known?.label ?: device.bestName.orEmpty(),
                onDismiss = { naming = false },
                onSave = { label ->
                    naming = false
                    scope.launch { container.store.setKnown(key, label) }
                    if (known == null) Telemetry.deviceMarkedKnown()
                },
            )
        }
    }
}

@Composable
private fun Field(label: String, value: String) {
    Column {
        Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodyLarge)
    }
}

@Composable
fun NameDialog(initial: String, onDismiss: () -> Unit, onSave: (String) -> Unit) {
    var text by rememberSaveable { mutableStateOf(initial) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.detail_mark_known)) },
        text = {
            OutlinedTextField(
                value = text,
                onValueChange = { text = it.take(60) },
                singleLine = true,
                placeholder = { Text(stringResource(R.string.detail_name_hint)) },
            )
        },
        confirmButton = { TextButton(onClick = { onSave(text.ifBlank { initial }) }, enabled = text.isNotBlank() || initial.isNotBlank()) { Text(stringResource(R.string.save)) } },
        dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(R.string.cancel)) } },
    )
}

internal fun Device.watchablePort(): Int? = openPorts.minOrNull()
