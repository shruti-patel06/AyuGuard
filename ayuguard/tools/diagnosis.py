"""
AyuGuard Non-Critical Disease Diagnosis Tool
=============================================
Provides safe, non-critical home-care suggestions for mild, self-limiting
conditions identified by the clinical dataset.

SAFETY RULES (hard-coded, not configurable by LLM):
  - NEVER diagnoses conditions outside the SAFE_TO_ADVISE list
  - NEVER diagnoses when urgency is "escalate"
  - NEVER uses words like "you have", "diagnosed", "confirmed"
  - ALWAYS appends the medical disclaimer
  - Similarity score must be >= MIN_SIMILARITY to even attempt home care tips

The LLM receives the output of this function and can only relay it
with the disclaimer intact — it cannot remove the warning.
"""
from __future__ import annotations

# ── Safety lists ─────────────────────────────────────────────────────────────
# Only conditions that are mild, self-limiting, and safe to provide home care for.
SAFE_TO_ADVISE = {
    "fungal infection",
    "allergy",
    "gerd",
    "gastroesophageal reflux disease",
    "common cold",
    "gastroenteritis",
    "migraine",
    "chicken pox",
    "acne",
    "urinary tract infection",
    "impetigo",
    "psoriasis",
    "cervical spondylosis",
    "hypoglycemia",
    "hypothyroidism",
    "hyperthyroidism",
    "bronchial asthma",
    "dimorphic hemmorhoids",
    "dimorphic hemorrhoids",
    "drug reaction",
    "alcoholic hepatitis",
}

# These are NEVER diagnosed — always refer to doctor
NEVER_DIAGNOSE = {
    "heart attack",
    "paralysis",
    "diabetes",
    "tuberculosis",
    "malaria",
    "dengue",
    "typhoid",
    "hepatitis a",
    "hepatitis b",
    "hepatitis c",
    "hepatitis d",
    "hepatitis e",
    "pneumonia",
    "jaundice",
    "aids",
    "chronic cholestasis",
}

# Minimum similarity to even consider home-care advice
MIN_SIMILARITY = 0.25

# Urgency levels that allow diagnosis
DIAGNOSABLE_URGENCY = {"low", "watch"}

