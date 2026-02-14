"""
Craving Replacement Service.

Core engine for the Hyper-Personalized Craving Replacement System.
Processes a craving request into tailored replacement suggestions by:
1. Querying RecipeDB for matching recipes (category, time-of-day, diet)
2. Using FlavorDB for flavor-matching quick combos
3. Generating psychological insights (LLM with template fallback)
4. Analyzing craving history for patterns

Uses the existing RecipeDB and FlavorDB service wrappers — no new
external API endpoints are required.
"""

import logging
from typing import List, Dict, Optional, Set
from collections import Counter

from app.models.craving import (
    CravingRequest,
    CravingReplacement,
    QuickCombo,
    CravingRecipe,
    CravingHistoryEntry,
    CravingPattern,
    CravingPatternAnalysis,
)
from app.services.recipedb_service import RecipeDBService
from app.services.flavordb_service import FlavorDBService
from app.services.health_scorer import HealthScorer
from app.utils.constants import (
    FLAVOR_TO_SEARCH_PARAMS,
    TIME_TO_DAY_CATEGORY,
    MOOD_FLAVOR_ASSOCIATIONS,
    CRAVING_INSIGHT_TEMPLATES,
    CRAVING_SCIENCE_TEMPLATES,
    ALLERGEN_KEYWORDS,
)

logger = logging.getLogger(__name__)


