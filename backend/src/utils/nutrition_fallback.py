"""
nutrition_fallback.py
---------------------
Rule-based nutrition advice fallback when Gemini API is unavailable.

Always returns TEXT-based nutrition advice. NEVER generates images.
Maps common symptoms/conditions to evidence-based dietary recommendations.

Rules:
    - Pure functions only.
    - No LLM calls.
    - No image generation.
    - No state mutation.
"""

from typing import List, Dict

# Symptom → nutrition mapping (evidence-based, conservative advice)
_SYMPTOM_NUTRITION_MAP: Dict[str, dict] = {
    "fever": {
        "dietary_recommendations": [
            "Drink plenty of warm fluids like soups and herbal teas",
            "Eat light foods like rice porridge, toast, and bananas",
            "Include fruits rich in vitamin C (oranges, kiwi, guava)",
            "Consume easily digestible proteins like boiled eggs or dal",
        ],
        "foods_to_avoid": [
            "Spicy and oily foods",
            "Caffeine and alcohol",
            "Heavy dairy products like cheese",
        ],
        "hydration_advice": "Drink at least 8-10 glasses of water daily. Add ORS if dehydrated.",
        "lifestyle_advice": "Rest adequately and avoid strenuous activity until fever subsides.",
    },
    "headache": {
        "dietary_recommendations": [
            "Stay well hydrated — dehydration is a common headache trigger",
            "Eat magnesium-rich foods: spinach, almonds, dark chocolate",
            "Include omega-3 rich foods: walnuts, flaxseeds",
            "Eat small, regular meals to maintain stable blood sugar",
        ],
        "foods_to_avoid": [
            "Aged cheeses and processed meats (contain tyramine)",
            "Excessive caffeine or sudden caffeine withdrawal",
            "Alcohol, especially red wine",
            "MSG-containing processed foods",
        ],
        "hydration_advice": "Drink 8-10 glasses of water. Dehydration headaches are very common.",
        "lifestyle_advice": "Ensure regular sleep schedule and take breaks from screens every 30 minutes.",
    },
    "stomach": {
        "dietary_recommendations": [
            "Follow the BRAT diet: bananas, rice, applesauce, toast",
            "Sip ginger tea or peppermint tea for nausea relief",
            "Eat small, frequent meals instead of large ones",
            "Include probiotics like yogurt or buttermilk",
        ],
        "foods_to_avoid": [
            "Spicy, fried, and fatty foods",
            "Raw vegetables and high-fiber foods temporarily",
            "Carbonated drinks and citrus juices",
            "Dairy products if lactose intolerant",
        ],
        "hydration_advice": "Sip clear fluids frequently. Try coconut water or diluted fruit juice.",
        "lifestyle_advice": "Eat slowly, chew thoroughly, and avoid lying down immediately after eating.",
    },
    "cold": {
        "dietary_recommendations": [
            "Warm chicken soup or vegetable broth",
            "Honey and ginger tea (natural soothing remedy)",
            "Citrus fruits for vitamin C (oranges, lemons)",
            "Garlic and turmeric in warm milk or food",
        ],
        "foods_to_avoid": [
            "Cold beverages and ice cream",
            "Sugary processed foods",
            "Heavy fried foods",
        ],
        "hydration_advice": "Drink warm fluids throughout the day. Honey-lemon water is excellent.",
        "lifestyle_advice": "Get extra rest and keep warm. Steam inhalation can help with congestion.",
    },
    "pain": {
        "dietary_recommendations": [
            "Anti-inflammatory foods: turmeric, ginger, berries",
            "Omega-3 rich foods: fish, flaxseeds, walnuts",
            "Leafy greens rich in vitamins and minerals",
            "Whole grains for sustained energy",
        ],
        "foods_to_avoid": [
            "Processed foods with artificial additives",
            "Excessive sugar which can increase inflammation",
            "Alcohol which can worsen pain sensitivity",
        ],
        "hydration_advice": "Stay hydrated with water and herbal teas. Avoid excess caffeine.",
        "lifestyle_advice": "Gentle stretching and movement can help. Apply warm compresses to sore areas.",
    },
    "default": {
        "dietary_recommendations": [
            "Eat a balanced diet with plenty of fruits and vegetables",
            "Include whole grains, lean proteins, and healthy fats",
            "Consume foods rich in vitamin C and antioxidants",
            "Stay hydrated and eat light, easily digestible meals",
        ],
        "foods_to_avoid": [
            "Highly processed and junk foods",
            "Excessive sugar and artificial sweeteners",
            "Alcohol and excessive caffeine",
        ],
        "hydration_advice": "Drink at least 8 glasses of water daily. Include herbal teas.",
        "lifestyle_advice": "Maintain regular meal times, get adequate sleep, and include light physical activity.",
    },
}


def get_fallback_nutrition(symptoms: List[str], risk_level: str = "low") -> dict:
    """
    Returns rule-based nutrition advice based on symptoms.
    
    TEXT ONLY — never generates or requests images.

    Args:
        symptoms: List of symptom keywords.
        risk_level: Current risk assessment level.

    Returns:
        dict: Structured nutrition advice with dietary_recommendations,
              foods_to_avoid, hydration_advice, lifestyle_advice,
              and confidence_score.
    """
    if not symptoms:
        base = _SYMPTOM_NUTRITION_MAP["default"].copy()
        base["confidence_score"] = 0.5
        return base

    # Find best matching symptom category
    matched_category = "default"
    for symptom in symptoms:
        symptom_lower = symptom.lower()
        for category in _SYMPTOM_NUTRITION_MAP:
            if category != "default" and category in symptom_lower:
                matched_category = category
                break
        if matched_category != "default":
            break

    result = _SYMPTOM_NUTRITION_MAP[matched_category].copy()
    result["confidence_score"] = 0.7 if matched_category != "default" else 0.5

    # Add risk-specific advice
    if risk_level in ("moderate", "high"):
        result["lifestyle_advice"] += " Consider consulting a nutritionist alongside your doctor."

    return result
