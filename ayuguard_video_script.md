# AyuGuard — 3-Minute Demo Video Script

---

## 🎬 STRUCTURE OVERVIEW

| Segment | Time | What you do |
|---|---|---|
| Hook — The Problem | 0:00–0:30 | Speak to camera (no screen) |
| Solution — What is AyuGuard | 0:30–1:00 | Show the UI landing page |
| Live Demo Part 1 — Caregiver Chat | 1:00–1:45 | Type a symptom, show AI response |
| Live Demo Part 2 — Dashboard | 1:45–2:15 | Show urgency ring, trend graph |
| Live Demo Part 3 — Medical Records | 2:15–2:40 | Show record upload / AI analysis |
| Closing — The Why | 2:40–3:00 | Speak to camera |

---

## 🎙️ SEGMENT 1 — THE HOOK (0:00 – 0:30)
**[No screen. Speak directly to camera.]**

> "Imagine you're looking after your ageing parent at home.
> Every day something small happens — he's a little tired, a bit thirsty, not sleeping well.
> You ask an AI chatbot: 'Is this serious?' And it says: 'Monitor it.'
>
> The problem is — no symptom in isolation is serious.
> But fatigue plus thirst plus blurry vision over ten days?
> That is a textbook early warning sign for a metabolic crisis.
>
> No caregiver has the bandwidth to track and connect those dots manually.
> AyuGuard does."

---

## 🖥️ SEGMENT 2 — WHAT IS AYUGUARD (0:30 – 1:00)
**[Switch to screen. Show the AyuGuard UI at http://127.0.0.1:8001]**

> "This is AyuGuard — an ambient multi-agent caregiver platform built with Google ADK and Gemini.
>
> It has three roles in one interface:
> The Caregiver — logs symptoms and manages the care plan.
> The Patient — reports how they feel and sees their updates.
> The AI Agent — connects the dots across days and weeks.
>
> Under the hood it runs a 6-step pipeline —
> free-text symptoms go in, they get extracted into structured data,
> scored against real clinical datasets,
> and a warm personalised message comes out —
> in English, Hindi, or Hinglish."

**[Hover over the 4 tabs: Caregiver / Dashboard / Patient Chat / Records]**

---

## 🖥️ SEGMENT 3 — LIVE DEMO: CAREGIVER CHAT (1:00 – 1:45)
**[Click Caregiver tab. Type in the chat box:]**
**→ Type:** `Dad was very tired and very thirsty today`

**[While waiting for the response, narrate:]**

> "I'm Priya — the caregiver — logging what I noticed about my father Rajan today.
> AyuGuard doesn't just answer my question.
> It runs the full pipeline in the background:
>
> First — it extracts the symptoms from my natural language.
> Second — it stores them in a rolling 14-day log.
> Third — it runs a deterministic urgency formula.
> The AI never decides what's dangerous. The math does.
> Fourth — it cross-references against 4,921 real clinical records.
> And then it writes me a warm, contextual message."

**[Show the response]**

> "Notice how it addresses me by name, refers to my father by name,
> and gives me a specific next step — not just 'monitor it'."

---

## 🖥️ SEGMENT 4 — LIVE DEMO: HEALTH DASHBOARD (1:45 – 2:15)
**[Click Dashboard tab. Scroll slowly as you speak.]**

> "Here is the Health Dashboard.
>
> This urgency ring shows the current alert level — Low, Watch, or Escalate —
> calculated from 14 days of symptom logs using a weighted formula:
> symptom similarity to disease clusters,
> how many days the pattern has persisted,
> and clinical severity scores from a real medical dataset.
>
> This chart shows symptom frequency — so Priya can see at a glance
> that fatigue has been the top symptom this fortnight.
>
> And the care plan below shows the meals, medications, and activities
> she has set up for Rajan ji today."

---

## 🖥️ SEGMENT 5 — LIVE DEMO: MEDICAL RECORDS (2:15 – 2:40)
**[Click Records tab.]**

> "Caregivers can also upload medical documents here —
> blood test reports, prescriptions, discharge summaries.
>
> AyuGuard uses Gemini's multimodal capability to read the document and extract
> abnormal lab values flagged as HIGH or LOW,
> medications mentioned,
> and follow-up recommendations.
>
> And here's the powerful part:
> If Rajan's HbA1c is flagged HIGH in his blood report
> AND he's been logging fatigue and thirst for 10 days —
> AyuGuard connects those dots across both sources and surfaces that pattern."

---

## 🎙️ SEGMENT 6 — THE CLOSING (2:40 – 3:00)
**[Back to camera.]**

> "AyuGuard is not a diagnostic tool.
> It never says 'you have diabetes.'
> It says: 'This pattern is sometimes associated with — please mention it to your doctor.'
>
> It's designed to be the difference between a caregiver who is reacting
> and a caregiver who is prepared.
>
> Built with Google ADK, Gemini, and real clinical datasets —
> AyuGuard is ambient care, powered by AI."

---

## ⚡ BEFORE YOU RECORD — SETUP CHECKLIST

- [ ] Run `python scripts/seed_demo_logs.py` so the Dashboard shows real trend data
- [ ] Open http://127.0.0.1:8001 in full-screen browser (hide bookmarks bar)
- [ ] Do a test run of the chat — make sure AI responds correctly
- [ ] Keep mic close, speak slowly — 3 minutes is tighter than it sounds

---

## 🔑 5 KEY PHRASES TO MEMORISE

| Moment | Line |
|---|---|
| Urgency formula | "The AI never decides what's dangerous — the formula does" |
| Response tone | "It speaks like a caring family member, not a doctor" |
| Safety boundary | "It supplements, never replaces, the doctor's advice" |
| Dataset credibility | "4,921 real clinical records — not invented by the LLM" |
| Core insight | "Patterns across days — not symptoms in isolation" |
