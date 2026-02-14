# NutriTwin Backend Architecture

**Production-ready CosyLab-first food intelligence engine**

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT REQUEST                                       │
│                    (recipe_name, ingredients?, allergens?, avoid?)                 │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         FALLBACK ROUTER (Orchestrator)                            │
│                                                                                   │
│   ┌─────────────────────┐     Success      ┌─────────────────────────────────┐   │
│   │ Try CosyLab APIs    │ ───────────────► │ CosyLab Pipeline (Primary)      │   │
│   │ (RecipeDB+FlavorDB) │                  │ - Health Score (WHO)             │   │
│   └─────────┬───────────┘                  │ - Risky Detection                │   │
│             │                              │ - Swap Generation (FlavorDB)     │   │
│             │ Failure                      │ - Sentence-Transformer Rerank    │   │
│             │ (timeout/503/empty/rate)     └─────────────────────────────────┘   │
│             ▼                                                                     │
│   ┌─────────────────────┐                                                         │
│   │ LLM Fallback        │                                                         │
│   │ - Heuristic nutrit  │                                                         │
│   │ - Risky inference    │                                                         │
│   │ - Swap proposals    │                                                         │
│   │ - ST re-rank still  │                                                         │
│   └─────────────────────┘                                                         │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              OUTPUT                                               │
│   Health Profile │ Potential Profile │ Swap Suggestions │ Explanation             │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                     COMPONENT RESPONSIBILITY MATRIX                               │
├──────────────────┬──────────────────────────────────────────────────────────────┤
│ CosyLab RecipeDB │ Nutrition, ingredients, recipes, search                       │
│ CosyLab FlavorDB │ Flavor profiles, flavor similarity, entity relationships      │
│ Rule Engine      │ WHO scoring, penalties/bonuses, swap filtering, aggregation   │
│ Sentence-Transf. │ Semantic re-ranking ONLY; NO API calls; local cosine similarity│
│ LLM (Gemini)     │ ONLY on CosyLab failure; heuristic nutrition, swaps, explain  │
└──────────────────┴──────────────────────────────────────────────────────────────┘
```

---

## 2. WHO-Based Health Scoring Model

### 2.1 WHO Reference Values (per day, adult)

| Nutrient | WHO Limit | Per 2000 kcal | Per Serving (N servings/day) |
|----------|-----------|---------------|------------------------------|
| Free sugars | < 10% energy | < 50 g | < 50/N g |
| Saturated fat | < 10% energy | < 22 g | < 22/N g |
| Trans fat | < 1% energy | < 2.2 g | < 2.2/N g |
| Sodium | < 5 g salt | < 2 g Na | < 2/N g |
| Fiber | ≥ 25 g | ≥ 25 g | ≥ 25/N g |
| Protein | 10–15% energy | 50–75 g | 50/N – 75/N g |

*Energy: 2000 kcal reference. Serving-based: divide by N where N = expected servings from recipe.*

### 2.2 Mathematical Scoring Model

```
BASE_SCORE = 100

MACRO_PENALTIES (each 0–20, max 60):
  sugar_penalty    = min(20, max(0, (sugar_g - sugar_limit) / sugar_limit * 20))
  sat_fat_penalty  = min(20, max(0, (sat_fat_g - sat_limit) / sat_limit * 20))
  trans_fat_penalty= min(20, max(0, trans_fat_g * 10))  # any trans is bad
  sodium_penalty   = min(20, max(0, (sodium_mg/1000 - sodium_limit_g) / sodium_limit_g * 20))

FIBER_BONUS (0–15):
  fiber_bonus = min(15, (fiber_g / fiber_target) * 15)   # cap at 15

WHO_COMPLIANCE_BONUS (0–10):
  whole_grain_bonus = has_whole_grain ? 5 : 0
  plant_diversity   = min(5, unique_plant_categories * 1.5)  # fruits, veg, legume, nut

PROCESSED_PENALTY (0–25):
  ultra_processed_count = count(ingredients in ULTRA_PROCESSED_SET)
  processed_penalty = min(25, ultra_processed_count * 5)

