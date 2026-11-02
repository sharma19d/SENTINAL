package com.charonsecurity.homora.ui.onboarding

import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.PagerState
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.charonsecurity.homora.AppContainer
import com.charonsecurity.homora.R
import com.charonsecurity.homora.telemetry.Telemetry
import com.charonsecurity.homora.ui.components.GlowButton
import com.charonsecurity.homora.ui.components.HomoraLogo
import com.charonsecurity.homora.ui.components.hasWifiDetailPermission
import com.charonsecurity.homora.ui.components.wifiDetailPermissions
import com.charonsecurity.homora.ui.theme.Brand
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlin.math.abs

private enum class Stage { INTRO, PAGES }

private const val PAGE_COUNT = 4
private const val PRIVACY_PAGE = PAGE_COUNT - 1

/**
 * First run only: the logo draws itself, then four short pages explain what
 * Homora does, and the last one asks for the one permission and for consent
 * to anonymous usage stats (off unless the user turns it on).
 */
@Composable
fun OnboardingScreen(container: AppContainer) {
    var stage by rememberSaveable { mutableStateOf(Stage.INTRO) }
    Box(
        Modifier
            .fillMaxSize()
            .background(Brush.verticalGradient(listOf(Color(0xFF07101F), Brand.Ink, Brand.Ink))),
    ) {
        AnimatedContent(
            targetState = stage,
            transitionSpec = { fadeIn(tween(500)) togetherWith fadeOut(tween(300)) },
            label = "onboarding",
        ) { s ->
            when (s) {
                Stage.INTRO -> IntroAnimation(onDone = { stage = Stage.PAGES })
                Stage.PAGES -> Pages(container)
            }
        }
    }
}

@Composable
private fun IntroAnimation(onDone: () -> Unit) {
    val draw = remember { Animatable(0f) }
    val words = remember { Animatable(0f) }
    LaunchedEffect(Unit) {
        draw.animateTo(1f, tween(1500, easing = LinearEasing))
        words.animateTo(1f, tween(550, easing = FastOutSlowInEasing))
        delay(750)
        onDone()
    }
    val t = rememberInfiniteTransition(label = "intro")
    val ring by t.animateFloat(0f, 1f, infiniteRepeatable(tween(1800, easing = LinearEasing)), label = "ring")

    Box(
        Modifier
            .fillMaxSize()
            .safeDrawingPadding()
            .clickable(interactionSource = remember { MutableInteractionSource() }, indication = null, onClick = onDone),
        contentAlignment = Alignment.Center,
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Box(Modifier.size(240.dp), contentAlignment = Alignment.Center) {
                Canvas(Modifier.fillMaxSize()) {
                    val shown = draw.value
                    // A soft blue glow that brightens as the mark completes.
                    drawCircle(
                        Brush.radialGradient(listOf(Brand.Blue.copy(alpha = 0.30f * shown), Color.Transparent), center, size.minDimension / 2f),
                        size.minDimension / 2f,
                    )
                    if (shown > 0.6f) {
                        val a = (shown - 0.6f) / 0.4f
                        repeat(2) { i ->
                            val f = (ring + i / 2f) % 1f
                            drawCircle(
                                Brand.Cyan.copy(alpha = 0.35f * (1f - f) * a),
                                size.minDimension * (0.28f + 0.22f * f),
                                center,
                                style = androidx.compose.ui.graphics.drawscope.Stroke(2f),
                            )
                        }
                    }
                }
                HomoraLogo(Modifier.size(150.dp), progress = draw.value)
            }
            Spacer(Modifier.height(20.dp))
            val w = words.value
            Text(
                stringResource(R.string.app_name),
                style = MaterialTheme.typography.displaySmall,
                modifier = Modifier.graphicsLayer { alpha = w; translationY = (1f - w) * 40f },
            )
            Spacer(Modifier.height(8.dp))
            Text(
                stringResource(R.string.onb_tagline),
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.graphicsLayer { alpha = w; translationY = (1f - w) * 60f },
            )
        }
    }
}