# ── Home care knowledge base ──────────────────────────────────────────────────
_HOME_CARE: dict[str, dict] = {
    "fungal infection": {
        "tips": ["Keep affected area clean and dry", "Avoid sharing towels or clothing", "Use breathable cotton fabrics", "Apply antifungal powder if available"],
        "when_to_see_doctor": "If the rash spreads, becomes painful, or does not improve in 5–7 days.",
        "emoji": "🍄",
    },
    "allergy": {
        "tips": ["Identify and avoid the trigger (dust, pollen, food)", "Keep windows closed during high pollen season", "Wash hands frequently", "Antihistamines (if already prescribed) may help"],
        "when_to_see_doctor": "If breathing becomes difficult, throat swells, or reaction is severe — go to doctor immediately.",
        "emoji": "🌸",
    },
    "gerd": {
        "tips": ["Avoid spicy, oily, or acidic foods", "Eat smaller meals more frequently", "Do not lie down immediately after eating — wait at least 2 hours", "Elevate the head of the bed slightly"],
        "when_to_see_doctor": "If symptoms persist more than 2 weeks, or if swallowing becomes painful.",
        "emoji": "🫁",
    },
    "gastroesophageal reflux disease": {
        "tips": ["Avoid spicy, oily, or acidic foods", "Eat smaller meals more frequently", "Do not lie down immediately after eating — wait at least 2 hours", "Elevate the head of the bed slightly"],
        "when_to_see_doctor": "If symptoms persist more than 2 weeks, or if swallowing becomes painful.",
        "emoji": "🫁",
    },
    "common cold": {
        "tips": ["Rest and drink plenty of warm fluids (kadha, warm water with honey and ginger)", "Steam inhalation for congestion", "Gargle with warm salt water for sore throat", "Eat light, warm meals like khichdi or dal soup"],
        "when_to_see_doctor": "If fever goes above 103°F (39.4°C), or symptoms worsen after 7 days.",
        "emoji": "🤧",
    },
    "gastroenteritis": {
        "tips": ["ORS (Oral Rehydration Solution) to prevent dehydration", "Eat light: bananas, rice, toast, boiled potatoes (BRAT diet)", "Avoid dairy, spicy food, and caffeine", "Rest as much as possible"],
        "when_to_see_doctor": "If vomiting or diarrhea lasts more than 2 days, or if there is blood in stool.",
        "emoji": "🫃",
    },
    "migraine": {
        "tips": ["Rest in a quiet, dark room", "Apply a cold or warm compress to the forehead", "Stay hydrated — dehydration can trigger migraines", "Avoid known triggers (bright lights, strong smells, skipping meals)"],
        "when_to_see_doctor": "If this is the worst headache ever experienced, or accompanied by fever, stiff neck, or vision changes.",
        "emoji": "🧠",
    },
    "chicken pox": {
        "tips": ["Keep nails trimmed to avoid scratching", "Calamine lotion can soothe itching", "Wear loose cotton clothing", "Isolate from others who have not had chicken pox"],
        "when_to_see_doctor": "If blisters become infected (red, warm, oozing pus), or if patient has difficulty breathing.",
        "emoji": "🔴",
    },
    "acne": {
        "tips": ["Wash face gently with mild soap twice a day", "Avoid touching the face", "Do not pop or squeeze pimples", "Use non-comedogenic moisturisers"],
        "when_to_see_doctor": "If acne is severe, cystic, or causing significant pain or scarring.",
        "emoji": "✨",
    },
    "urinary tract infection": {
        "tips": ["Drink plenty of water (3–4 litres daily)", "Urinate frequently — do not hold it in", "Avoid caffeine and alcohol", "Maintain personal hygiene"],
        "when_to_see_doctor": "UTIs require antibiotic treatment. Please see a doctor within 1–2 days if burning or pain during urination persists.",
        "emoji": "💧",
    },
    "impetigo": {
        "tips": ["Keep sores clean with mild soap and water", "Cover sores loosely with gauze", "Do not touch or scratch sores", "Wash hands frequently"],
        "when_to_see_doctor": "Impetigo usually requires antibiotic cream. See a doctor soon.",
        "emoji": "🩹",
    },
    "psoriasis": {
        "tips": ["Moisturise skin regularly with fragrance-free lotion", "Avoid hot showers — use lukewarm water", "Manage stress with relaxation techniques", "Wear soft, breathable fabrics"],
        "when_to_see_doctor": "For a formal diagnosis and prescription treatment if plaques are spreading.",
        "emoji": "🧴",
    },
    "cervical spondylosis": {
        "tips": ["Maintain good posture — avoid hunching over a phone or book", "Do gentle neck exercises recommended by a physiotherapist", "Apply warm compress to neck for 10–15 minutes", "Use a low, firm pillow while sleeping"],
        "when_to_see_doctor": "If numbness, tingling in hands/arms, or weakness develops.",
        "emoji": "🦴",
    },
    "hypoglycemia": {
        "tips": ["If feeling dizzy or shaky: eat a small, fast-acting carb (juice, glucose tablet, banana)", "Do not skip meals — eat at regular intervals", "Carry a small snack always", "Monitor blood sugar if diabetic"],
        "when_to_see_doctor": "If blood sugar drops below 70 mg/dL or patient loses consciousness — seek immediate help.",
        "emoji": "🍌",
    },
    "hypothyroidism": {
        "tips": ["Take thyroid medication at the same time each morning on an empty stomach", "Avoid calcium-rich foods 4 hours after medication", "Gentle daily exercise helps manage fatigue", "Ensure adequate iodine in diet (iodised salt)"],
        "when_to_see_doctor": "For regular TSH monitoring — typically every 6 months.",
        "emoji": "🦋",
    },
    "hyperthyroidism": {
        "tips": ["Avoid caffeine and stimulants if heart is racing", "Eat small, frequent, calorie-rich meals if losing weight", "Rest when fatigued — do not overexert", "Keep a symptom diary to share with your doctor"],
        "when_to_see_doctor": "Hyperthyroidism needs medical management. See your doctor soon.",
        "emoji": "⚡",
    },
    "bronchial asthma": {
        "tips": ["Avoid known triggers: dust, smoke, pollen, cold air", "Keep rescue inhaler (if prescribed) nearby at all times", "Use a humidifier in dry weather", "Practice slow breathing exercises"],
        "when_to_see_doctor": "If wheezing is severe, inhaler is not helping, or lips/fingertips turn bluish — go to emergency immediately.",
        "emoji": "🌬️",
    },
    "dimorphic hemmorhoids": {
        "tips": ["Eat high-fibre foods (fruits, vegetables, whole grains)", "Drink plenty of water", "Avoid straining during bowel movements", "Sitz baths (warm water soak) for 15 minutes can reduce discomfort"],
        "when_to_see_doctor": "If bleeding is significant or persistent.",
        "emoji": "🌿",
    },
    "dimorphic hemorrhoids": {
        "tips": ["Eat high-fibre foods (fruits, vegetables, whole grains)", "Drink plenty of water", "Avoid straining during bowel movements", "Sitz baths (warm water soak) for 15 minutes can reduce discomfort"],
        "when_to_see_doctor": "If bleeding is significant or persistent.",
        "emoji": "🌿",
    },
    "drug reaction": {
        "tips": ["Stop the suspected medication if safe to do so and contact your doctor", "Document the medication name, dose, and symptoms", "Drink plenty of water to help clear the medication", "Do not take another dose without medical advice"],
        "when_to_see_doctor": "If rash spreads rapidly, face swells, or breathing becomes difficult — go to emergency immediately.",
        "emoji": "💊",
    },
    "alcoholic hepatitis": {
        "tips": ["Complete rest and abstinence from alcohol", "Stay hydrated with clear fluids", "Eat small, nutritious meals — avoid fatty or processed food", "Ensure regular monitoring by a doctor"],
        "when_to_see_doctor": "Alcoholic hepatitis always needs medical supervision. Please see a doctor.",
        "emoji": "🫀",
    },
}

