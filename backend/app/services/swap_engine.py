"""
Ingredient swap engine with flavor preservation.

This module implements the core substitution logic for replacing unhealthy
ingredients with healthier alternatives while preserving flavor profiles
as much as possible.

The engine uses FlavorDB data to match flavor compounds and ranks
substitutes based on a weighted combination of:
- Flavor similarity (60% weight): How well the substitute matches the original flavor
- Health improvement (40% weight): How much the substitute improves the health score

This balance ensures swaps are both palatable and nutritionally beneficial.
"""

import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from app.services.flavordb_service import FlavorDBService
from app.services.health_scorer import HealthScorer
from app.services.semantic_similarity import compute_similarity_scores
from app.utils.constants import HEALTHY_SWAPS
from app.utils.helpers import normalize_ingredient_name, categorize_ingredient

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class SubstituteOption:
    """
    Data class representing a substitute ingredient option.

    Attributes:
        name: Substitute ingredient name
        flavor_match: Flavor similarity percentage (0-100)
        health_improvement: Expected health score improvement
        category: Ingredient category
        rank_score: Combined ranking score
        explanation: Brief explanation of the substitution
        shared_molecules: Flavor molecules shared with the original ingredient
    """
    name: str
    flavor_match: float
    health_improvement: float
    category: str
    rank_score: float
    explanation: Optional[str] = None
    shared_molecules: Optional[List[str]] = None

    def to_dict(self) -> Dict:
        """Convert substitute option to dictionary format."""
        return {
            "name": self.name,
            "flavor_match": round(self.flavor_match, 2),
            "health_improvement": round(self.health_improvement, 2),
            "category": self.category,
            "rank_score": round(self.rank_score, 2),
            "explanation": self.explanation,
            "shared_molecules": self.shared_molecules or [],
        }


