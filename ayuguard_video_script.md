# AyuGuard — 3-Minute Demo Video Script 🎬

---

## ⏱️ STRUCTURE OVERVIEW (Target: 3:10)

| Segment | Time | Focus / Action |
|---|---|---|
| **1. Hook — The Problem** | 0:00–0:30 (30s) | Speak to camera: patterns across time vs. isolated symptoms |
| **2. Architecture & Platform** | 0:30–0:55 (25s) | UI landing page: Google ADK + Vertex AI multi-agent architecture |
| **3. Live Demo — Caregiver Scenario** | 0:55–1:45 (50s) | **Star feature**: three-condition conflict reconciliation (diabetes + hypertension + new kidney finding) |
| **4. Live Demo — Patient Chat** | 1:45–2:15 (30s) | Senior-friendly UI, warm tone, jargon-free translation & instant care plan sync |
| **5. Live Demo — Dashboard & Records** | 2:15–2:45 (30s) | Glassmorphism dashboard, real-time sync, Gemini multimodal PDF lab extraction |
| **6. Closing — The Impact** | 2:45–3:10 (25s) | Speak to camera: ambient care powered by AI |

---

## 🎙️ SEGMENT 1 — THE HOOK (0:00 – 0:30)
**[No screen. Speak directly to camera.]**

> "Imagine caring for your ageing parent at home. Every day something small happens — he's a bit tired, thirsty, not sleeping well. You ask a chatbot, and it says: *'Monitor it.'*
>
> But no symptom in isolation tells the whole story. **Fatigue plus thirst plus blurry vision over 10 days** is a classic metabolic warning sign.
>
> Caregivers don't have the bandwidth to manually track and connect sparse observations across weeks.
>
> **AyuGuard does.**"

---

## 🖥️ SEGMENT 2 — WHAT IS AYUGUARD (0:30 – 0:55)
**[Switch to screen. Show AyuGuard UI at http://127.0.0.1:8001]**

> "This is AyuGuard — an ambient multi-agent caregiver platform built with **Google ADK** and **Vertex AI Gemini 2.5**.
>
> Under the hood, specialized AI subagents collaborate in real-time:
> - **Extraction Subagent** turns free text — in English, Hindi, or Hinglish — into structured medical logs.
> - **Retrieval Subagent** searches 4,921 real clinical dataset rows.
> - **Dietary Reconciliation Subagent** resolves complex, conflicting health conditions."

**[Hover over the tabs: Caregiver Chat / Health Dashboard / Patient Chat / Records]**

---

## 🖥️ SEGMENT 3 — MULTI-AGENT SUBAGENT COLLABORATION (0:55 – 1:45)
**[Click Caregiver tab. Type in chat:]**

`Dad's blood test yesterday showed his creatinine is high and the doctor mentioned his kidneys — but he's still diabetic and has high BP. What can he actually eat now?`

**[Narrate while response streams in real-time:]**

> "Watch what happens here. I'm Priya — and this time it's not one condition colliding with another, it's three at once. Rajan ji is diabetic, he has high blood pressure, and now a new kidney concern just came back from his labs.
>
> Each condition alone has a clear diet. Diabetes wants fiber-rich produce. Blood pressure wants low sodium. But kidney strain changes the rules entirely — some of those same diabetic-friendly fruits and vegetables are high in potassium, which a strained kidney can't clear properly.
>
> AyuGuard's **`dietary_reconciliation_agent`** doesn't just average these out. It recognizes the kidney finding is new and takes priority, reweights the whole plan around it, while still holding the line on sugar and salt — and because this is a *new* diagnosis, it flags that the plan needs the doctor's confirmation before anything sticks permanently.
>
> The moment it resolves, his **Care Plan** on the dashboard updates instantly — no manual entry, no lag."

---

## 🖥️ SEGMENT 4 — PATIENT CHAT EXPERIENCE (1:45 – 2:15)
**[Click Patient Chat tab. Show senior-friendly interface with quick action chips.]**

**[Click chip or type in chat:]**

`What can I eat for lunch today with my new care plan?`

**[Narrate as streaming response appears in warm, reassuring tone:]**

> "Now, look at the patient experience. Seniors shouldn't be overwhelmed by clinical jargon or scary diagnoses.
>
> When Rajan ji switches to **Patient Mode**, AyuGuard greets him in a calming, senior-accessible interface. When he asks what he can eat for lunch, AyuGuard translates complex medical reconciliations into warm, simple, actionable guidance:
>
> *'Hello Rajan ji! Based on your updated care plan, enjoy soft moong dal with rice and steamed bottle gourd today. We're keeping things gentle on your kidneys while keeping your blood sugar stable.'*
>
> The caregiver gets clinical precision; the elderly patient gets gentle, reassuring ambient support."

---

## 🖥️ SEGMENT 5 — DASHBOARD & GEMINI MEDICAL RECORDS (2:15 – 2:45)
**[Click Dashboard tab, scroll through glassmorphism cards & timeline. Then click Records tab.]**

> "Our Health Dashboard features real-time background sync:
> - **Urgency Ring**: calculated deterministically from 14-day symptom persistence and clinical severity weights. The LLM never decides what's dangerous — math does.
> - **Live Notification Engine**: updates caregiver and patient views instantly.
>
> On the **Records tab**, caregivers upload PDF blood reports or discharge summaries. **Gemini AI** extracts abnormal lab values — like elevated HbA1c — and cross-references them with Rajan ji's logged symptoms automatically."

---

## 🎙️ SEGMENT 6 — THE CLOSING (2:45 – 3:10)
**[Back to camera.]**

> "AyuGuard supplements — never replaces — the doctor's advice. It turns reactive caregiving into proactive, ambient monitoring.
>
> Built with Google ADK, Vertex AI, and real clinical datasets —
>
> **AyuGuard is ambient care, powered by AI.**"

---

## ⚡ RECORDING SETUP CHECKLIST

- [ ] Open http://127.0.0.1:8001 in full-screen browser (hide bookmarks bar)
- [ ] Test-type the caregiver & patient demo prompts before recording to verify instant response
- [ ] Clear chat on both Caregiver & Patient tabs using **🗑️ Clear history** right before recording
- [ ] Keep mic clear and pace steady — at 3:10 you have room to articulate both caregiver and patient sides clearly

---

## 🔑 5 KEY LINES TO EMPHASIZE

1. **Safety Line:** *"The LLM never decides what is dangerous — deterministic math does."*
2. **Subagent Innovation:** *"Subagents collaborate to resolve conflicting conditions — even three at once, like diabetes, hypertension, and a new kidney diagnosis."*
3. **Prioritization & Deference:** *"When a new diagnosis appears, the system reprioritizes automatically — and knows to defer to the doctor before finalizing the plan."*
4. **Patient-First Ambient Care:** *"Caregivers get clinical precision; elderly patients get gentle, reassuring, jargon-free guidance that syncs in real-time."*
5. **Core Insight:** *"Connecting patterns across weeks — not symptoms in isolation."*
