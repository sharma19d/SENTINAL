package com.charonsecurity.homora

import android.graphics.Color
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import com.charonsecurity.homora.ui.HomoraRoot
import com.charonsecurity.homora.ui.theme.HomoraTheme

class MainActivity : ComponentActivity() {
    private val container get() = (application as HomoraApp).container

    override fun onCreate(savedInstanceState: Bundle?) {
        // Swaps the system splash (logo on dark) for the app theme as soon as the first frame is ready.
        installSplashScreen()
        super.onCreate(savedInstanceState)
        // The app is always dark, so system bar icons are always light.
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.dark(Color.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.dark(Color.TRANSPARENT),
        )
        setContent {
            HomoraTheme {
                HomoraRoot(container)
            }
        }
    }

    override fun onStop() {
        super.onStop()
        // Nothing runs while the app isn't on screen.
        if (!isChangingConfigurations) container.scans.cancel()
    }
}
