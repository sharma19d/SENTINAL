package com.charonsecurity.homora.ui.settings

import android.Manifest
import android.content.Intent
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.core.net.toUri
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.charonsecurity.homora.AppContainer
import com.charonsecurity.homora.BuildConfig
import com.charonsecurity.homora.R
import com.charonsecurity.homora.feedback.FeedbackRepository
import com.charonsecurity.homora.telemetry.Telemetry
import com.charonsecurity.homora.ui.components.DetailScaffold
import com.charonsecurity.homora.ui.components.SectionHeader
import com.charonsecurity.homora.work.NewDeviceWorker
import kotlinx.coroutines.launch

@Composable
fun SettingsScreen(container: AppContainer, onBack: () -> Unit, onFeedback: () -> Unit) {
    val context = LocalContext.current
    val analytics by container.prefs.analytics.collectAsStateWithLifecycle()
    val alerts by container.prefs.newDeviceAlerts.collectAsStateWithLifecycle()
    val scope = rememberCoroutineScope()
    var showSent by rememberSaveable { mutableStateOf(false) }
    var confirmClear by rememberSaveable { mutableStateOf(false) }
    val privacyUrl = stringResource(R.string.privacy_url)

    fun setAlerts(on: Boolean) {
        container.prefs.setNewDeviceAlerts(on)
        NewDeviceWorker.schedule(context, on)
        Telemetry.newDeviceAlerts(on)
    }
    val notifPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted -> setAlerts(granted) }

    DetailScaffold(stringResource(R.string.settings), onBack) { padding ->
        Column(Modifier.padding(padding).fillMaxSize().verticalScroll(rememberScrollState())) {
            SectionHeader(stringResource(R.string.settings_privacy_section))
            ToggleRow(stringResource(R.string.settings_analytics), stringResource(R.string.settings_analytics_body), analytics) {
                container.prefs.setAnalytics(it)
                Telemetry.setConsent(it)
            }
            LinkRow(stringResource(R.string.settings_what_sent)) { showSent = true }
            LinkRow(stringResource(R.string.settings_privacy_policy)) {
                context.startActivity(Intent(Intent.ACTION_VIEW, privacyUrl.toUri()))
            }
            HorizontalDivider(Modifier.padding(vertical = 8.dp))
            ToggleRow(stringResource(R.string.settings_alerts), stringResource(R.string.settings_alerts_body), alerts) { on ->
                if (on && Build.VERSION.SDK_INT >= 33) notifPermission.launch(Manifest.permission.POST_NOTIFICATIONS) else setAlerts(on)
            }
            LinkRow(stringResource(R.string.settings_feedback), stringResource(R.string.settings_feedback_body), onFeedback)
            LinkRow(stringResource(R.string.settings_clear), stringResource(R.string.settings_clear_body)) { confirmClear = true }
            HorizontalDivider(Modifier.padding(vertical = 8.dp))
            SectionHeader(stringResource(R.string.settings_about))
            Text(
                stringResource(R.string.settings_about_body),
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(horizontal = 16.dp),
            )
            Text(
                stringResource(R.string.settings_version, BuildConfig.VERSION_NAME),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(16.dp),
            )
        }
    }

    if (showSent) {
        AlertDialog(
            onDismissRequest = { showSent = false },
            title = { Text(stringResource(R.string.settings_what_sent)) },
            text = { Text(stringResource(R.string.settings_what_sent_body)) },
            confirmButton = { TextButton(onClick = { showSent = false }) { Text(stringResource(android.R.string.ok)) } },
        )
    }
    if (confirmClear) {
        AlertDialog(
            onDismissRequest = { confirmClear = false },
            title = { Text(stringResource(R.string.settings_clear)) },
            text = { Text(stringResource(R.string.settings_clear_confirm)) },
            confirmButton = {
                TextButton(onClick = {
                    confirmClear = false
                    scope.launch { container.store.clearAll() }
                }) { Text(stringResource(R.string.settings_clear_yes)) }
            },
            dismissButton = { TextButton(onClick = { confirmClear = false }) { Text(stringResource(R.string.cancel)) } },
        )
    }
}

@Composable
private fun ToggleRow(title: String, body: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(
        Modifier.fillMaxWidth().clickable { onChange(!checked) }.padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.bodyLarge)
            Text(body, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Spacer(Modifier.width(12.dp))
        Switch(checked = checked, onCheckedChange = onChange)
    }
}

@Composable
private fun LinkRow(title: String, body: String? = null, onClick: () -> Unit) {
    Column(Modifier.fillMaxWidth().clickable(onClick = onClick).padding(horizontal = 16.dp, vertical = 14.dp)) {
        Text(title, style = MaterialTheme.typography.bodyLarge)
        body?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
    }
}

@Composable
fun FeedbackScreen(container: AppContainer, onBack: () -> Unit) {
    var isProblem by rememberSaveable { mutableStateOf(false) }
    var text by rememberSaveable { mutableStateOf("") }
    var email by rememberSaveable { mutableStateOf("") }
    var sending by rememberSaveable { mutableStateOf(false) }
    var result by rememberSaveable { mutableStateOf<Boolean?>(null) }
    val scope = rememberCoroutineScope()
    val repo = container.feedback

    DetailScaffold(stringResource(R.string.feedback_title), onBack) { padding ->
        Column(
            Modifier.padding(padding).fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (!repo.isAvailable) {
                Text(stringResource(R.string.feedback_unavailable), style = MaterialTheme.typography.bodyLarge)
                return@Column
            }
            if (result == true) {
                Text(stringResource(R.string.feedback_sent), style = MaterialTheme.typography.titleMedium)
                Button(onClick = onBack) { Text(stringResource(R.string.back)) }
                return@Column
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(selected = !isProblem, onClick = { isProblem = false }, label = { Text(stringResource(R.string.feedback_idea)) })
                FilterChip(selected = isProblem, onClick = { isProblem = true }, label = { Text(stringResource(R.string.feedback_problem)) })
            }
            OutlinedTextField(
                value = text,
                onValueChange = { text = it.take(FeedbackRepository.MAX_LENGTH) },
                modifier = Modifier.fillMaxWidth().height(180.dp),
                placeholder = { Text(stringResource(R.string.feedback_hint)) },
                supportingText = { Text(stringResource(R.string.feedback_count, text.length, FeedbackRepository.MAX_LENGTH)) },
            )
            OutlinedTextField(
                value = email,
                onValueChange = { email = it.take(120) },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                label = { Text(stringResource(R.string.feedback_email)) },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
            )
            Text(stringResource(R.string.feedback_warning), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (result == false) {
                Text(stringResource(R.string.feedback_error), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
            }
            Button(
                enabled = !sending && text.trim().length >= FeedbackRepository.MIN_LENGTH,
                onClick = {
                    sending = true
                    scope.launch {
                        val ok = repo.send(isProblem, text, email.ifBlank { null }).isSuccess
                        if (ok) Telemetry.feedbackSent(isProblem)
                        result = ok
                        sending = false
                    }
                },
            ) { Text(stringResource(R.string.feedback_send)) }
        }
    }
}
