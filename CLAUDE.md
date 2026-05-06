Here's a clean, agent-ready project brief. No fluff, no ambiguity, just enough structure for execution.

---

## 🧠 Project: Virtual Body Double

### 🎯 Objective

Build a **local-first system** that observes a user's digital behavior during focus sessions and **detects deviations from intended work**, then intervenes in a configurable way — from a gentle nudge to an active blocker.

The system should function as a **real-time attention monitor** that adapts to how much enforcement the user wants.

---

## 🧩 Core Capabilities

### 1. Behavior Tracking

Capture user activity across the system:

* Active application (foreground window)
* Window title
* Browser tab (URL + title)
* Timestamped events
* Idle vs active time

---

### 2. Context Aggregation

Convert raw event streams into structured sessions:

* Group continuous activity into time blocks
* Detect context switches (e.g., VSCode → YouTube)
* Maintain a timeline of user behavior

---

### 3. Focus Mode (Intent Definition)

Allow user to define a session goal:

* Example: "coding backend", "studying transformers"
* Optional:

  * Allowed domains/apps (allowlist)
  * Session duration
  * Intervention mode: nudge or block

This becomes the **reference intent** for evaluation.

---

### 4. Deviation Detection

Determine whether current behavior aligns with intent.

#### MVP (rule-based):

* Match URLs/domains against a distraction list or outside the allowlist
* Detect time spent outside allowed contexts

#### Later (ML-enhanced):

* Compute semantic similarity between:

  * User intent
  * Current page content/title
* Flag low-relevance activity as potential distraction

---

### 5. Intervention System

Two modes, user-selectable per session:

#### Nudge Mode (default)

* Non-intrusive desktop notification when distraction detected
* Examples: "You switched to YouTube. Intentional?", "We were coding. Want to go back?"

#### Block Mode (focus mode)

* Browser extension intercepts navigation to disallowed URLs
* Redirects to a local block page instead of loading the site
* Block page shows current task intent and offers a conscious override ("Let me through anyway")
* Windows agent can optionally minimize windows of disallowed apps
* Override adds friction, not a hard wall — intentional choice is always possible

Requirements:

* Real-time (low latency)
* Context-aware (avoid false positives)
* Override always available — system assists focus, never removes agency

---

### 6. Feedback Loop (optional, later)

Allow user to confirm or dismiss nudges:

* Improve future detection
* Personalize behavior model

---

## 🏗️ System Architecture

### Components

#### 1. Windows Agent

* Tracks active window and system-level behavior
* Sends events to local server
* In block mode: can minimize disallowed app windows

#### 2. Browser Extension

* Tracks active tab (URL + title)
* Sends events to local server
* In block mode: intercepts navigation, checks against server session allowlist, redirects to block page

#### 3. Local Server (Core Engine)

* Receives events
* Stores and aggregates behavior
* Manages focus sessions (start/end, intent, allowlist, mode)
* Runs deviation detection
* Triggers nudges or signals blocks

#### 4. Nudger

* Displays notifications or interventions to user

#### 5. Storage

* Local database (SQLite)
* Stores events and session data

---

## 🔄 Data Flow

### Nudge Mode
1. Agent + Extension emit events
2. Events sent to local server via HTTP
3. Server stores event, evaluates deviation
4. If distracted → trigger nudge notification

### Block Mode
1. User starts session: `POST /session/start` with intent + allowlist
2. Extension checks every navigation: `GET /session/check?url=...`
3. Server returns `allowed: true/false`
4. If blocked → extension redirects to local block page
5. User can override (logged) or go back
6. `POST /session/end` clears the block

---

## 📦 Data Models

### Event
```json
{
  "timestamp": 1710000000,
  "app": "chrome.exe",
  "title": "YouTube - Video Title",
  "url": "https://youtube.com/..."
}
```

### Session
```json
{
  "intent": "coding backend",
  "mode": "block",
  "allowed_domains": ["github.com", "docs.python.org"],
  "started_at": 1710000000,
  "duration_minutes": 90
}
```

---

## ⚙️ Constraints

* Must run on **CPU-only systems**
* Must be **local-first (privacy-preserving)**
* Must be **low-latency** (real-time detection)
* Must be **lightweight** (background process)

---

## 🚀 MVP Scope (Strict)

The first working version must:

* Track active window (Windows)
* Track browser tabs (via extension)
* Send events to local server
* Support nudge mode: detect distraction via simple rules and show toast notification
* Support block mode: extension intercepts and redirects disallowed URLs, server manages session allowlist

---

## ❌ Out of Scope (for MVP)

* Complex ML models
* Full-page content analysis
* Cross-device tracking
* Cloud sync
* Advanced UI

---

## 🧠 Future Extensions

* Semantic relevance detection (embeddings)
* Personalized distraction patterns
* Predictive nudging
* Focus scoring and analytics
* Passive "presence" simulation (cursor, overlays)

---

## 🧪 Success Criteria

The system is considered functional when:

* It reliably detects when the user switches to a distracting site
* In nudge mode: triggers a notification within a few seconds
* In block mode: prevents navigation to disallowed sites, with override available
* It does not significantly impact system performance
* It runs continuously without crashing

---

## 🧭 Guiding Principle

The system should feel like:

> a **supportive presence that notices drift**

The user chooses how firm that presence is — from a gentle reminder to an active focus enforcer. It is never a surveillance tool or a productivity dashboard.
