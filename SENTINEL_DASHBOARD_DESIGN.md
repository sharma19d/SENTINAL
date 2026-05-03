# SENTINEL Dashboard — Complete Design Specification
## UI/UX Blueprint for AI Agent & Development Reference

> This document defines every visual and interaction decision for the SENTINEL
> dashboard. Any AI assistant or developer working on the frontend must read
> this entire file before writing a single line of code.

---

## 1. Design Philosophy — "Dark Matter"

### The One-Line Brief
A premium intelligence interface that makes threat data feel like calm, 
surgical clarity — not panic, not noise.

### The Problem We Are Solving Visually
Every security dashboard looks the same:
- Dark blue backgrounds with cyan/green text
- Hexagon grids and "hacker" aesthetics  
- Data overload with no visual hierarchy
- Feels like enterprise software from 2015

SENTINEL must feel like none of those things. It should feel closer to:
- A Bloomberg Terminal redesigned by a luxury product studio
- The calm precision of a surgical monitor
- Something a premium smart home brand (not a cybersecurity corp) designed

### Three Words That Define Every Decision
**CALM. PRECISE. ALIVE.**

- **Calm** — the UI never screams at you. Even critical alerts feel controlled.
- **Precise** — every element earns its space. Nothing decorative that adds no meaning.
- **Alive** — data breathes. The dashboard feels like it is actively watching.

