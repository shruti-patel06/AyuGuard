# AyuGuard — 2.5-Minute Demo Video Script 🎬

---

## ⏱️ STRUCTURE OVERVIEW (Target: 2 min 30 sec)

| Segment | Duration | Focus / Action |
|---|---|---|
| **1. Hook — The Problem** | 0:00–0:25 (25s) | Speak to camera: Patterns across time vs isolated symptoms |
| **2. Architecture & Platform** | 0:25–0:50 (25s) | Show UI landing page: Google ADK + Vertex AI multi-agent architecture |
| **3. Live Demo — Multi-Agent Subagent Collaboration** | 0:50–1:40 (50s) | **Star Feature**: Pre-diabetes + Diarrhoea conflict reconciliation & recovery transition |
| **4. Live Demo — Health Dashboard & Medical Records** | 1:40–2:15 (35s) | Glassmorphism dashboard, real-time sync, Gemini multimodal PDF lab extraction |
| **5. Closing — The Impact** | 2:15–2:30 (15s) | Speak to camera: Ambient care powered by AI |

---

## 🎙️ SEGMENT 1 — THE HOOK (0:00 – 0:25)
**[No screen. Speak directly to camera.]**

> "Imagine caring for your ageing parent at home. Every day something small happens — he's a bit tired, thirsty, not sleeping well. You ask a chatbot, and it says: *'Monitor it.'*
> 
> But no symptom in isolation tells the whole story. **Fatigue plus thirst plus blurry vision over 10 days** is a classic metabolic warning sign.
> 
> Caregivers don't have the bandwidth to manually track and connect sparse observations across weeks. **AyuGuard does.**"

---

## 🖥️ SEGMENT 2 — WHAT IS AYUGUARD (0:25 – 0:50)
**[Switch to screen. Show AyuGuard UI at http://127.0.0.1:8001]**

> "This is AyuGuard — an ambient multi-agent caregiver platform built with **Google ADK** and **Vertex AI Gemini 2.5**.
> 
> Under the hood, specialized AI subagents collaborate in real-time:
> - **Extraction Subagent** turns free text (in English, Hindi, or Hinglish) into structured medical logs.
> - **Retrieval Subagent** searches 4,921 real clinical dataset rows.
> - **Dietary Reconciliation Subagent** resolves complex, conflicting health conditions."

**[Hover over the tabs: Caregiver Chat / Health Dashboard / Patient Chat / Records]**

---

## 🖥️ SEGMENT 3 — MULTI-AGENT SUBAGENT COLLABORATION (0:50 – 1:40)
**[Click Caregiver tab. Type in chat:]**
`Dad has developed diarrhoea today. What should we feed him considering his pre-diabetes?`

**[Narrate while response streams in real-time:]**

> "Watch what happens here. I'm Priya — logging an acute symptom for my father Rajan ji.
> 
> Normally, a pre-diabetes diet requires high fiber. But acute diarrhoea requires low fiber. High fiber during diarrhoea accelerates gut motility and worsens dehydration.
> 
> AyuGuard's **`dietary_reconciliation_agent`** recognizes this conflict instantly. It reconciles the two conditions, formulates a temporary low-fiber, bland, glycemic-safe diet (*bananas, soft white rice with moong dal, ORS*), and automatically updates his **Care Plan** on the dashboard in real-time!"

**[Now type:]**
`Dad has completely recovered from diarrhoea today!`

**[Narrate response:]**

> "And when I report recovery, the subagent automatically de-escalates the acute diet and transitions his care plan right back to his healthy baseline pre-diabetes schedule."

---

## 🖥️ SEGMENT 4 — DASHBOARD & GEMINI MEDICAL RECORDS (1:40 – 2:15)
**[Click Dashboard tab, scroll through glassmorphism cards & timeline.]**

> "Our Health Dashboard features real-time background sync:
> - **Urgency Ring**: Calculated deterministically from 14-day symptom persistence and clinical severity weights. The LLM never decides what's dangerous — math does.
> - **Live Notification Engine**: Updates caregiver and patient views instantly.
> 
> On the **Records tab**, caregivers upload PDF blood reports or discharge summaries. **Gemini AI** extracts abnormal lab values — like elevated HbA1c — and cross-references them with Rajan ji's logged symptoms automatically."

---

## 🎙️ SEGMENT 5 — THE CLOSING (2:15 – 2:30)
**[Back to camera.]**

> "AyuGuard supplements — never replaces — the doctor's advice. It turns reactive caregiving into proactive, ambient monitoring.
> 
> Built with Google ADK, Vertex AI, and real clinical datasets — AyuGuard is ambient care, powered by AI."

---

## ⚡ RECORDING SETUP CHECKLIST

- [ ] Open http://127.0.0.1:8001 in full-screen browser (hide bookmarks bar).
- [ ] Test typing the two demo prompts before recording to verify instant response.
- [ ] Clear chat using **`🗑️ Clear history`** button right before starting recording.
- [ ] Keep mic clear and pace steady — 2.5 minutes is fast, crisp, and high-impact!

---

## 🔑 4 KEY LINES TO EMPHASIZE

1. **Safety Line:** *"The LLM never decides what is dangerous — deterministic math does."*
2. **Subagent Innovation:** *"Subagents collaborate to resolve conflicting conditions like Pre-diabetes and Diarrhoea."*
3. **Recovery Lifecycle:** *"When symptoms resolve, the care plan automatically transitions back to baseline."*
4. **Core Insight:** *"Connecting patterns across weeks — not symptoms in isolation."*