HEALTH_SCORE = BASE_SCORE
             - sugar_penalty
             - sat_fat_penalty
             - trans_fat_penalty
             - sodium_penalty
             - processed_penalty
             + fiber_bonus
             + whole_grain_bonus
             + plant_diversity

FINAL_SCORE = clip(HEALTH_SCORE, 0, 100)
```

### 2.3 Per-Serving Normalization

For a recipe yielding N servings:
```
sugar_limit_per_serving   = 50 / N
sat_fat_limit_per_serving = 22 / N
trans_fat_limit_per_serving = 2.2 / N
sodium_limit_per_serving  = 2 / N   (g Na)
fiber_target_per_serving  = 25 / N
```

### 2.4 Risky Ingredient Detection Rules

```python
RISKY_CATEGORIES = {
    "ultra_processed": ["modified starch", "hydrogenated", "high fructose", "maltodextrin", ...],
    "refined_sugar": ["white sugar", "brown sugar", "corn syrup", "dextrose", ...],
    "high_sodium": ["salt", "soy sauce", "msg", "sodium benzoate", ...],
    "high_sat_fat": ["butter", "lard", "palm oil", "cream", ...],
    "trans_fat": ["shortening", "margarine", "hydrogenated oil", ...],
    "artificial": ["aspartame", "sucralose", "red 40", "bha", "bht", ...],
}

def is_risky(ingredient, nutrition_per_serving):
    keyword_match = any(kw in ingredient for cat, kws in RISKY_CATEGORIES for kw in kws)
    nutrition_match = (
        nutrition_per_serving["sugar"] > 15 or
        nutrition_per_serving["sodium"] > 0.4 or  # 400mg
        nutrition_per_serving["saturated_fat"] > 5 or
        nutrition_per_serving["trans_fat"] > 0.1
    )
    return keyword_match or nutrition_match
```

---

## 3. Health Profile + Potential Profile

### 3.1 Health Profile (Current State)

```json
{
  "schema_version": "1.0",
  "health_profile": {
    "overall_score": 68,
    "diet_category": "High_Carb",
    "balance_score": 0.72,
    "nutritional_density": 0.65,
    "risk_flags": ["high_sugar", "low_fiber"],
    "strengths": ["adequate_protein", "low_trans_fat"],
    "weaknesses": ["excess_sugar", "fiber_deficiency"],
    "breakdown": {
      "macros": {
        "carb_pct": 55,
        "protein_pct": 18,
        "fat_pct": 27,
        "sugar_pct_of_energy": 14,
        "sat_fat_pct_of_energy": 8
      },
      "penalties": {
        "sugar": 8,
        "saturated_fat": 0,
        "trans_fat": 0,
        "sodium": 4,
        "processed": 5
      },
      "bonuses": {
        "fiber": 6,
        "whole_grain": 0,
        "plant_diversity": 3
      }
    },
    "risky_ingredients": [
      {"name": "white sugar", "reason": "refined_sugar", "priority": 4}
    ]
  }
}
```

### 3.2 Potential Profile (Achievable Best)

```
POTENTIAL_SCORE = theoretical best if all risky ingredients swapped optimally

For each risky ingredient R:
  candidates = FlavorDB.get_similar(R) ∩ WHO_compliant_filter
  best_swap = argmax(0.5*flavor + 0.4*health + 0.1*semantic) over candidates
  projected_nutrition += nutrition_delta(R → best_swap)

POTENTIAL_SCORE = WHO_score(projected_nutrition)
IMPROVEMENT_HEADROOM = (POTENTIAL_SCORE - CURRENT_SCORE) / (100 - CURRENT_SCORE) * 100
```

```json
{
  "potential_profile": {
    "theoretical_best_score": 82,
    "improvement_headroom_pct": 43.75,
    "primary_limiting_factors": ["white sugar", "refined flour"],
    "blockers": [
      {"ingredient": "white sugar", "reason": "excess_free_sugar", "max_improvement": 8}
    ],
    "projected_breakdown": { ... }
  }
}
```

---

## 4. Swap Generation (CosyLab-Only)

### 4.1 Flow

```
1. Identify unhealthy ingredient (Rule Engine)
2. candidates = FlavorDB.get_entities_by_readable_name(ingredient)
   → get flavor profile
   → FlavorDB.get_similar_flavors() or molecule-overlap graph
