# Homora

An Android app that checks the home network your phone is on. It does three jobs:

1. **Who's on my Wi-Fi.** Finds the devices on the network, names them from what they announce, and lets you mark them as yours. Anything left unmarked deserves a closer look. It also has a "find this device" helper (unplug things one at a time and the app tells you when this one disappears) and a guide for getting someone off your Wi-Fi.
2. **Is my network set up safely.** Wi-Fi encryption, WPS, UPnP, Telnet, FTP, VNC, open camera streams and an unencrypted router settings page. Every finding comes with a fix.
3. **Where's my Wi-Fi good.** A live signal meter with router latency, a sound mode for walking around, saved rooms ranked best to worst, and a helper for smart devices that won't connect on 2.4 GHz.

Homora is a spin-off of [SENTINEL](../README.md) and shares its goal, but it is a standalone phone app. A phone can't see other devices' traffic, so SENTINEL's packet capture, anomaly model, firewall and honeypots are not part of it.

## Principles

- **A scanner, never an attack tool.** It only checks the private /24 network the phone is on, with a short list of ports and read-only questions. It never tries passwords, sends exploits, or disconnects devices. These limits are enforced in code (`net/Ipv4.scanRange`, `net/Scanner`).
- **Your device data stays on the phone.** Device lists, names, rooms and history live in one private JSON file (`data/Store`). Cloud backup is off.
- **Nothing runs unless you're looking at it.** Scans and the meter stop when the app leaves the screen. The only background job is the optional daily new-device check, which runs only on Wi-Fi while charging.
- **Telemetry is opt-in and can't leak identifiers.** `telemetry/Telemetry` accepts only counts and enums, sends counts as ranges, and is off until the user agrees.

## Android limits to know

- **Since Android 10, apps can't read other devices' MAC addresses** (the ARP table is blocked), so there is no MAC-vendor lookup. Devices are identified by mDNS/Bonjour, UPnP, NetBIOS, the router's DNS names and their web page title. A device that announces nothing shows as "Unknown device", which every non-root scanner app shares.
- Android exposes the Wi-Fi name and scan results only with location permission. Homora asks for it with that explanation and never reads the location.
- Android refreshes Wi-Fi signal strength only about every 1–3 s, so the meter animates between readings and adds router latency (polled every 0.5 s) as the fast-moving value.

## Build

Requirements: JDK 17 and the Android SDK (platform 36). From this folder:

```
./gradlew testDebugUnitTest assembleDebug
```

The APK is written to `app/build/outputs/apk/debug/`. GitHub Actions (`.github/workflows/homora.yml`) runs the tests and builds on every push that touches `homora/` and uploads three artifacts:

- **homora-release-apk** — install this one to try the app. It is minified and precompiled (baseline profile), so it opens much faster than the debug build. It is signed with the debug key; switch `signingConfig` in `app/build.gradle.kts` to your Play upload key before publishing.
- **homora-debug-apk** — for debugging only; debug builds of Compose apps start noticeably slower.
- **homora-screenshots** — PNGs of the real screens rendered by `SnapshotTest`, for reviewing the UI without a phone.

### Firebase config

`app/google-services.json` is **not committed**. Put your copy there for local builds, and store its contents as the repository secret `GOOGLE_SERVICES_JSON` for CI. Without it the app still builds and runs, with analytics, crash reports and feedback disabled.

### Firebase setup (free Spark plan)

1. **Authentication → Sign-in method:** enable **Anonymous** (used only for feedback).
2. **Firestore Database:** create it (production mode), then deploy the rules in `firebase/firestore.rules`.
3. **App Check:** register the Android app with **Play Integrity**. Debug builds print a debug token to logcat; add it under *App Check → Manage debug tokens*. Turn on enforcement for Firestore once the app works.
4. **Google Cloud console → APIs & Services → Credentials:** restrict the Android API key to package `com.charonsecurity.homora` and your signing certificate's SHA-1.
5. **Analytics:** leave Google Signals off and set data retention to the minimum.
6. **Hosting (privacy policy):** `firebase/public/privacy.html` is served at `https://homora-2026.web.app/privacy.html`. Fill in the contact e-mail first.

Deploy rules and the privacy page with the Firebase CLI:

```
cd firebase
firebase deploy --only firestore:rules,hosting --project homora-2026
```

Feedback appears in the Firebase console under *Firestore → feedback*. Usage appears under *Analytics → Events*.

## Layout

```
app/src/main/java/com/charonsecurity/homora/
  net/        IP maths, DNS/mDNS, SSDP, NetBIOS, LAN HTTP, probes, Scanner
  wifi/       Wi-Fi link reader, signal zones, security and smart-device analysis
  checks/     security findings (each one must have a fix the user can do)
  data/       on-phone storage, settings, scan repository and history
  telemetry/  the only analytics entry point
  feedback/   Firestore feedback with anonymous sign-in
  work/       the optional daily new-device check
  ui/         Compose screens (home, devices, security, wifi, settings, onboarding)
app/src/test/ unit tests for parsers, identity, checks, Wi-Fi analysis, history
firebase/     Firestore rules, Hosting config, privacy policy page
tools/        make_icon.py (all icon assets from one geometry)
store/        Play Store icon (512 px)
```
