# Hyper-Personalized Craving Replacement System

## Overview

The Craving Replacement System adds a dedicated **Cravings** tab to NutriTwin.
Users log what they are craving (with flavor, mood, time-of-day, and optional context), and the system returns:

1. **Psychological insight** — a short, evidence-based explanation of *why* the craving happens (e.g. cortisol-driven sugar seeking under stress).
2. **Quick combos** — 2–3 ingredient pairings generated via FlavorDB molecule matching, each preparable in under 5 minutes.
3. **Full recipe suggestions** — up to 5 RecipeDB recipes filtered by flavor category, time of day, diet, and allergens, ranked by health score.
4. **Science explanation** — why the suggested replacements satisfy the same neural pathways without the downsides.

Over time, the system detects **craving patterns** (e.g. "you crave sweet foods late at night when stressed") and shows **encouragement stats** ("you replaced 6 sugar cravings this week") on both the Cravings page and the Dashboard.

---

## Psychology & Design Rationale

| Principle | How the system applies it |
|-----------|--------------------------|
| Cravings are emotional, not nutritional | Mood and context inputs let the system tailor responses to the emotional trigger, not just the food category. |
| Deprivation causes rebound | The system never says "don't eat X". It always suggests a *substitution* that matches the same flavor profile. |
| Decision fatigue drives relapse | One-tap "I'll try this" buttons and pre-scored options reduce the effort of making a healthy choice. |
| Awareness reduces impulsivity | Pattern detection and stats make habitual craving triggers visible. |
| Positive reinforcement sustains change | Encouragement messages reward progress rather than punishing slips. |

---

## Architecture

### Backend

All new backend code lives under the existing FastAPI application — no new services, databases, or infrastructure.

```
backend/app/
  models/craving.py          # Pydantic request/response schemas
  services/craving_service.py # Core engine (RecipeDB + FlavorDB + patterns)
  services/llm_explainer.py   # +2 methods for LLM craving insight (Gemini)
  utils/constants.py          # +craving mapping tables (FLAVOR_TO_SEARCH_PARAMS, etc.)
  main.py                     # +2 endpoints (POST /cravings/replace, POST /cravings/patterns)
```

### Frontend

```
frontend/src/
  pages/Cravings.tsx           # New /cravings page
  store/cravingStore.ts        # localStorage persistence for craving history
  types/api.ts                 # +craving TypeScript types
  services/api.ts              # +2 API methods
  pages/Dashboard.tsx          # +Craving Insights card
  components/Header.tsx        # +Cravings nav item
  App.tsx                      # +/cravings route
```

### Data Flow

```
User fills craving form
  |
  +--> frontend logCraving() -> localStorage
  |
  +--> POST /cravings/replace
         |
         +-- CravingService.process_craving()
               |
               +-- RecipeDBService (search_by_category, search_by_day_category, ...)
               +-- FlavorDBService (get_flavor_pairings for quick combos)
               +-- HealthScorer (rank recipes)
               +-- LLMExplainer.generate_craving_insight() OR template fallback
               |
               +--> CravingReplacement response
```

Pattern analysis uses a separate call:

```
Frontend sends history array from localStorage
  |
  +--> POST /cravings/patterns
         |
         +-- CravingService.analyze_patterns()
         +-- (optional) LLMExplainer.generate_craving_pattern_insights()
         |
         +--> CravingPatternAnalysis response
```

---

## API Endpoints

### `POST /cravings/replace`

Process a craving into replacement suggestions.

**Request body** (`CravingRequest`):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `craving_text` | string | yes | Free-text craving, e.g. "chocolate at night" |
| `flavor_type` | enum | yes | `sweet`, `salty`, `crunchy`, `spicy`, `umami`, `creamy` |
| `mood` | enum | no | `stressed`, `bored`, `tired`, `happy`, `anxious`, `sad` |
| `time_of_day` | enum | yes | `morning`, `afternoon`, `evening`, `late-night` |
| `context` | string | no | e.g. "after studying" |
| `user_allergens` | string[] | no | Allergen categories to exclude |
| `user_avoid_ingredients` | string[] | no | Specific ingredients to exclude |
| `diet_type` | string | no | e.g. "vegetarian" |

**Response** (`CravingReplacement`):

| Field | Type | Description |
|-------|------|-------------|
| `original_craving` | string | Echo of the input craving text |
| `flavor_type` | string | Echo of the selected flavor |
| `psychological_insight` | string | 1–2 sentence explanation of the craving trigger |
| `quick_combos` | QuickCombo[] | Up to 3 fast ingredient pairings |
| `full_recipes` | CravingRecipe[] | Up to 5 RecipeDB recipes sorted by health score |
| `science_explanation` | string | Why the replacements satisfy the craving |
| `encouragement` | string | Brief positive reinforcement message |