class SwapEngine:
    """
    Engine for finding and ranking ingredient substitutions.
    
    Combines flavor matching from FlavorDB with health scoring to find
    optimal ingredient swaps that balance taste and nutrition.
    
    Attributes:
        flavordb_service: Service for flavor profile queries
        health_scorer: Service for health score calculations
        healthy_swaps: Database of healthy alternative ingredients
        flavor_weight: Weight for flavor similarity in ranking (0-1)
        health_weight: Weight for health improvement in ranking (0-1)
    """
    
    def __init__(
        self,
        flavordb_service: FlavorDBService,
        health_scorer: HealthScorer,
        use_semantic_rerank: bool = True,
        semantic_weight: float = 0.1,
    ):
        """
        Initialize swap engine with required services.
        
        Args:
            flavordb_service: FlavorDB service instance
            health_scorer: Health scorer instance
            use_semantic_rerank: Use sentence-transformers for semantic re-ranking
            semantic_weight: Weight for semantic similarity (flavor+health+semantic sum to 1.0)
        """
        self.flavordb_service = flavordb_service
        self.health_scorer = health_scorer
        self.healthy_swaps = HEALTHY_SWAPS
        self.use_semantic_rerank = use_semantic_rerank
        self.semantic_weight = semantic_weight
        
        # Ranking weights (must sum to 1.0)
        if use_semantic_rerank:
            self.flavor_weight = 0.6 - semantic_weight  # e.g. 0.5 when semantic=0.1
            self.health_weight = 0.4
        else:
            self.flavor_weight = 0.6
            self.health_weight = 0.4
        
        logger.info(
            f"SwapEngine initialized with flavor_weight={self.flavor_weight}, "
            f"health_weight={self.health_weight}"
            + (f", semantic_weight={self.semantic_weight} (rerank enabled)" if use_semantic_rerank else "")
        )
    
    def find_substitutes(
        self,
        risky_ingredient: str,
        flavor_profile: Dict,
        current_health_score: float = 50.0,
        recipe_ingredients: Optional[List[str]] = None,
    ) -> List[SubstituteOption]:
        """
        Find healthier alternatives with similar flavor profiles.

        This is the main entry point for finding ingredient substitutes.
        It combines three candidate sources:
        1. Ingredient-specific entries in HEALTHY_SWAPS (exact match first)
        2. FlavorDB flavor-pairings endpoint (molecule-aware discovery)
        3. Category-level fallback from HEALTHY_SWAPS

        Candidates are then ranked by FlavorDB molecule similarity, estimated
        health improvement, and sentence-transformer semantic similarity.

        Args:
            risky_ingredient: Name of ingredient to replace
            flavor_profile: Flavor profile dict from FlavorDB
            current_health_score: Current recipe health score (0-100)
            recipe_ingredients: Full list of recipe ingredients (for context)

        Returns:
            List[SubstituteOption]: Ranked substitutes (best first, up to 5).
        """
        logger.info(
            f"Finding substitutes for: {risky_ingredient} "
            f"(current health score: {current_health_score})"
        )

        normalized = normalize_ingredient_name(risky_ingredient)
        category = categorize_ingredient(normalized)
        logger.debug(f"Ingredient category: {category}")

        # ── Candidate discovery (multi-source) ────────────────────────
        candidates = self.get_healthy_alternative_pool(normalized, category)

        # Augment with FlavorDB pairings — these are molecule-aware
        try:
            fdb_pairings = self.flavordb_service.get_flavor_pairings(risky_ingredient)
            if fdb_pairings:
                seen = {normalize_ingredient_name(c) for c in candidates}
                for p in fdb_pairings:
                    norm_p = normalize_ingredient_name(p)
                    if norm_p not in seen and norm_p != normalized:
                        candidates.append(p)
                        seen.add(norm_p)
                logger.info(
                    f"FlavorDB pairings added {len(fdb_pairings)} extra candidates "
                    f"for '{risky_ingredient}'"
                )
        except Exception as e:
            logger.warning(f"FlavorDB pairings lookup failed for '{risky_ingredient}': {e}")

        # Remove the risky ingredient itself and any already in the recipe
        recipe_normalized = set()
        if recipe_ingredients:
            recipe_normalized = {normalize_ingredient_name(i) for i in recipe_ingredients}
        candidates = [
            c for c in candidates
            if normalize_ingredient_name(c) != normalized
            and normalize_ingredient_name(c) not in recipe_normalized
        ]

        if not candidates:
            logger.warning(f"No candidates found for '{risky_ingredient}'")
            return []

        logger.info(f"Total candidates for '{risky_ingredient}': {len(candidates)}")

        # ── Rank candidates ───────────────────────────────────────────
        ranked = self.rank_substitutes(
            candidates, flavor_profile, current_health_score
        )

        logger.info(
            f"Returning {len(ranked)} substitute(s) for {risky_ingredient}"
        )
        return ranked

    def get_healthy_alternative_pool(
        self, ingredient_name: str, ingredient_category: str
    ) -> List[str]:
        """
        Get pool of healthy alternative ingredients.

        Priority order:
        1. Exact-match key in HEALTHY_SWAPS[category] for this specific ingredient
        2. Partial-match keys (ingredient name contained in key or vice-versa)
        3. Full category fallback (all alternatives in the category)

        This ensures 'butter' and 'lard' get DIFFERENT alternatives instead of
        the same flattened pool.

        Args:
            ingredient_name: Normalized ingredient name
            ingredient_category: Category string

        Returns:
            List[str]: Candidate alternative names (de-duplicated).
        """
        logger.debug(
            f"Getting alternatives for '{ingredient_name}' "
            f"(category: {ingredient_category})"
        )

        category_swaps = self.healthy_swaps.get(ingredient_category, {})
        if not category_swaps:
            logger.warning(f"No HEALTHY_SWAPS for category: {ingredient_category}")
            return []

        # 1. Exact key match
        if ingredient_name in category_swaps:
            alts = list(category_swaps[ingredient_name])
            logger.debug(f"Exact match '{ingredient_name}' → {len(alts)} alternatives")
            return alts

        # 2. Partial match — ingredient name appears in key or key in name
        partial: List[str] = []
        for key, alts in category_swaps.items():
            if ingredient_name in key or key in ingredient_name:
                partial.extend(alts)
        if partial:
            # de-dup
            seen, unique = set(), []
            for a in partial:
                na = normalize_ingredient_name(a)
                if na not in seen:
                    seen.add(na)
                    unique.append(a)
            logger.debug(
                f"Partial match for '{ingredient_name}' → {len(unique)} alternatives"
            )
            return unique

        # 3. Full-category fallback
        all_alts: List[str] = []
        for alts in category_swaps.values():
            all_alts.extend(alts)
        seen, unique = set(), []
        for a in all_alts:
            na = normalize_ingredient_name(a)
            if na not in seen:
                seen.add(na)
                unique.append(a)
        logger.debug(
            f"Category fallback for '{ingredient_name}' → {len(unique)} alternatives"
        )
        return unique
    
    def rank_substitutes(
        self,
        candidates: List[str],
        target_flavor: Dict,
        current_health_score: float
    ) -> List[SubstituteOption]:
        """
        Rank substitute candidates by FlavorDB molecule similarity,
        health improvement, and sentence-transformer semantic closeness.

        Returns up to 5 best options so the frontend can show multiple choices.
        """
        logger.info(
            f"Ranking {len(candidates)} substitute candidates "
            f"against target flavor"
        )

        original_name = target_flavor.get("ingredient", "")
        original_molecules = [
            m.get("common_name") or m.get("name", "")
            for m in target_flavor.get("molecules", [])
        ]
        substitute_options = []

        for candidate in candidates:
            if normalize_ingredient_name(candidate) == \
               normalize_ingredient_name(original_name):
                continue

            try:
                # 1. Flavor similarity via FlavorDB molecule Jaccard
                flavor_match = self.flavordb_service.calculate_flavor_similarity(
                    original_name, candidate
                )

                # 2. Find shared molecules for explainability
                cand_profile = self.flavordb_service.get_flavor_profile_by_ingredient(candidate)
                cand_molecules = [
                    m.get("common_name") or m.get("name", "")
                    for m in cand_profile.get("molecules", [])
                ]
                shared_molecules = sorted(
                    set(m.lower() for m in original_molecules if m)
                    & set(m.lower() for m in cand_molecules if m)
                )

                # 3. Health improvement estimate
                health_improvement = self._estimate_health_improvement(
                    candidate, current_health_score
                )

                # 4. Combined rank (convert to Python float for JSON serialization)
                rank_score = float(
                    (flavor_match * self.flavor_weight)
                    + (health_improvement * self.health_weight)
                )

                # 5. Explanation with molecule evidence
                explanation = self._generate_swap_explanation(
                    original_name, candidate, flavor_match,
                    health_improvement, shared_molecules
                )

                option = SubstituteOption(
                    name=candidate,
                    flavor_match=float(flavor_match),
                    health_improvement=float(health_improvement),
                    category=categorize_ingredient(candidate),
                    rank_score=rank_score,
                    explanation=explanation,
                    shared_molecules=shared_molecules[:8],  # top 8 for display
                )
                substitute_options.append(option)

                logger.debug(
                    f"Ranked {candidate}: flavor={flavor_match:.1f}%, "
                    f"health_improvement={health_improvement:.1f}, "
                    f"rank_score={rank_score:.2f}, "
                    f"shared_molecules={len(shared_molecules)}"
                )

            except Exception as e:
                logger.warning(
                    f"Error processing candidate {candidate}: {str(e)}"
                )
                logger.warning(
                    f"[COSYLAB API FALLBACK] FlavorDB flavor similarity "
                    f"lookup failed for swap candidate '{candidate}'. "
                    f"Skipping this candidate."
                )
                continue

        # ── Semantic re-ranking ───────────────────────────────────────
        if self.use_semantic_rerank and substitute_options:
            candidate_names = [opt.name for opt in substitute_options]
            ranked_semantic = compute_similarity_scores(original_name, candidate_names)
            if ranked_semantic:
                semantic_map = {name: float(score) for name, score in ranked_semantic}
                for opt in substitute_options:
                    semantic_score = semantic_map.get(opt.name, 50.0)
                    opt.rank_score = float(
                        (opt.flavor_match * self.flavor_weight)
                        + (opt.health_improvement * self.health_weight)
                        + (semantic_score * self.semantic_weight)
                    )
                logger.debug(
                    "Applied semantic re-ranking. Top: %s",
                    ranked_semantic[:3] if len(ranked_semantic) >= 3 else ranked_semantic,
                )

        substitute_options.sort(key=lambda x: x.rank_score, reverse=True)

        # Return top 5 so the UI can present choices
        top = substitute_options[:5]
        logger.info(
            f"Ranked {len(substitute_options)} substitutes. "
            f"Returning top {len(top)}. "
            f"Best: {top[0].name if top else 'None'}"
        )
        return top
    
    def _estimate_health_improvement(
        self,
        substitute_ingredient: str,
        current_score: float
    ) -> float:
        """
        Estimate health score improvement from using a substitute.
        
        This is a simplified estimation. In a production system, you might:
        - Look up actual nutrition data for the substitute
        - Recalculate the full health score
        - Use ML to predict improvement
        
        For MVP, we use category-based estimates.
        
        Args:
            substitute_ingredient: Name of substitute ingredient
            current_score: Current recipe health score
            
        Returns:
            float: Estimated score improvement (0-100)
        """
        # Normalize ingredient name
        normalized = normalize_ingredient_name(substitute_ingredient)
        
        # Category-based improvement estimates
        # These are rough estimates based on typical nutritional profiles
        improvement_estimates = {
            # Oils and fats
            "olive oil": 8.0,
            "avocado oil": 8.0,
            "coconut oil": 5.0,
            
            # Sweeteners
            "honey": 3.0,
            "maple syrup": 3.0,
            "stevia": 7.0,
            "monk fruit": 7.0,
            
            # Dairy alternatives
            "almond milk": 6.0,
            "oat milk": 5.0,
            "coconut milk": 4.0,
            "soy milk": 6.0,
            
            # Grains
            "brown rice": 7.0,
            "quinoa": 8.0,
            "whole wheat flour": 6.0,
            "almond flour": 7.0,
            "oat flour": 6.0,
            
            # Default for unknown
            "default": 5.0
        }
        
        # Find matching estimate
        improvement = improvement_estimates.get("default")
        for ingredient_name, estimate in improvement_estimates.items():
            if ingredient_name in normalized:
                improvement = estimate
                break
        
        # Scale improvement based on current score
        # Lower scores have more room for improvement
        if current_score < 30:
            improvement *= 1.5  # 50% boost for very low scores
        elif current_score < 50:
            improvement *= 1.2  # 20% boost for low scores
        elif current_score > 70:
            improvement *= 0.8  # Less room for improvement in good recipes
        
        return min(improvement, 100.0 - current_score)  # Cap at max possible
    
    def _generate_swap_explanation(
        self,
        original: str,
        substitute: str,
        flavor_match: float,
        health_improvement: float,
        shared_molecules: Optional[List[str]] = None,
    ) -> str:
        """
        Generate human-readable explanation for a swap recommendation,
        including FlavorDB molecule evidence when available.
        """
        # Flavor match description
        if flavor_match >= 80:
            flavor_desc = "very similar flavor profile"
        elif flavor_match >= 60:
            flavor_desc = "similar flavor profile"
        elif flavor_match >= 40:
            flavor_desc = "moderately similar flavor"
        else:
            flavor_desc = "different but complementary flavor"

        # Health improvement description
        if health_improvement >= 8:
            health_desc = "significantly healthier"
        elif health_improvement >= 5:
            health_desc = "healthier"
        elif health_improvement >= 3:
            health_desc = "slightly healthier"
        else:
            health_desc = "marginally healthier"

        explanation = (
            f"Replace {original} with {substitute} — "
            f"{flavor_desc} ({flavor_match:.0f}% match), {health_desc}."
        )

        if shared_molecules:
            mol_str = ", ".join(shared_molecules[:5])
            explanation += (
                f" They share {len(shared_molecules)} flavor molecule(s) "
                f"({mol_str}), preserving the taste you expect."
            )

        return explanation
    
    def apply_swaps(
        self,
        original_ingredients: List[str],
        swaps: List[Dict]
    ) -> List[str]:
        """
        Generate new ingredient list with swaps applied.
        
        Creates a modified ingredient list where risky ingredients are
        replaced with their selected substitutes.
        
        Args:
            original_ingredients: Original recipe ingredient list
            swaps: List of swap dictionaries with structure:
                [
                    {
                        "original": str,
                        "substitute": SubstituteOption or dict,
                        "accepted": bool
                    }
                ]
                
        Returns:
            List[str]: Modified ingredient list with swaps applied
            
        Example:
            new_ingredients = engine.apply_swaps(
                ["butter", "sugar", "flour"],
                [
                    {
                        "original": "butter",
                        "substitute": {"name": "olive oil"},
                        "accepted": True
                    }
                ]
            )
            # Returns: ["olive oil", "sugar", "flour"]
        """
        logger.info(
            f"Applying {len(swaps)} swap(s) to {len(original_ingredients)} ingredients"
        )
        
        # Create mapping of original -> substitute
        swap_map = {}
        for swap in swaps:
            if not swap.get("accepted", False):
                continue
            
            original = swap.get("original", "")
            substitute_obj = swap.get("substitute", {})
            
            # Handle both SubstituteOption objects and dicts
            if isinstance(substitute_obj, SubstituteOption):
                substitute_name = substitute_obj.name
            else:
                substitute_name = substitute_obj.get("name", "")
            
            if original and substitute_name:
                swap_map[normalize_ingredient_name(original)] = substitute_name
        
        # Apply swaps
        new_ingredients = []
        swaps_applied = 0
        
        for ingredient in original_ingredients:
            normalized = normalize_ingredient_name(ingredient)
            
            if normalized in swap_map:
                new_ingredients.append(swap_map[normalized])
                swaps_applied += 1
                logger.debug(f"Swapped: {ingredient} -> {swap_map[normalized]}")
            else:
                new_ingredients.append(ingredient)
        
        logger.info(f"Applied {swaps_applied} swap(s) successfully")
        
        return new_ingredients
    
    def estimate_nutrition_with_swaps(
        self,
        original_nutrition: Dict,
        swaps: List[Dict],
        total_ingredients: int = 0
    ) -> Dict:
        """
        Estimate new nutrition data after applying swaps.

        Uses adjustment factors from ``_get_nutrition_adjustments`` but
        only modifies health-penalty nutrients (sugar, sodium,
        saturated_fat, trans_fat, cholesterol) and fiber.  Calories,
        protein, carbs, and fat are left unchanged so macro-percentage
        scoring is not distorted.

        The per-ingredient share is set to ``1 / max(N, 3)`` where N is
        the number of major ingredients (capped at a minimum of 3 so that
        each swap has a meaningful impact).  When the original value of a
        nutrient is 0 but the factor would *add* value (factor > 1.0, e.g.
        fiber boost), a small baseline is injected so the increase is
        visible.
        """
        logger.info("Estimating nutrition with swaps applied")

        new_nutrition = original_nutrition.copy()

        accepted_swaps = [s for s in swaps if s.get("accepted", False)]
        if not accepted_swaps:
            return new_nutrition

        # Use a share that is impactful but not overpowering.
        # Cap denominator at max(total, swaps+2) but floor at 3 so a
        # single swap still changes about 33% of the nutrient.
        num_ingredients = max(total_ingredients, len(accepted_swaps) + 2, 3)
        ingredient_share = 1.0 / num_ingredients

        ADJUSTABLE_NUTRIENTS = {
            "sugar", "sodium", "saturated_fat", "trans_fat",
            "cholesterol", "fiber",
        }

        # Small baselines for when the original value is 0 but we want to
        # model an *increase* (e.g. fiber from lentils, sugar from honey).
        BASELINE = {
            "sugar": 5.0, "sodium": 50.0, "saturated_fat": 2.0,
            "trans_fat": 0.0, "cholesterol": 20.0, "fiber": 2.0,
        }

        for swap in accepted_swaps:
            substitute_obj = swap.get("substitute", {})
            if isinstance(substitute_obj, SubstituteOption):
                substitute_name = substitute_obj.name
            else:
                substitute_name = substitute_obj.get("name", "")

            adjustments = self._get_nutrition_adjustments(substitute_name)

            for nutrient, factor in adjustments.items():
                if nutrient not in ADJUSTABLE_NUTRIENTS:
                    continue
                if nutrient not in new_nutrition:
                    continue

                original_value = new_nutrition[nutrient]

                # Handle zero originals
                if original_value == 0:
                    if factor > 1.0:
                        # Inject a baseline so the increase is visible
                        # (e.g. adding fiber from lentils)
                        baseline = BASELINE.get(nutrient, 0)
                        new_nutrition[nutrient] = baseline * ingredient_share * factor
                    # else: nothing to reduce, skip
                    continue

                # Apply proportional adjustment
                portion = original_value * ingredient_share
                adjusted = portion * factor
                new_nutrition[nutrient] = original_value - portion + adjusted

        logger.info(
            f"Nutrition after swaps: calories={new_nutrition.get('calories', 0):.1f}, "
            f"sugar={new_nutrition.get('sugar', 0):.1f}, "
            f"sat_fat={new_nutrition.get('saturated_fat', 0):.1f}, "
            f"sodium={new_nutrition.get('sodium', 0):.1f}, "
            f"fiber={new_nutrition.get('fiber', 0):.1f}"
        )
        return new_nutrition
    
    def _get_nutrition_adjustments(self, substitute_name: str) -> Dict[str, float]:
        """
        Get nutrition adjustment factors for a substitute ingredient.
        
        Returns multiplication factors for each nutrient (1.0 = no change).
        
        Args:
            substitute_name: Name of substitute ingredient
            
        Returns:
            Dict[str, float]: Nutrient adjustment factors
        """
        normalized = normalize_ingredient_name(substitute_name)
        
        # Predefined adjustment factors for common swap substitutes.
        # Each factor is a multiplier on the ingredient's share of the
        # nutrient (1.0 = no change, <1.0 = reduction, >1.0 = increase).
        adjustment_map = {
            # ----- Oils / fats -----
            "olive oil": {
                "saturated_fat": 0.55, "trans_fat": 0.0, "cholesterol": 0.5,
            },
            "avocado oil": {
                "saturated_fat": 0.5, "trans_fat": 0.0, "cholesterol": 0.4,
            },
            "coconut oil": {
                "saturated_fat": 1.2, "trans_fat": 0.0, "cholesterol": 0.3,
            },
            "ghee": {
                "saturated_fat": 0.9, "trans_fat": 0.0,
            },
            "applesauce": {
                "saturated_fat": 0.1, "sugar": 1.3, "calories": 0.5, "fat": 0.1,
            },
            # ----- Sweeteners -----
            "stevia": {
                "sugar": 0.05, "calories": 0.05,
            },
            "monk fruit": {
                "sugar": 0.05, "calories": 0.05,
            },
            "honey": {
                "sugar": 0.85, "calories": 0.9,
            },
            "maple syrup": {
                "sugar": 0.8, "calories": 0.85,
            },
            "coconut sugar": {
                "sugar": 0.75, "calories": 0.9,
            },
            "date sugar": {
                "sugar": 0.7, "calories": 0.85, "fiber": 1.5,
            },
            "agave": {
                "sugar": 0.8, "calories": 0.85,
            },
            # ----- Dairy alternatives -----
            "almond milk": {
                "saturated_fat": 0.2, "cholesterol": 0.0, "calories": 0.4,
            },
            "oat milk": {
                "saturated_fat": 0.2, "cholesterol": 0.0, "fiber": 1.5, "calories": 0.6,
            },
            "soy milk": {
                "saturated_fat": 0.25, "cholesterol": 0.0, "calories": 0.55,
            },
            "coconut cream": {
                "saturated_fat": 1.1, "cholesterol": 0.0,
            },
            "cashew cream": {
                "saturated_fat": 0.4, "cholesterol": 0.0,
            },
            "greek yogurt": {
                "saturated_fat": 0.5, "cholesterol": 0.6, "sugar": 0.5,
            },
            "nutritional yeast": {
                "saturated_fat": 0.1, "cholesterol": 0.0, "sodium": 0.3,
            },
            # ----- Grains -----
            "brown rice": {
                "fiber": 2.0,
            },
            "quinoa": {
                "fiber": 2.0,
            },
            "cauliflower rice": {
                "calories": 0.3, "carbs": 0.2, "fiber": 1.5,
            },
            "whole wheat flour": {
                "fiber": 2.0,
            },
            "almond flour": {
                "carbs": 0.4, "fiber": 2.0, "fat": 1.3,
            },
            "oat flour": {
                "fiber": 2.0,
            },
            "whole wheat pasta": {
                "fiber": 2.0,
            },
            "zucchini noodles": {
                "calories": 0.2, "carbs": 0.15, "fiber": 1.5,
            },
            # ----- Protein -----
            "ground turkey": {
                "saturated_fat": 0.5, "cholesterol": 0.7, "calories": 0.75,
            },
            "ground chicken": {
                "saturated_fat": 0.4, "cholesterol": 0.6, "calories": 0.7,
            },
            "lentils": {
                "saturated_fat": 0.1, "cholesterol": 0.0, "fiber": 3.0, "calories": 0.6,
            },
            "turkey bacon": {
                "saturated_fat": 0.4, "sodium": 0.8, "calories": 0.6,
            },
            "tempeh": {
                "saturated_fat": 0.2, "cholesterol": 0.0, "fiber": 2.5,
            },
            "chicken sausage": {
                "saturated_fat": 0.5, "calories": 0.7,
            },
            "turkey sausage": {
                "saturated_fat": 0.45, "calories": 0.7,
            },
            # ----- Condiments -----
            "hummus": {
                "saturated_fat": 0.3, "fiber": 2.0, "cholesterol": 0.0,
            },
            "avocado": {
                "saturated_fat": 0.3, "fiber": 2.5, "cholesterol": 0.0,
            },
            "coconut aminos": {
                "sodium": 0.4,
            },
            "tamari": {
                "sodium": 0.7,
            },
            "salsa": {
                "sugar": 0.3, "sodium": 0.6, "calories": 0.3,
            },
            # ----- Spices/salt -----
            "herbs": {
                "sodium": 0.0,
            },
            "lemon juice": {
                "sodium": 0.0,
            },
            "garlic powder": {
                "sodium": 0.05,
            },
            "herb blend": {
                "sodium": 0.05,
            },
        }
        
        # Find matching adjustments
        for ingredient_pattern, adjustments in adjustment_map.items():
            if ingredient_pattern in normalized:
                return adjustments
        
        # Default: modest improvement across negative factors
        return {
            "saturated_fat": 0.85,
            "sodium": 0.85,
            "sugar": 0.85,
            "cholesterol": 0.85,
        }
    
    def reconstruct_swaps(
        self,
        original_ingredients: List[str],
        accepted_substitute_names: List[str]
    ) -> List[Dict]:
        """
        Reconstruct swap dictionaries from ingredient lists.
        
        Used when recalculating scores after user accepts specific swaps.
        Matches accepted substitutes back to their original ingredients.
        
        Args:
            original_ingredients: Original recipe ingredients
            accepted_substitute_names: Names of accepted substitute ingredients
            
        Returns:
            List[Dict]: Reconstructed swap dictionaries
        """
        logger.info(
            f"Reconstructing swaps for {len(accepted_substitute_names)} "
            f"accepted substitute(s)"
        )
        
        swaps = []
        
        # This is a simplified reconstruction
        # In a real system, you'd store swap metadata in a session/database
        for substitute_name in accepted_substitute_names:
            # Try to infer original ingredient by category matching
            substitute_category = categorize_ingredient(substitute_name)
            
            # Find original ingredient of same category
            for original in original_ingredients:
                if categorize_ingredient(original) == substitute_category:
                    swaps.append({
                        "original": original,
                        "substitute": {"name": substitute_name},
                        "accepted": True
                    })
                    break
        
        logger.info(f"Reconstructed {len(swaps)} swap(s)")
        
        return swaps
    
    def get_swap_statistics(self) -> Dict:
        """
        Get statistics about available swaps in the system.
        
        Returns:
            Dict: Swap system statistics
        """
        total_categories = len(self.healthy_swaps)
        total_original = sum(len(originals) for originals in self.healthy_swaps.values())
        total_alternatives = sum(
            len(alternatives)
            for category in self.healthy_swaps.values()
            for alternatives in category.values()
        )
        
        return {
            "total_categories": total_categories,
            "total_original_ingredients": total_original,
            "total_alternative_ingredients": total_alternatives,
            "categories": list(self.healthy_swaps.keys()),
            "flavor_weight": self.flavor_weight,
            "health_weight": self.health_weight
        }