class CravingService:
    """
    Service for processing cravings and generating personalized replacements.

    Composes RecipeDB searches, FlavorDB flavor matching, and health scoring
    to deliver contextual craving substitutions.
    """

    def __init__(
        self,
        recipedb_service: RecipeDBService,
        flavordb_service: FlavorDBService,
        health_scorer: HealthScorer,
        llm_explainer=None,
    ):
        self.recipedb = recipedb_service
        self.flavordb = flavordb_service
        self.health_scorer = health_scorer
        self.llm_explainer = llm_explainer
        logger.info("CravingService initialized")

    # ------------------------------------------------------------------
    # PUBLIC: process a single craving
    # ------------------------------------------------------------------

    def process_craving(self, request: CravingRequest) -> CravingReplacement:
        """
        Main entry point: turn a craving into replacement suggestions.

        Steps:
        1. Build search parameters from flavor type + time of day
        2. Query RecipeDB for matching recipes
        3. Filter by allergens / avoid ingredients / diet
        4. Score recipes for health
        5. Generate quick combos via FlavorDB pairings
        6. Generate psychological insight and science explanation
        """
        logger.info(
            f"Processing craving: '{request.craving_text}' "
            f"flavor={request.flavor_type} mood={request.mood} time={request.time_of_day}"
        )

        # 1 — Fetch candidate recipes from RecipeDB
        recipes = self._fetch_candidate_recipes(request)

        # 2 — Filter allergens & avoid ingredients
        recipes = self._filter_recipes(recipes, request)

        # 3 — Score and sort
        scored = self._score_and_rank(recipes)
        top_recipes = scored[:5]

        # 4 — Quick combos (FlavorDB + knowledge)
        quick_combos = self._build_quick_combos(request)

        # 5 — Insight + science
        insight = self._get_psychological_insight(request)
        science = CRAVING_SCIENCE_TEMPLATES.get(
            request.flavor_type.value,
            "Choosing nutrient-dense alternatives helps satisfy cravings while supporting your overall health goals.",
        )

        # 6 — Encouragement
        encouragement = self._build_encouragement(request)

        return CravingReplacement(
            original_craving=request.craving_text,
            flavor_type=request.flavor_type.value,
            psychological_insight=insight,
            quick_combos=quick_combos,
            full_recipes=top_recipes,
            science_explanation=science,
            encouragement=encouragement,
        )

    # ------------------------------------------------------------------
    # PUBLIC: analyse craving history for patterns
    # ------------------------------------------------------------------

    def analyze_patterns(
        self, history: List[CravingHistoryEntry]
    ) -> CravingPatternAnalysis:
        """Detect patterns in the user's craving history sent from the frontend."""
        if not history:
            return CravingPatternAnalysis(
                patterns=[],
                weekly_summary={"total": 0, "replaced": 0},
                encouragement_messages=["Start logging cravings to discover your patterns."],
            )

        flavor_counts = Counter(e.flavor_type for e in history)
        mood_counts = Counter(e.mood for e in history if e.mood)
        time_counts = Counter(e.time_of_day for e in history)
        replaced = sum(1 for e in history if e.replacement_chosen)
        total = len(history)

        patterns: List[CravingPattern] = []

        # Most common flavor + time combo
        combo_counts: Counter = Counter()
        for entry in history:
            combo_counts[(entry.flavor_type, entry.time_of_day)] += 1

        for (flav, tod), count in combo_counts.most_common(3):
            if count < 2:
                continue
            top_mood = None
            moods_for_combo = [
                e.mood for e in history
                if e.flavor_type == flav and e.time_of_day == tod and e.mood
            ]
            if moods_for_combo:
                top_mood = Counter(moods_for_combo).most_common(1)[0][0]

            trigger = top_mood if top_mood else tod
            patterns.append(
                CravingPattern(
                    pattern_description=(
                        f"You tend to crave {flav} foods during {tod.replace('-', ' ')}"
                        + (f" when feeling {top_mood}" if top_mood else "")
                        + f" ({count} times)."
                    ),
                    frequency=count,
                    trigger=trigger,
                    top_time=tod,
                    top_mood=top_mood,
                )
            )

        # Mood-driven pattern
        if mood_counts:
            top_mood_val, top_mood_count = mood_counts.most_common(1)[0]
            if top_mood_count >= 2:
                assoc_flavors = MOOD_FLAVOR_ASSOCIATIONS.get(top_mood_val, [])
                actual_top = flavor_counts.most_common(1)[0][0] if flavor_counts else "various"
                patterns.append(
                    CravingPattern(
                        pattern_description=(
                            f"When {top_mood_val}, you most often crave {actual_top} foods ({top_mood_count} times)."
                        ),
                        frequency=top_mood_count,
                        trigger=top_mood_val,
                        top_time=time_counts.most_common(1)[0][0] if time_counts else "various",
                        top_mood=top_mood_val,
                    )
                )

        # Weekly summary
        weekly_summary = {
            "total": total,
            "replaced": replaced,
            "replacement_rate": round(replaced / total * 100) if total else 0,
            "top_flavor": flavor_counts.most_common(1)[0][0] if flavor_counts else None,
            "top_time": time_counts.most_common(1)[0][0] if time_counts else None,
            "top_mood": mood_counts.most_common(1)[0][0] if mood_counts else None,
        }

        # Encouragement messages
        encouragement: List[str] = []
        if replaced > 0:
            encouragement.append(
                f"You chose a healthier replacement {replaced} out of {total} times. Keep it up!"
            )
        rate = weekly_summary["replacement_rate"]
        if rate >= 70:
            encouragement.append("Excellent consistency — your craving management is on track.")
        elif rate >= 40:
            encouragement.append("Good progress. Each healthy swap builds a stronger habit.")
        if not encouragement:
            encouragement.append("Logging cravings is the first step — awareness drives change.")

        return CravingPatternAnalysis(
            patterns=patterns,
            weekly_summary=weekly_summary,
            encouragement_messages=encouragement,
        )

    # ------------------------------------------------------------------
    # PRIVATE: recipe fetching
    # ------------------------------------------------------------------

    def _fetch_candidate_recipes(self, req: CravingRequest) -> List[Dict]:
        """Query RecipeDB using flavor + time + diet parameters."""
        seen_ids: Set[str] = set()
        results: List[Dict] = []

        search_params = FLAVOR_TO_SEARCH_PARAMS.get(req.flavor_type.value, {})

        # By category
        for cat in search_params.get("categories", []):
            try:
                for r in self.recipedb.search_by_category(cat):
                    rid = r.get("id")
                    if rid and rid not in seen_ids:
                        seen_ids.add(rid)
                        results.append(r)
            except Exception as e:
                logger.warning(f"Category search '{cat}' failed: {e}")

        # By day category (time awareness)
        for day_cat in TIME_TO_DAY_CATEGORY.get(req.time_of_day.value, []):
            try:
                for r in self.recipedb.search_by_day_category(day_cat):
                    rid = r.get("id")
                    if rid and rid not in seen_ids:
                        seen_ids.add(rid)
                        results.append(r)
            except Exception as e:
                logger.warning(f"Day-category search '{day_cat}' failed: {e}")

        # By cuisine (for spicy/umami flavors)
        for cuisine in search_params.get("cuisines", []):
            try:
                for r in self.recipedb.search_by_cuisine(cuisine):
                    rid = r.get("id")
                    if rid and rid not in seen_ids:
                        seen_ids.add(rid)
                        results.append(r)
            except Exception as e:
                logger.warning(f"Cuisine search '{cuisine}' failed: {e}")

        # By diet type
        if req.diet_type:
            try:
                for r in self.recipedb.search_by_diet(req.diet_type):
                    rid = r.get("id")
                    if rid and rid not in seen_ids:
                        seen_ids.add(rid)
                        results.append(r)
            except Exception as e:
                logger.warning(f"Diet search '{req.diet_type}' failed: {e}")

        # By calorie cap
        max_cal = search_params.get("max_calories")
        if max_cal:
            try:
                for r in self.recipedb.search_by_calories(0, max_cal):
                    rid = r.get("id")
                    if rid and rid not in seen_ids:
                        seen_ids.add(rid)
                        results.append(r)
            except Exception as e:
                logger.warning(f"Calorie search failed: {e}")

        logger.info(f"Fetched {len(results)} candidate recipes from RecipeDB")
        return results

    # ------------------------------------------------------------------
    # PRIVATE: filtering
    # ------------------------------------------------------------------

    def _filter_recipes(self, recipes: List[Dict], req: CravingRequest) -> List[Dict]:
        """Remove recipes containing user allergens or avoided ingredients."""
        allergens = set(req.user_allergens or [])
        avoid = {a.lower() for a in (req.user_avoid_ingredients or [])}
        if not allergens and not avoid:
            return recipes

        filtered: List[Dict] = []
        for r in recipes:
            ings = r.get("ingredients", [])
            ing_text = " ".join(i.lower() if isinstance(i, str) else "" for i in ings)
            skip = False
            for allergen in allergens:
                keywords = ALLERGEN_KEYWORDS.get(allergen, [])
                if any(kw in ing_text for kw in keywords):
                    skip = True
                    break
            if not skip:
                for term in avoid:
                    if term in ing_text:
                        skip = True
                        break
            if not skip:
                filtered.append(r)

        logger.info(f"Filtered {len(recipes)} -> {len(filtered)} recipes after allergen/avoid check")
        return filtered

    # ------------------------------------------------------------------
    # PRIVATE: scoring
    # ------------------------------------------------------------------

    def _score_and_rank(self, recipes: List[Dict]) -> List[CravingRecipe]:
        """Score each recipe with the health scorer and return sorted list."""
        scored: List[CravingRecipe] = []
        for r in recipes:
            try:
                rid = r.get("id")
                nutrition = None
                if rid:
                    try:
                        nutrition = self.recipedb.fetch_nutrition_info(str(rid))
                    except Exception:
                        nutrition = None

                hs = None
                if nutrition:
                    score_obj = self.health_scorer.calculate_health_score(nutrition)
                    hs = score_obj.score if score_obj else None

                ings = r.get("ingredients", [])
                scored.append(
                    CravingRecipe(
                        id=str(rid) if rid else None,
                        name=r.get("name", "Unknown Recipe"),
                        cuisine=r.get("cuisine"),
                        diet_type=r.get("diet_type"),
                        ingredients=ings if isinstance(ings, list) else [],
                        prep_time=r.get("prep_time"),
                        health_score=hs,
                    )
                )
            except Exception as e:
                logger.warning(f"Error scoring recipe {r.get('name')}: {e}")

        # Sort: prefer recipes with a health score, highest first
        scored.sort(key=lambda x: x.health_score if x.health_score is not None else 0, reverse=True)
        return scored

    # ------------------------------------------------------------------
    # PRIVATE: quick combos from FlavorDB
    # ------------------------------------------------------------------

    def _build_quick_combos(self, req: CravingRequest) -> List[QuickCombo]:
        """
        Build quick combos using FlavorDB pairings for the craved flavor,
        filtered by allergens.
        """
        combos: List[QuickCombo] = []
        flavor = req.flavor_type.value
        avoid = {a.lower() for a in (req.user_avoid_ingredients or [])}
        allergens = set(req.user_allergens or [])

        # Seed ingredients per flavor type (these are common healthy bases)
        seed_map: Dict[str, List[str]] = {
            "sweet": ["dark chocolate", "banana", "yogurt", "honey", "dates"],
            "salty": ["roasted chickpeas", "cucumber", "hummus", "popcorn", "nuts"],
            "crunchy": ["carrots", "almonds", "apple", "celery", "roasted makhana"],
            "spicy": ["chili flakes", "ginger", "lentil soup", "salsa", "sriracha"],
            "umami": ["miso", "mushrooms", "soy sauce", "tomato", "seaweed"],
            "creamy": ["avocado", "greek yogurt", "banana", "coconut cream", "nut butter"],
        }

        seeds = seed_map.get(flavor, ["mixed nuts", "fruit"])

        for seed in seeds:
            if seed.lower() in avoid:
                continue
            if self._ingredient_has_allergen(seed, allergens):
                continue

            # Try FlavorDB pairing
            try:
                pairings = self.flavordb.get_flavor_pairings(seed)
                if pairings and isinstance(pairings, list):
                    partner = None
                    for p in pairings[:10]:
                        name = p if isinstance(p, str) else p.get("name", "")
                        if not name:
                            continue
                        if name.lower() in avoid:
                            continue
                        if self._ingredient_has_allergen(name, allergens):
                            continue
                        partner = name
                        break
                    if partner:
                        combos.append(
                            QuickCombo(
                                name=f"{seed.title()} + {partner.title()}",
                                ingredients=[seed, partner],
                                prep_time_minutes=3,
                                why_it_works=f"Flavor-paired {flavor} combo with complementary molecules",
                                flavor_match=flavor,
                            )
                        )
            except Exception as e:
                logger.debug(f"FlavorDB pairing for '{seed}' failed: {e}")

        # Ensure we always return at least one combo using seed ingredients directly
        if len(combos) < 2 and len(seeds) >= 2:
            safe = [s for s in seeds
                    if s.lower() not in avoid and not self._ingredient_has_allergen(s, allergens)]
            if len(safe) >= 2:
                combos.append(
                    QuickCombo(
                        name=f"{safe[0].title()} & {safe[1].title()}",
                        ingredients=[safe[0], safe[1]],
                        prep_time_minutes=2,
                        why_it_works=f"Quick {flavor} combination with complementary nutrients",
                        flavor_match=flavor,
                    )
                )

        return combos[:3]

    # ------------------------------------------------------------------
    # PRIVATE: insight generation
    # ------------------------------------------------------------------

    def _get_psychological_insight(self, req: CravingRequest) -> str:
        """Generate a psychological insight for the craving. LLM first, template fallback."""
        # Try LLM if available
        if self.llm_explainer and hasattr(self.llm_explainer, "generate_craving_insight"):
            try:
                insight = self.llm_explainer.generate_craving_insight(req)
                if insight:
                    return insight
            except Exception as e:
                logger.warning(f"LLM craving insight failed, using template: {e}")

        # Template fallback
        flavor_templates = CRAVING_INSIGHT_TEMPLATES.get(req.flavor_type.value, {})
        mood_key = req.mood.value if req.mood else "_default"
        return flavor_templates.get(mood_key, flavor_templates.get("_default",
            "Understanding what drives your cravings is the first step to managing them sustainably."
        ))

    def _build_encouragement(self, req: CravingRequest) -> str:
        """Build a brief encouragement message."""
        flavor = req.flavor_type.value
        return (
            f"Great job seeking a healthier {flavor} option instead of giving in. "
            "Each smart swap strengthens the habit."
        )

    # ------------------------------------------------------------------
    # PRIVATE: helpers
    # ------------------------------------------------------------------

    def _ingredient_has_allergen(self, ingredient: str, allergens: Set[str]) -> bool:
        """Check if an ingredient matches any allergen keywords."""
        ing_lower = ingredient.lower()
        for allergen in allergens:
            keywords = ALLERGEN_KEYWORDS.get(allergen, [])
            if any(kw in ing_lower for kw in keywords):
                return True
        return False