### `POST /cravings/patterns`

Analyse craving history and detect patterns.

**Request body**: array of `CravingHistoryEntry` objects (sent from frontend localStorage).

**Response** (`CravingPatternAnalysis`):

| Field | Type | Description |
|-------|------|-------------|
| `patterns` | CravingPattern[] | Detected behavioural patterns |
| `weekly_summary` | object | Aggregate stats (total, replaced, rate, top flavor/mood/time) |
| `encouragement_messages` | string[] | Positive reinforcement messages |

---

## RecipeDB Endpoints Used

No new RecipeDB API endpoints are needed. The craving service composes existing wrappers in `recipedb_service.py`:

| RecipeDB Endpoint | Purpose in Cravings |
|-------------------|---------------------|
| `recipe_by_category` | Map flavor type to food categories (sweet → desserts/snacks) |
| `recipe_by_recipe_day_category` | Time-of-day awareness (late-night → snack) |
| `recipe_by_cuisine` | Spicy/umami → Indian/Mexican/Thai |
| `recipe_by_diet` | Apply user's dietary restrictions |
| `recipe_by_calories` | Cap calories for healthier alternatives |
| `recipe_nutrition_info` | Score candidate recipes with HealthScorer |

---

## FlavorDB Endpoints Used

| FlavorDB Endpoint | Purpose in Cravings |
|-------------------|---------------------|
| `flavor_pairings` | Find molecule-compatible pairings for quick combo ingredients |

---

## LLM Integration

The system uses **Gemini with template fallback**:

- If `GEMINI_API_KEY` is set, `LLMExplainer.generate_craving_insight()` sends a prompt to Gemini asking for a 2-sentence psychological explanation.
- If the LLM call fails or no API key is configured, the system falls back to `CRAVING_INSIGHT_TEMPLATES` in `constants.py` — a dictionary mapping `(flavor_type, mood)` pairs to pre-written insights.
- Pattern analysis optionally calls `generate_craving_pattern_insights()` for deeper behavioral observations from the LLM.

---

## Frontend Persistence

Craving history is stored in **localStorage** under key `nutritwin-craving-history`, following the same pattern as `recipeStore.ts`. A pub/sub system (`CustomEvent`) keeps the Cravings page and Dashboard in sync.

Key store methods:
- `logCraving()` — append a new entry
- `markReplacementChosen()` — update an entry when user picks a replacement
- `getCravingStats()` — compute aggregate stats
- `getCravingHistory()` — retrieve all entries
- `subscribeToCravingStore()` — listen for changes

---

## How Craving Constants Work

All craving mappings live in `backend/app/utils/constants.py` and are data-driven, not hardcoded logic:

- **`FLAVOR_TO_SEARCH_PARAMS`** — maps each flavor type to RecipeDB categories, cuisine filters, and calorie caps.
- **`TIME_TO_DAY_CATEGORY`** — maps time-of-day to RecipeDB `day_category` values.
- **`MOOD_FLAVOR_ASSOCIATIONS`** — maps moods to commonly associated flavor cravings (used in pattern analysis).
- **`CRAVING_INSIGHT_TEMPLATES`** — fallback psychological insights indexed by `(flavor, mood)`.
- **`CRAVING_SCIENCE_TEMPLATES`** — per-flavor explanations of replacement science.

To add new flavor types, moods, or insight text, edit these dictionaries — no code changes required.

---

## Files Changed / Created

| File | Status | Description |
|------|--------|-------------|
| `backend/app/models/craving.py` | **New** | Pydantic models for craving system |
| `backend/app/services/craving_service.py` | **New** | Core craving processing + pattern analysis |
| `backend/app/utils/constants.py` | Modified | Added craving mapping tables |
| `backend/app/services/llm_explainer.py` | Modified | Added `generate_craving_insight()` and `generate_craving_pattern_insights()` |
| `backend/app/main.py` | Modified | Added 2 endpoints, CravingService initialization |
| `frontend/src/types/api.ts` | Modified | Added craving TypeScript types and option arrays |
| `frontend/src/services/api.ts` | Modified | Added `getCravingReplacement()` and `analyzeCravingPatterns()` |
| `frontend/src/store/cravingStore.ts` | **New** | localStorage-based craving history store |
| `frontend/src/pages/Cravings.tsx` | **New** | Complete Cravings page (form + results + patterns + history) |
| `frontend/src/pages/Dashboard.tsx` | Modified | Added Craving Insights card and Log a Craving quick action |
| `frontend/src/components/Header.tsx` | Modified | Added Cravings nav item |
| `frontend/src/App.tsx` | Modified | Added `/cravings` route |