3. Filter: candidates that improve WHO compliance
   - RecipeDB nutrition lookup for each candidate
   - Keep only if: sugar_delta ≤ 0, sodium_delta ≤ 0, sat_fat_delta ≤ 0
4. Score each candidate:
   flavor_similarity = FlavorDB.calculate_similarity(original, candidate)
   health_improvement = WHO_score_delta(swap)  # 0–100
   semantic_similarity = SentenceTransformer.encode(original, candidate) → cosine
5. rank = 0.5 × flavor + 0.4 × health + 0.1 × semantic
6. Return top-k swaps
```

### 4.2 Swap Rules

| Rule | Constraint |
|------|------------|
| Calorie cap | Replacement must not increase calories > 15% per ingredient share |
| Cooking function | Same category (fat, sweetener, binder, etc.) |
| Cuisine | Preserve regional integrity (e.g. olive oil for Mediterranean) |
| Category match | Substitute must be in same functional category |

### 4.3 Swap Output Schema

```json
{
  "original": "butter",
  "replacement": "olive oil",
  "health_delta": 6.2,
  "flavor_delta": -5,
  "semantic_score": 72,
  "explanation": "Replaces saturated fat with monounsaturated fat; similar cooking role.",
  "who_improvements": ["saturated_fat", "trans_fat"],
  "caveats": ["Lower smoke point; adjust heat."
}
```

---

## 5. Strict Fallback Logic

### 5.1 CosyLab Failure Detection

```python
def is_cosylab_failure(response_or_exception):
    if response_or_exception is None:
        return True
    if isinstance(response_or_exception, TimeoutError):
        return True
    if isinstance(response_or_exception, requests.HTTPError):
        return response_or_exception.response.status_code in (401, 403, 429, 500, 502, 503)
    if response is dict/list and (empty or "error" in response):
        return True
    return False
```

### 5.2 Fallback Router Pseudocode

```python
def analyze_recipe(request):
    cosylab_ok = False
    try:
        # 1. Try RecipeDB
        recipe = recipedb.fetch_recipe(request.recipe_name)
        if not recipe or not recipe.get("ingredients"):
            raise CosyLabUnavailable("RecipeDB empty")

        nutrition = recipedb.fetch_nutrition(recipe["id"])
        micro = recipedb.fetch_micro_nutrition(recipe["id"])
        if not nutrition:
            raise CosyLabUnavailable("Nutrition empty")

        # 2. Try FlavorDB for each risky ingredient
        risky = identify_risky(recipe["ingredients"], nutrition)
        swap_candidates = {}
        for r in risky:
            fp = flavordb.get_flavor_profile(r.name)
            if fp:
                swap_candidates[r] = flavordb.get_similar_entities(fp)

        cosylab_ok = True

    except (Timeout, requests.RequestException, CosyLabUnavailable) as e:
        log.warning("CosyLab failed: %s", e)
        cosylab_ok = False

    if cosylab_ok:
        # PRIMARY: CosyLab pipeline
        health_score = who_score(nutrition, micro, recipe["ingredients"])
        health_profile = build_health_profile(health_score, nutrition, risky)
        swaps = generate_swaps_cosylab(risky, flavordb, recipedb)
        swaps = sentence_transformer_rerank(swaps)  # ALWAYS runs
        potential = compute_potential(recipe, swaps, health_score)
    else:
        # FALLBACK: LLM only
        nutrition = llm_estimate_nutrition(recipe_name, ingredients)
        risky = llm_identify_risky(ingredients)
        swaps = llm_propose_swaps(risky, ingredients)
        swaps = sentence_transformer_rerank(swaps)  # ST still active
        health_score = who_score(nutrition, ...)  # Use heuristic nutrition
        health_profile = build_health_profile(...)
        potential = compute_potential(...)

    return {
        "health_profile": health_profile,
        "potential_profile": potential,
        "swap_suggestions": swaps,
    }
```

### 5.3 LLM Must NOT Run in Parallel

```
WRONG:  if USE_LLM: llm_run() else cosylab_run()
RIGHT:  try cosylab_run() except: llm_run()
```

---

## 6. Sentence-Transformer Contract

```python
# MUST:
# - Run locally only
# - NOT call CosyLab
# - NOT replace CosyLab for swap discovery
# - ONLY re-rank existing candidates

def semantic_rerank(original: str, candidates: List[Dict]) -> List[Dict]:
    """
    candidates: [{"name": "olive oil", "flavor_match": 70, "health_improvement": 8}, ...]
    Returns: same list, re-sorted by rank = 0.5*flavor + 0.4*health + 0.1*semantic
    """
    texts = [original] + [c["name"] for c in candidates]
    embs = model.encode(texts)
    orig_emb = embs[0]
    cand_embs = embs[1:]
    semantic_scores = [cosine_sim(orig_emb, e) * 50 + 50 for e in cand_embs]  # 0-100
    for c, s in zip(candidates, semantic_scores):
        c["semantic_score"] = s
        c["rank"] = 0.5*c["flavor_match"] + 0.4*c["health_improvement"] + 0.1*s
    return sorted(candidates, key=lambda x: x["rank"], reverse=True)
```

---

## 7. Database Structure (If Needed)

```sql
-- Recipe cache (reduce CosyLab calls)
CREATE TABLE recipe_cache (
    id UUID PRIMARY KEY,
    recipe_name VARCHAR(255) UNIQUE NOT NULL,
    cosylab_recipe_id VARCHAR(64),
    ingredients JSONB,
    nutrition JSONB,
    micro_nutrition JSONB,
    fetched_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
);

-- Analysis results (audit / ML)
CREATE TABLE analysis_log (
    id UUID PRIMARY KEY,
    recipe_name VARCHAR(255),
    source VARCHAR(16),  -- 'cosylab' | 'llm_fallback'
    health_score FLOAT,
    health_profile JSONB,
    potential_profile JSONB,
    swap_suggestions JSONB,
    created_at TIMESTAMPTZ
);

-- API availability tracking
CREATE TABLE api_health (
    id UUID PRIMARY KEY,
    api_name VARCHAR(32),  -- 'recipedb' | 'flavordb'
    status VARCHAR(16),   -- 'ok' | 'fail'
    response_time_ms INT,
    error_message TEXT,
    checked_at TIMESTAMPTZ
);
```

---

## 8. JSON Schema Summary

### Health Score Response

```json
{
  "overall_score": "number 0-100",
  "rating": "Excellent|Good|Decent|Bad|Poor",
  "breakdown": {
    "base": 100,
    "penalties": { "sugar": 0, "sat_fat": 0, "trans_fat": 0, "sodium": 0, "processed": 0 },
    "bonuses": { "fiber": 0, "whole_grain": 0, "plant_diversity": 0 }
  }
}
```

### Full Analysis Response

```json
{
  "source": "cosylab|llm_fallback",
  "health_profile": { ... },
  "potential_profile": { ... },
  "swap_suggestions": [
    {
      "original": "string",
      "replacement": "string",
      "health_delta": "number",
      "flavor_delta": "number",
      "semantic_score": "number 0-100",
      "explanation": "string"
    }
  ]
}
```

---

## 9. Summary: Component Responsibilities

| Component | Responsibility | Calls CosyLab? | Calls LLM? |
|-----------|----------------|----------------|------------|
| RecipeDB Service | Fetch recipe, nutrition, micro | Yes | No |
| FlavorDB Service | Flavor profiles, similarity | Yes | No |
| Health Scorer | WHO-based score, penalties, bonuses | No | No |
| Risky Detector | Identify risky ingredients | No | No |
| Swap Engine | Generate swaps from FlavorDB + RecipeDB | Yes | No |
| Sentence Transformer | Re-rank swap candidates | **No** | No |
| LLM Fallback | Only when CosyLab fails | No | Yes |
| Fallback Router | Try CosyLab → on fail use LLM | Yes | Conditionally |