@Composable
private fun Pages(container: AppContainer) {
    val context = LocalContext.current
    val pager = rememberPagerState { PAGE_COUNT }
    val scope = rememberCoroutineScope()
    var share by rememberSaveable { mutableStateOf(false) }
    val granted = remember { hasWifiDetailPermission(context) }

    fun finish(permission: Boolean) {
        container.prefs.setAnalytics(share)
        Telemetry.setConsent(share)
        Telemetry.onboardingDone(permission)
        container.prefs.setOnboarded()
    }

    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) {
        val ok = hasWifiDetailPermission(context)
        Telemetry.permissionResult(ok)
        finish(ok)
    }

    BackHandler(enabled = pager.currentPage > 0) {
        scope.launch { pager.animateScrollToPage(pager.currentPage - 1) }
    }

    Column(Modifier.fillMaxSize().safeDrawingPadding()) {
        Row(Modifier.fillMaxWidth().height(52.dp).padding(horizontal = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            Spacer(Modifier.weight(1f))
            if (pager.currentPage < PRIVACY_PAGE) {
                TextButton(onClick = { scope.launch { pager.animateScrollToPage(PRIVACY_PAGE) } }) {
                    Text(stringResource(R.string.onb_skip), color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
        HorizontalPager(state = pager, modifier = Modifier.weight(1f), beyondViewportPageCount = 0) { page ->
            PageContent(page, pager)
        }
        Dots(pager, Modifier.align(Alignment.CenterHorizontally).padding(vertical = 18.dp))
        Column(Modifier.fillMaxWidth().padding(horizontal = 24.dp).padding(bottom = 20.dp)) {
            AnimatedContent(
                targetState = pager.currentPage == PRIVACY_PAGE,
                transitionSpec = { fadeIn(tween(250)) togetherWith fadeOut(tween(150)) },
                label = "actions",
            ) { last ->
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (!last) {
                        GlowButton(
                            stringResource(if (pager.currentPage == 0) R.string.onb_get_started else R.string.onb_next),
                            onClick = { scope.launch { pager.animateScrollToPage((pager.currentPage + 1).coerceAtMost(PRIVACY_PAGE)) } },
                        )
                        Spacer(Modifier.height(48.dp))
                    } else {
                        ShareRow(share) { share = it }
                        Spacer(Modifier.height(4.dp))
                        if (granted) {
                            GlowButton(stringResource(R.string.onb_continue), onClick = { finish(true) })
                            Spacer(Modifier.height(48.dp))
                        } else {
                            GlowButton(stringResource(R.string.onb2_allow), onClick = { launcher.launch(wifiDetailPermissions()) })
                            TextButton(onClick = { finish(false) }, modifier = Modifier.fillMaxWidth().height(40.dp)) {
                                Text(stringResource(R.string.onb2_skip), color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun PageContent(page: Int, pager: PagerState) {
    val active = pager.currentPage == page
    Column(
        Modifier
            .fillMaxSize()
            .graphicsLayer {
                // Slight fade and scale as a page slides away.
                val offset = abs((pager.currentPage - page) + pager.currentPageOffsetFraction).coerceIn(0f, 1f)
                alpha = 1f - offset * 0.7f
                val s = 1f - offset * 0.08f
                scaleX = s; scaleY = s
            }
            .padding(horizontal = 28.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Box(Modifier.weight(1f, fill = false), contentAlignment = Alignment.Center) {
            when (page) {
                0 -> RadarIllustration()
                1 -> ShieldIllustration(active)
                2 -> SignalIllustration()
                else -> PrivacyIllustration()
            }
        }
        Spacer(Modifier.height(28.dp))
        val (title, body) = when (page) {
            0 -> R.string.onb_p1_title to R.string.onb_p1_body
            1 -> R.string.onb_p2_title to R.string.onb_p2_body
            2 -> R.string.onb_p3_title to R.string.onb_p3_body
            else -> R.string.onb_p4_title to R.string.onb_p4_body
        }
        Text(stringResource(title), style = MaterialTheme.typography.headlineMedium, textAlign = TextAlign.Center)
        Spacer(Modifier.height(12.dp))
        Text(
            stringResource(body),
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
    }
}

@Composable
private fun Dots(pager: PagerState, modifier: Modifier = Modifier) {
    Row(modifier, horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
        repeat(PAGE_COUNT) { i ->
            val selected = pager.currentPage == i
            val w by animateDpAsState(if (selected) 24.dp else 8.dp, tween(250), label = "dot")
            Box(
                Modifier
                    .width(w)
                    .height(8.dp)
                    .background(if (selected) Color.White else Color.White.copy(alpha = 0.22f), RoundedCornerShape(50)),
            )
        }
    }
}

@Composable
private fun ShareRow(checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .background(Color.White.copy(alpha = 0.04f), RoundedCornerShape(18.dp))
            .clickable { onChange(!checked) }
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(stringResource(R.string.onb3_yes), style = MaterialTheme.typography.bodyLarge)
            Text(stringResource(R.string.onb_share_body), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Spacer(Modifier.width(12.dp))
        Switch(
            checked = checked,
            onCheckedChange = onChange,
            colors = SwitchDefaults.colors(checkedTrackColor = Brand.Blue, checkedThumbColor = Color.White),
        )
    }
}
