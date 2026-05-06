# 👻 Body Double (MVP)

A local-first "virtual body double" that observes your behavior and nudges you when you drift from focus.

---

## 🚀 Features (MVP)

- Tracks active Windows applications
- Tracks browser tabs (via extension)
- Detects distraction (rule-based)
- Sends gentle nudges

---

## 🧱 Architecture

- `agent/` → Tracks active window (Windows)
- `extension/` → Tracks browser tabs
- `server/` → Decision engine (FastAPI)
- `nudger/` → Sends notifications

---

## ⚙️ Setup

### 1. Clone repo

```bash
git clone <repo-url>
cd body-double