_DISCLAIMER = (
    "\n\n⚕️ *Important:* This is an informational suggestion based on the symptom "
    "pattern — it is NOT a medical diagnosis. Please always consult your doctor "
    "before making any changes to medication or treatment."
)


def diagnose_non_critical(
    symptom_text: str,
    urgency: str,
    top_disease: str,
    similarity_score: float,
) -> dict:
    """
    Provide safe home-care suggestions for non-critical, self-limiting conditions.

    This function ONLY provides suggestions for conditions in the SAFE_TO_ADVISE list.
    It NEVER diagnoses serious conditions and NEVER overrides the urgency scorer.

    Args:
        symptom_text:     The symptom description string from the trend window.
        urgency:          Urgency level from compute_trend_score() — "low"/"watch"/"escalate".
        top_disease:      The top matching disease from the clinical dataset.
        similarity_score: The similarity score (0–1) from the dataset search.

    Returns:
        dict with:
          - can_diagnose: bool — True if home-care advice can be given
          - condition: str — the matched condition name (only if can_diagnose)
          - emoji: str — condition emoji
          - home_care_tips: list[str] — actionable home-care steps
          - when_to_see_doctor: str — when to escalate
          - disclaimer: str — mandatory medical disclaimer
          - reason_skipped: str — why advice is not given (only if can_diagnose=False)
    """
    disease_lower = (top_disease or "").lower().strip()
    urgency_lower = (urgency or "low").lower().strip()

    # ── Hard safety gates ──────────────────────────────────────────────────────
    if urgency_lower == "escalate":
        return {
            "can_diagnose": False,
            "reason_skipped": "Urgency is 'escalate' — please consult your doctor rather than trying home care.",
            "home_care_tips": [],
            "when_to_see_doctor": "Please see a doctor as soon as possible.",
            "disclaimer": _DISCLAIMER,
        }

    if disease_lower in NEVER_DIAGNOSE:
        return {
            "can_diagnose": False,
            "reason_skipped": f"'{top_disease}' is a condition that requires professional medical assessment. Home-care advice is not appropriate here.",
            "home_care_tips": [],
            "when_to_see_doctor": "Please consult your doctor for proper evaluation and treatment.",
            "disclaimer": _DISCLAIMER,
        }

    if similarity_score < MIN_SIMILARITY:
        return {
            "can_diagnose": False,
            "reason_skipped": f"Symptom pattern similarity is low ({similarity_score:.0%}) — not confident enough to suggest specific home care.",
            "home_care_tips": [],
            "when_to_see_doctor": "If symptoms persist or worsen, please see a doctor.",
            "disclaimer": _DISCLAIMER,
        }

    if disease_lower not in SAFE_TO_ADVISE:
        return {
            "can_diagnose": False,
            "reason_skipped": f"'{top_disease}' is not in the list of conditions safe for home-care advice. Please consult your doctor.",
            "home_care_tips": [],
            "when_to_see_doctor": "Please see a doctor for a proper diagnosis.",
            "disclaimer": _DISCLAIMER,
        }

    # ── Provide home care advice ───────────────────────────────────────────────
    care = _HOME_CARE.get(disease_lower, {})
    tips = care.get("tips", [
        "Rest and stay hydrated",
        "Eat light, nutritious meals",
        "Monitor symptoms and keep a daily log",
    ])
    when_doctor = care.get("when_to_see_doctor", "If symptoms worsen or persist beyond 5–7 days.")
    emoji = care.get("emoji", "🌿")

    confidence_note = ""
    if urgency_lower == "watch":
        confidence_note = (
            " Note: the pattern is building over several days — monitor closely "
            "and mention this at your next doctor visit."
        )

    return {
        "can_diagnose": True,
        "condition": top_disease,
        "emoji": emoji,
        "similarity_percent": round(similarity_score * 100),
        "home_care_tips": tips,
        "when_to_see_doctor": when_doctor + confidence_note,
        "disclaimer": _DISCLAIMER,
    }