### What We Deliberately Avoid
- ❌ Cyan/teal as primary accent (overused in security tools)
- ❌ Hexagon backgrounds or grid patterns (cliché hacker aesthetic)
- ❌ Neon glow effects on everything
- ❌ Pure black (#000000) backgrounds (harsh, low depth)
- ❌ Tables that look like spreadsheets
- ❌ Pie charts (use ring charts or arc gauges instead)
- ❌ Red for everything dangerous (use amber for warning, rose for critical)
- ❌ Sidebar navigation that takes 260px of prime real estate

---

## 2. Color System

### Base Palette — "Deep Slate"

```css
:root {
  /* ── Backgrounds (layered depth system) ────────────────── */
  --bg-void:        #060A12;   /* deepest layer — page background */
  --bg-base:        #0B1120;   /* base surfaces — main content areas */
  --bg-surface:     #101829;   /* cards, panels */
  --bg-elevated:    #162035;   /* hover states, dropdowns */
  --bg-overlay:     #1C2A42;   /* modals, tooltips */

  /* ── Borders ────────────────────────────────────────────── */
  --border-subtle:  #1E2D45;   /* barely visible — card edges */
  --border-default: #253552;   /* normal borders */
  --border-strong:  #2E4168;   /* emphasis borders */

  /* ── Primary Accent — Electric Amber ────────────────────── */
  /* Not the typical cyan. Amber conveys intelligence, alert, warmth.
     Completely unusual in security tools = instant differentiation. */
  --amber-dim:      #92540A;   /* subtle amber backgrounds */
  --amber-muted:    #C4710F;   /* secondary amber elements */
  --amber:          #F59E0B;   /* primary amber — main accent */
  --amber-bright:   #FCD34D;   /* highlight amber */
  --amber-glow:     rgba(245, 158, 11, 0.15); /* ambient glow */

  /* ── Semantic Colors ────────────────────────────────────── */
  --safe:           #10B981;   /* emerald — device is healthy */
  --safe-bg:        rgba(16, 185, 129, 0.08);
  --warning:        #F59E0B;   /* amber — medium risk (same as accent) */
  --warning-bg:     rgba(245, 158, 11, 0.08);
  --critical:       #F43F5E;   /* rose — high severity threat */
  --critical-bg:    rgba(244, 63, 94, 0.08);
  --info:           #6366F1;   /* indigo — informational, passive */
  --info-bg:        rgba(99, 102, 241, 0.08);

  /* ── Text ───────────────────────────────────────────────── */
  --text-primary:   #E8EDF5;   /* main readable text — NOT pure white */
  --text-secondary: #8A99B5;   /* supporting text */
  --text-muted:     #4A5A78;   /* timestamps, labels, metadata */
  --text-disabled:  #2E3D58;   /* inactive elements */
  --text-accent:    #F59E0B;   /* amber text for highlights */
  --text-code:      #93C5FD;   /* blue-tinted for IPs, ports, hex */

  /* ── Severity Scale ─────────────────────────────────────── */
  /* Used for device risk scores 1-10 */
  --sev-1:  #10B981;   /* 1-2  safe      emerald */
  --sev-3:  #34D399;   /* 3    low        light emerald */
  --sev-4:  #FCD34D;   /* 4-5  moderate   amber bright */
  --sev-6:  #F59E0B;   /* 6-7  high       amber */
  --sev-8:  #FB923C;   /* 8    very high  orange */
  --sev-9:  #F43F5E;   /* 9-10 critical   rose */
}
```

### Color Usage Rules

- **Amber is used sparingly** — only for the most important interactive 
  elements and the highest-value data points. Overusing it kills impact.
- **Backgrounds are never truly black** — they have deep blue undertones 
  which creates warmth and depth.
- **Surface layers follow a strict 5-level hierarchy** — never skip levels 
  (a tooltip must sit on --bg-overlay, never on --bg-base).
- **Text code color** (--text-code) is used for all technical data: 
  IP addresses, MAC addresses, port numbers, CVE IDs, technique IDs.
  This creates an instant visual category that trained eyes scan to.

---

## 3. Typography

### Font Stack

```css
/* Display — headings, dashboard title, section labels */
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700;800&display=swap');

/* Body — all readable prose, descriptions, alert summaries */
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;500;600&display=swap');

/* Monospace — IPs, MACs, ports, CVE IDs, hex, technique IDs */
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap');

:root {
  --font-display: 'Syne', sans-serif;
  --font-body:    'Sora', sans-serif;
  --font-mono:    'IBM Plex Mono', monospace;
}
```

### Why These Three Fonts

**Syne** — Geometric, architectural, slightly compressed. Used by design studios 
and creative agencies. Has a precision engineering quality. Nobody uses it in 
security tools — which is exactly why we do. Makes SENTINEL look designed, 
not assembled.

**Sora** — Slightly rounded geometric. Approachable but not playful. Has 
excellent readability at small sizes — critical for dense security data. 
Feels modern without being trendy.

**IBM Plex Mono** — IBM's own monospace typeface. Has a technical pedigree 
but also beautiful letterforms. Looks intentional and premium where Courier 
or Fira Mono would look generic.

### Type Scale

```css
/* ── Display ───────────────────────────────────── */
.text-display-xl  { font: 800 48px/1.1 var(--font-display); letter-spacing: -0.03em; }
.text-display-lg  { font: 700 36px/1.15 var(--font-display); letter-spacing: -0.02em; }
.text-display-md  { font: 600 28px/1.2  var(--font-display); letter-spacing: -0.015em; }

/* ── Section headers ────────────────────────────── */
.text-heading-lg  { font: 600 20px/1.3  var(--font-display); letter-spacing: -0.01em; }
.text-heading-md  { font: 600 16px/1.4  var(--font-display); letter-spacing: -0.005em; }
.text-heading-sm  { font: 500 13px/1.4  var(--font-display); letter-spacing: 0.06em;
                    text-transform: uppercase; }  /* ← label style */

/* ── Body ───────────────────────────────────────── */
.text-body-lg     { font: 400 16px/1.6  var(--font-body); }
.text-body-md     { font: 400 14px/1.6  var(--font-body); }
.text-body-sm     { font: 400 12px/1.5  var(--font-body); }

/* ── Monospace / Data ────────────────────────────── */
.text-mono-md     { font: 500 14px/1.4  var(--font-mono); }
.text-mono-sm     { font: 400 12px/1.4  var(--font-mono); }
.text-mono-xs     { font: 400 11px/1.4  var(--font-mono); letter-spacing: 0.02em; }
```

### Typography Rules

- **Section labels** (DEVICES, THREATS, STATUS) use `.text-heading-sm` — 
  uppercase, tracked out, amber colored. Creates structure without using headers.
- **IP addresses always use IBM Plex Mono** in --text-code color. Never body font.
- **CVE IDs always use IBM Plex Mono** in --critical color.
- **Technique IDs (T0884) always use IBM Plex Mono** in --amber color.
- **Risk scores use Syne 700** — they are display numbers, not data labels.
- **Line heights are deliberately generous** — 1.6 for body text. Crowded 
  security dashboards cause cognitive overload. Space is information.

---

## 4. Layout Architecture

### The Grid Concept — "Command Canvas"

SENTINEL does not use a traditional sidebar + main content layout.
Instead it uses a **top command bar + fluid canvas** system.

```
┌─────────────────────────────────────────────────────────────┐
│  COMMAND BAR (fixed, 56px height)                           │
│  [SENTINEL mark]  [network status]  [search]  [alerts]  [⚙] │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  THREAT RIBBON (collapsible, 48px when collapsed)            │
│  Live scrolling strip of recent threat events               │
│                                                              │
├──────────────────────┬──────────────────┬───────────────────┤
│                      │                  │                   │
│  NETWORK GRAPH       │  DEVICE LIST     │  DETAIL PANEL     │
│  (D3.js force)       │  (scrollable)    │  (contextual)     │
│  flex: 1.2           │  flex: 1         │  flex: 0.9        │
│                      │                  │                   │
│  40% of width        │  33% of width    │  27% of width     │
│                      │                  │                   │
├──────────────────────┴──────────────────┴───────────────────┤
│                                                              │
│  INTEL STRIP (fixed height 120px)                           │
│  [honeypot activity] [threat intel feed] [system metrics]   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Layout Principles

**No sidebar.** The command bar is a single horizontal strip at the top.
Navigation happens via the command bar and contextual panels — not a 
260px sidebar that wastes prime real estate.

**The Detail Panel is contextual.** Clicking a device populates it with 
device details. Clicking a threat populates it with threat details. 
It's never empty — it shows network overview by default.

**The Intel Strip is always visible.** Like a stock ticker for your network.
Always running, always current, never intrudes on the main canvas.

**The Threat Ribbon collapses.** When there are no active threats it 
collapses to a 4px amber line at the top (like a pulse line). When threats 
arrive it expands to 48px with scrolling event cards.

### Responsive Behavior

```
> 1400px: Full three-column layout as above
1100-1400px: Graph takes full top half, device list + detail stack below
800-1100px: Tabbed layout — Graph | Devices | Threats tabs
< 800px: Mobile — single column, bottom navigation, simplified graph
```

---

## 5. Component Design

### 5.1 Command Bar

```
Height: 56px
Background: --bg-surface with backdrop-filter: blur(20px)
Border-bottom: 1px solid --border-subtle
Position: fixed top-0, z-index: 100

Left section:
  - SENTINEL wordmark in Syne 700, 18px
  - A single amber dot (8px) that pulses when system is active
  - Below wordmark: "NETWORK ACTIVE" in --text-muted, 10px mono uppercase

Center section:
  - Search/command bar — single input, 400px wide
  - Placeholder: "Search device, IP, CVE, technique..."
  - CMD+K keyboard shortcut badge on right
  - On focus: subtle amber glow border, dropdown of recent searches

Right section (left to right):
  - Network health pill: "[●] 24 DEVICES  [●] 2 ALERTS"
    - dot color maps to worst current severity
  - Alert bell icon — badge count, rings with animation on new alert
  - Settings gear — opens side sheet (not a new page)
```

### 5.2 Device Cards (in Device List panel)

Each card represents one discovered device. Cards are the core unit of 
the device list — they should be scannable in under 1 second.

```
Card anatomy (height: 72px, full width of panel):

┌─────────────────────────────────────────────────────┐
│ [icon]  Device Name              Risk Score    [●]  │
│         192.168.1.45             ████░░  7.2   ●●●  │
│         Hikvision · Camera                          │
└─────────────────────────────────────────────────────┘

Elements:
  - Device icon: category icon (camera, bulb, TV, router)
    16x16px, --text-muted color, left-aligned
  - Device name: Syne 500, 14px, --text-primary
    If no hostname: show vendor + MAC last 4
  - IP address: IBM Plex Mono 12px, --text-code
  - Vendor + type: Sora 12px, --text-muted
  - Risk score: right-aligned
    - Number: Syne 700, 20px, colored by severity
    - Bar: thin 40px progress bar, colored by severity, animated fill
  - Status dot: 6px circle
    - Solid green: normal
    - Pulsing amber: anomaly detected
    - Pulsing red: active threat
    - Grey: offline/unseen >10 min

Hover state:
  - Background lifts to --bg-elevated
  - Left border: 2px solid severity color appears
  - Subtle translateX(2px) on the content
  - Transition: all 150ms cubic-bezier(0.4, 0, 0.2, 1)

Selected state:
  - Background: --bg-overlay
  - Left border: 2px solid --amber (always amber when selected,
    regardless of severity — selection is selection)
  - Detail panel animates in from right
```

### 5.3 Network Risk Graph (D3.js)

This is the centerpiece of the dashboard. It must be beautiful and functional.

```
Graph type: Force-directed node-link diagram

Node design:
  - Shape: Circle (not hexagon — everyone uses hexagon)
  - Size: Maps to risk score (min 20px, max 52px diameter)
  - Fill: --bg-elevated (dark, not bright)
  - Border: 2px solid, color = severity color
  - Icon inside: SVG device category icon, 40% of node diameter
  - No label on node — label appears on hover only
  - Low-risk nodes: gentle 4s breathing animation (scale 1→1.03→1)
  - Threat nodes: sharp 1.5s pulse animation (border glow)
  - Quarantined nodes: red X overlay, desaturated, stop animations

Edge (link) design:
  - Width: 1px normally, 2px for active traffic
  - Color: --border-default normally
  - Active traffic: gradient line, animated dash flowing in direction
  - Edge color maps to traffic volume:
    quiet = --border-subtle
    normal = --border-default  
    high = --amber at 40% opacity

SENTINEL node (the appliance itself):
  - Always in center
  - Slightly larger (fixed 60px)
  - Amber colored border (always)
  - Shield icon inside
  - All other nodes connect through this one

Graph controls (bottom-right of graph panel):
  - [+] [-] zoom buttons (36px, ghost style)
  - [↺] reset layout
  - [⊞] toggle labels on/off
  All controls: --bg-elevated, --border-subtle, no drop shadows

Honeypot nodes:
  - Dashed border instead of solid (indicates virtual/fake device)
  - Spider icon inside
  - If attacker is connected to it: amber glow + animated dashes
```

### 5.4 Threat Event Cards (in Threat Ribbon)

```
Ribbon card (when expanded to 48px height):

┌──────────────────────────────────────────────────────────────┐
│ ● CRITICAL  T0884  192.168.1.45  →  C2 Beacon   2m ago  [→] │
└──────────────────────────────────────────────────────────────┘

Elements:
  - Severity dot: 8px, color-coded
  - Severity label: Syne 600, 11px uppercase, severity color
  - Technique ID: IBM Plex Mono 11px, --amber
  - Source IP: IBM Plex Mono 11px, --text-code
  - Arrow: → in --text-muted
  - Short summary: Sora 12px, --text-secondary, truncated
  - Timestamp: IBM Plex Mono 10px, --text-muted
  - Arrow icon: opens detail panel

New event animation:
  - Card slides in from right, 300ms ease-out
  - Brief amber flash on entry (opacity 0.3 → 0, 600ms)
  - Older events push left
  - When ribbon is collapsed: the 4px line flashes amber on new event
```

### 5.5 Detail Panel — Threat View

When a threat event is clicked, the right panel shows full detail:

```
Panel header:
  - Technique name: Syne 700, 24px
  - Technique ID: IBM Plex Mono 14px, --amber, below
  - Severity badge: large pill, severity color background
  - Confidence %: arc gauge, 80px diameter
  - Timestamp: IBM Plex Mono 12px, --text-muted

Tactic path (breadcrumb style):
  Shows ATT&CK kill chain position:
  Reconnaissance → Initial Access → [COMMAND & CONTROL] → Exfiltration
  Current stage highlighted in amber, others in --text-muted

Affected device card (mini version of device card):
  - Inline, shows device name, IP, vendor, risk score

Indicators section:
  - Each indicator on its own row
  - IP indicators: globe icon + IBM Plex Mono
  - Domain indicators: @ icon + IBM Plex Mono
  - AbuseIPDB score inline if available (small bar)

LLM Summary box:
  - Slightly different background (--bg-overlay)
  - Left border: 2px --info (indigo) — visually marks as AI-generated
  - Label: "SENTINEL ANALYSIS" in --text-muted 10px uppercase
  - Text: Sora 14px, --text-secondary
  - Small "Gemma 4" badge in corner (small, honest attribution)

Action buttons (at bottom of panel):
  Three options, stacked vertically:

  [QUARANTINE DEVICE]
    - Full width, rose background, Syne 600 14px
    - Only active for severity >= 8
    - Disabled state for lower severity (with tooltip why)

  [REDIRECT TO HONEYPOT]  
    - Full width, --bg-elevated border, --text-primary
    - Available for severity 6+

  [MARK AS FALSE POSITIVE]
    - Ghost button, --text-muted
    - Smaller than the other two

  Confirmation modal for quarantine (not a separate page):
    - Slides up from bottom of panel (not a global modal)
    - Shows exactly what will happen in plain English
    - 10-second countdown with cancel option
    - Requires typing device name to confirm (like GitHub delete)
```

### 5.6 Device Detail Panel

When a device is clicked (no active threat):

```
Header section:
  - Large device icon: 48px, in a rounded square, --bg-overlay
  - Device name: Syne 700, 22px
  - Status pill: ONLINE / OFFLINE / QUARANTINED / MONITORING
  - Last seen: IBM Plex Mono 12px, --text-muted

Stats row (4 numbers across):
  ┌──────────┬──────────┬──────────┬──────────┐
  │  9.2     │  23      │  3       │  14d     │
  │ Risk     │ Open     │ Critical │ Since    │
  │ Score    │ Ports    │ CVEs     │ Seen     │
  └──────────┴──────────┴──────────┴──────────┘
  - Numbers: Syne 700, 28px, colored by implication
  - Labels: Sora 11px, --text-muted, uppercase

Risk score arc gauge:
  - 120px diameter
  - Arc from 7 o'clock to 5 o'clock (220° sweep)
  - Filled portion: severity color
  - Score number in center: Syne 800, 32px
  - "RISK SCORE" label below: 10px uppercase

CVE List:
  - Each CVE as a row:
    [CVE-2021-36260]  [CVSS 9.8]  Remote Code Execution  [UNPATCHED]
    - CVE ID: IBM Plex Mono 12px, --critical
    - CVSS score: severity-colored pill
    - Description: Sora 12px, --text-secondary, truncated
    - Status pill: UNPATCHED (rose) / PATCHED (emerald)

Traffic baseline chart:
  - 24-hour sparkline: bytes/sec
  - Current vs baseline overlay
  - Anomaly regions highlighted in amber
  - Chart library: Recharts, minimal style (no borders, no grid,
    just the line and area fill)
  - Height: 80px (intentionally compact)

Open ports:
  - Grid of port pills: [22/TCP] [443/TCP] [8080/TCP]
  - Risky well-known ports: amber border
  - Standard ports: --border-subtle
```

### 5.7 Intel Strip (bottom bar)

Three sections always visible at bottom:

```
Section 1 — Honeypot Activity (left, 33%):
  Label: "HONEYPOT SESSIONS" in --text-muted uppercase 10px
  Content: Scrolling list of recent attacker interactions
    "SSH login attempt · cowrie · 2m ago"
    "3 commands executed · 192.168.1.102 · 5m ago"
  Font: IBM Plex Mono 11px

Section 2 — Threat Intel Feed (center, 34%):
  Label: "THREAT INTEL" in --text-muted uppercase 10px
  Content: Recent IoC matches scrolling through
    "AbuseIPDB match: 185.220.101.47 (confidence 98%)"
  Font: IBM Plex Mono 11px

Section 3 — System Metrics (right, 33%):
  Label: "SENTINEL HEALTH" in --text-muted uppercase 10px
  Content: 3 mini metrics:
    CPU: [████░░░░] 34%
    RAM: [██████░░] 61%  
    PACKETS/s: 847
  Mini bars, no numbers except the final value
  All green when normal, amber when >75%, rose when >90%
```

---

## 6. Animation System

### Guiding Principle
Animations must have **semantic meaning** — every motion communicates 
something about the data or system state. No animation exists purely 
for decoration.

### Animation Tokens

```css
:root {
  /* Duration */
  --duration-instant:  80ms;   /* immediate feedback — button press */
  --duration-fast:    150ms;   /* hover states, small transitions */
  --duration-normal:  250ms;   /* panel transitions, card reveals */
  --duration-slow:    400ms;   /* page-level transitions, graph updates */
  --duration-breathe: 4000ms;  /* ambient breathing animations */

  /* Easing */
  --ease-out:    cubic-bezier(0.0, 0.0, 0.2, 1);  /* decelerate to rest */
  --ease-in:     cubic-bezier(0.4, 0.0, 1.0, 1);  /* accelerate from rest */
  --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1); /* slight overshoot */
  --ease-linear: linear;  /* only for continuous animations like spinners */
}
```

### Specific Animations

**Device Node Breathing (safe devices):**
```css
@keyframes breathe {
  0%, 100% { transform: scale(1);    opacity: 1; }
  50%       { transform: scale(1.04); opacity: 0.85; }
}
/* Applied to: safe device nodes in D3 graph */
/* Duration: 4s, infinite, ease-in-out */
/* Stagger: each device gets a random delay (0-4s) so they don't pulse in sync */
```

**Threat Pulse (devices with active threats):**
```css
@keyframes threat-pulse {
  0%   { box-shadow: 0 0 0 0px rgba(244, 63, 94, 0.4); }
  70%  { box-shadow: 0 0 0 12px rgba(244, 63, 94, 0); }
  100% { box-shadow: 0 0 0 0px rgba(244, 63, 94, 0); }
}
/* Duration: 1.5s, infinite */
/* This is the only "urgent" animation — everything else is slow */
```

**New Threat Event Entry:**
```css
@keyframes threat-enter {
  from {
    opacity: 0;
    transform: translateX(24px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}
/* Duration: 300ms, ease-out */
/* Followed by: 600ms amber flash fade on the card */
```

**Detail Panel Slide In:**
```css
@keyframes panel-enter {
  from {
    opacity: 0;
    transform: translateX(16px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}
/* Duration: 250ms, ease-out */
/* Applied to: content inside detail panel on context change */
/* The panel container does NOT animate — only its contents do */
```

**Risk Score Count-Up:**
When a device risk score updates or when the panel first opens, 
the score number counts up from 0 to the actual value.
```
Duration: 800ms
Easing: ease-out (fast at start, slow at end — builds tension)
Font weight animates simultaneously: 400 → 700 as number rises
Color transitions from --safe → severity color as number climbs
```

**Quarantine Countdown:**
```
10-second circular countdown in the confirmation modal
SVG circle stroke-dashoffset animates over 10 seconds
Color: amber → rose over the duration
At 0: action executes automatically OR user cancelled
```

**Traffic Anomaly Highlight:**
When LSTM detects anomaly in sparkline chart:
```
Anomaly region: amber fill appears, opacity 0 → 0.3, duration 600ms
Simultaneously: chart border flashes amber once, 300ms
Device card row: brief amber background flash, 400ms, ease-out
```

**Page Load — Staggered Reveal:**
```
Command bar: slides down from top, 400ms, delay 0ms
Threat ribbon: fades in, 300ms, delay 100ms
Graph panel: fades in + slight scale (0.98 → 1), 400ms, delay 200ms
Device list cards: each card fades in sequentially, 
  150ms each, 40ms stagger between cards
Intel strip: slides up from bottom, 300ms, delay 400ms
```

**Data Refresh Pulse:**
When new data comes in via WebSocket (every 5 seconds):
```
The amber dot in the command bar pulses once: scale 1 → 1.5 → 1, 400ms
Affected device cards get a subtle shimmer sweep (like a loading skeleton
but reversed — content is already there, shimmer confirms update)
Shimmer: transparent → --amber at 5% → transparent, left to right, 600ms
```

---

## 7. Micro-interactions

### Hover States
All interactive elements have distinct hover states. No element should 
be interactive without communicating that it is.

```
Buttons:
  Ghost → slight background lift (--bg-elevated)
  Primary → brightness(1.1), slight scale(1.01)
  Destructive (quarantine) → brightness(1.05), adds rose glow

Cards:
  translateX(2px), background lift, left border appears
  All: 150ms ease-out

Navigation items:
  Amber underline slides in from left (not from center — 
  center-expanding underlines are overused)
  Duration: 200ms ease-out

Tooltips:
  Scale from 0.95 → 1.0 + opacity 0 → 1
  Duration: 150ms ease-out
  Never delay more than 300ms on hover
  Disappear instantly (0ms) — no fade out on mouse leave
```

### Click Feedback
```
All buttons: scale(0.97) on mousedown, returns on mouseup
Duration: 80ms (instant-feeling)
This applies to EVERY clickable element — no exceptions
```

### Focus States (Accessibility)
```
All focusable elements:
  outline: 2px solid --amber
  outline-offset: 3px
  border-radius: matches the element
Never remove focus outlines — style them instead
```

---

## 8. Empty and Loading States

### Empty States
When a section has no data, never show a blank space.

```
Device list (no devices discovered yet):
  Centered in the panel:
  Icon: subtle network scan animation (pulsing rings)
  Heading: "Scanning your network"
  Subtext: "SENTINEL is discovering devices. This takes 2-5 minutes."
  No button, no CTA — just calm reassurance

Threat feed (no threats):
  Ribbon stays collapsed (4px line)
  Color: --safe (emerald) instead of amber — the line itself
  communicates "all clear" without any text needed

Honeypot (no sessions):
  "No attacker interactions" in --text-muted
  Subtext: "Honeypots are active and listening"
```

### Loading States
```
Skeleton screens for device cards:
  - Same 72px height as real cards
  - Animated shimmer: --bg-elevated → --bg-overlay → --bg-elevated
  - Sweeps left to right, 1.5s, infinite
  - Show 4-6 skeleton cards while loading
  - NEVER show a spinner for list content

Graph loading:
  - Nodes fade in one by one as devices are discovered
  - No "loading" state — graph is always partially populated
  - Empty graph shows SENTINEL node alone, pulsing rings indicate scan

Gemma 4 classifying a threat (LLM inference):
  - In the detail panel, the Analysis section shows:
  - Three dots typing animation in --amber color
  - Label: "SENTINEL is analysing..."
  - Duration typically 2-5 seconds on Pi 5
  - When complete: text fades in line by line, not all at once
    (reinforces the "AI is thinking" experience)
```

---

## 9. Notification & Alert System

### Alert Hierarchy
SENTINEL uses four notification levels, each with distinct visual treatment:

```
LEVEL 1 — INFO (blue/indigo)
  Passive. Appears in Intel Strip only.
  Example: "New device discovered: Amazon Echo"
  No sound, no intrusion into main UI

LEVEL 2 — WARNING (amber)
  Appears in Threat Ribbon + banner below command bar
  Banner: 40px tall, amber left border, slides down from command bar
  Auto-dismisses after 10 seconds
  Example: "Anomaly detected on Hikvision Camera"

LEVEL 3 — CRITICAL (rose)
  Full attention capture:
  - Threat ribbon expands and flashes
  - Affected device node pulses in graph
  - Detail panel auto-opens with threat detail
  - Web Push notification sent to mobile
  - Does NOT play a sound (home security tool — silent is respectful)

LEVEL 4 — QUARANTINE REQUESTED
  Unique state — only when LLM recommends quarantine (severity 8+):
  - Rose banner persists (does not auto-dismiss)
  - Device card gets rose left border treatment
  - Confirmation modal appears in detail panel
  - All other UI dims slightly (background opacity 0.6)
  - Timer countdown: user has 60 seconds to confirm or dismiss
```

### Web Push Notification Design
```
Title: "SENTINEL Alert" 
Body: "[Device name] — [Short summary] — Severity [score]/10"
Icon: SENTINEL shield mark (amber on dark)
Action buttons: "View" | "Quarantine" (native push action buttons)
Badge: Number of unacknowledged threats
```

---

## 10. The Quarantine Confirmation UX

This is the most consequential action in SENTINEL. It must be:
- **Impossible to trigger accidentally**
- **Completely clear what will happen**
- **Easy to cancel**

```
Trigger: User clicks [QUARANTINE DEVICE] button

Step 1 — Context panel expands (no full-screen modal):
  Shows inside the detail panel, pushes action buttons down:
  
  ┌─────────────────────────────────────────────────┐
  │  ⚠  QUARANTINE 192.168.1.45                    │
  │                                                  │
  │  This will immediately:                          │
  │  • Block ALL network traffic from this device    │
  │  • Disconnect it from the internet               │
  │  • Log the action with timestamp                 │
  │                                                  │
  │  Device will remain isolated until manually      │
  │  released from this panel.                       │
  │                                                  │
  │  Type the device name to confirm:                │
  │  [________________________]                      │
  │                                                  │
  │  [    QUARANTINE NOW    ]  ← disabled until typed│
  │  [       Cancel         ]                        │
  │                                                  │
  │  Auto-cancels in [●●●●●●●●●●] 60s               │
  └─────────────────────────────────────────────────┘

Step 2 — On confirm:
  Button: brief loading state (spinner, 500ms)
  Then: device card immediately updates to QUARANTINED state
  Graph node: greyed out, red X overlay, edges fade to --border-subtle
  Success message in panel: "Device quarantined at [timestamp]"
  [RELEASE QUARANTINE] button appears

Design rationale:
  The typing requirement is borrowed from GitHub's delete repo flow.
  It forces a conscious action — you cannot accidentally type the 
  device name. The auto-cancel timer prevents forgotten modals.
```

---

## 11. Mobile Experience (< 800px)

Mobile is a monitoring and alert-response surface, not a management surface.
Heavy configuration happens on desktop. Mobile must do three things fast:
**see threats, approve actions, check device status.**

```
Navigation:
  Bottom tab bar (not top, not hamburger):
  [Network] [Threats] [Devices] [Honeypot]
  Active tab: amber underline + icon fills
  
Overview tab:
  - Summary cards at top:
    [24 Devices] [2 Alerts] [All Systems]
    Full width, stacked
  - Simplified graph: circular layout (not force-directed on mobile)
    Nodes arranged by risk score, highest at top
  - Recent threat list below (no ribbon on mobile)

Threats tab:
  - Threat cards full width
  - Swipe right: mark as reviewed
  - Swipe left: open detail
  - Pull to refresh

Quick action (floating):
  Single amber floating button bottom-right
  Opens action sheet: "Quarantine", "Redirect", "Scan Now"
  Not always visible — appears when a device is selected

Typography adjustments:
  - Increase body size to 15px (thumb-reading distance)
  - Reduce display sizes by 30%
  - IBM Plex Mono stays same size — technical data must be readable
```

---

## 12. Design Tokens Summary

Quick reference for implementation. Every value the codebase should import:

```javascript
// sentinel/dashboard/lib/tokens.js

export const colors = {
  bg: {
    void:     '#060A12',
    base:     '#0B1120',
    surface:  '#101829',
    elevated: '#162035',
    overlay:  '#1C2A42',
  },
  border: {
    subtle:  '#1E2D45',
    default: '#253552',
    strong:  '#2E4168',
  },
  amber: {
    dim:    '#92540A',
    muted:  '#C4710F',
    base:   '#F59E0B',
    bright: '#FCD34D',
    glow:   'rgba(245, 158, 11, 0.15)',
  },
  semantic: {
    safe:     '#10B981',
    warning:  '#F59E0B',
    critical: '#F43F5E',
    info:     '#6366F1',
  },
  text: {
    primary:   '#E8EDF5',
    secondary: '#8A99B5',
    muted:     '#4A5A78',
    disabled:  '#2E3D58',
    accent:    '#F59E0B',
    code:      '#93C5FD',
  },
  severity: {
    1: '#10B981',
    3: '#34D399',
    5: '#FCD34D',
    6: '#F59E0B',
    8: '#FB923C',
    9: '#F43F5E',
  }
}

export const typography = {
  fonts: {
    display: "'Syne', sans-serif",
    body:    "'Sora', sans-serif",
    mono:    "'IBM Plex Mono', monospace",
  },
  sizes: {
    xs:  '11px', sm: '12px', base: '14px',
    md:  '16px', lg: '20px', xl:  '28px',
    '2xl': '36px', '3xl': '48px',
  }
}

export const animation = {
  duration: {
    instant: '80ms',  fast: '150ms', normal: '250ms',
    slow:    '400ms', breathe: '4000ms',
  },
  easing: {
    out:    'cubic-bezier(0.0, 0.0, 0.2, 1)',
    in:     'cubic-bezier(0.4, 0.0, 1.0, 1)',
    spring: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
  }
}

export const spacing = {
  // 4px base unit
  1: '4px',   2: '8px',   3: '12px',  4: '16px',
  5: '20px',  6: '24px',  8: '32px',  10: '40px',
  12: '48px', 16: '64px', 20: '80px',
}

export const radius = {
  sm: '4px', md: '8px', lg: '12px', xl: '16px', full: '9999px',
}
```

---

## 13. What SENTINEL Must Never Look Like

Screenshots and inspirations to actively avoid:

```
❌ Grafana default dark theme (too many colored lines, no hierarchy)
❌ Kibana security dashboards (information without communication)
❌ pfSense/OPNsense UI (functional but visual disaster)
❌ Any dashboard with purple-to-blue gradients on white
❌ Any dashboard where the sidebar is wider than the content
❌ DataDog's monitor list (table overload, no spatial reasoning)
❌ Generic Tailwind admin templates (they all look identical)
```

And what it should feel like (mood reference, not copy):
```
✅ Linear's issue tracker — calm density, excellent hierarchy
✅ Vercel's deployment dashboard — premium dark, intentional whitespace  
✅ Raycast — everything feels responsive and alive
✅ Apple's iOS health app — data that tells a story
✅ Arc browser sidebar — unexpected but immediately intuitive
```

---

## 14. Implementation Notes for Developers

```
Framework:     Next.js 14 (App Router)
Styling:       Tailwind CSS + CSS custom properties for tokens
Graph:         D3.js v7 — custom force simulation, no charting library
Charts:        Recharts — sparklines and small charts only
Animations:    CSS animations for simple states, Framer Motion for 
               complex sequenced transitions
Icons:         Lucide React (consistent stroke-based icons)
Fonts:         Google Fonts with next/font (preloaded, no FOUT)
WebSocket:     Native WebSocket API, custom hook in lib/websocket.js
State:         Zustand — lightweight, no Redux complexity needed
Push alerts:   Web Push API + service worker

Performance targets:
  - First contentful paint: < 1.2s
  - Largest contentful paint: < 2.5s  
  - Graph renders with 50 nodes at 60fps
  - WebSocket event → UI update: < 50ms
  - No layout shift (CLS = 0) on data updates

Accessibility:
  - WCAG AA minimum for all text/background combinations
  - All interactive elements keyboard navigable
  - Graph has text alternative (screen reader list view)
  - Animations respect prefers-reduced-motion:
    @media (prefers-reduced-motion: reduce) {
      animation-duration: 0.01ms !important;
    }
```

---

*SENTINEL Dashboard Design Specification v1.0*
*Designed for: Final Year Project — charon19d*
*Design language: "Dark Matter" — Calm. Precise. Alive.*
