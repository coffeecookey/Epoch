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
    """
    name: str
    flavor_match: float
    health_improvement: float
    category: str
    rank_score: float
    explanation: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """
        Convert substitute option to dictionary format.
        
        Returns:
            Dict: Substitute data as dictionary
        """
        return {
            "name": self.name,
            "flavor_match": round(self.flavor_match, 2),
            "health_improvement": round(self.health_improvement, 2),
            "category": self.category,
            "rank_score": round(self.rank_score, 2),
            "explanation": self.explanation
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
        current_health_score: float = 50.0
    ) -> List[SubstituteOption]:
        """
        Find healthier alternatives with similar flavor profiles.
        
        This is the main entry point for finding ingredient substitutes.
        It identifies candidate alternatives, calculates flavor similarity,
        estimates health improvements, and ranks options.
        
        Algorithm:
        1. Categorize the risky ingredient
        2. Get pool of healthy alternatives for that category
        3. Fetch flavor profiles for each candidate
        4. Calculate flavor similarity scores
        5. Estimate health improvements
        6. Rank candidates by combined score
        7. Return top substitutes
        
        Args:
            risky_ingredient: Name of ingredient to replace
            flavor_profile: Flavor profile dict from FlavorDB
                {
                    "ingredient": str,
                    "molecules": [...],
                    "primary_flavors": [...],
                    "category": str
                }
            current_health_score: Current recipe health score (0-100)
            
        Returns:
            List[SubstituteOption]: Ranked list of substitute options
                                    (best matches first).
                                    Returns empty list if no suitable substitutes found.
                                    
        Example:
            engine = SwapEngine(flavordb_service, health_scorer)
            substitutes = engine.find_substitutes(
                "butter",
                flavor_profile,
                current_health_score=45.0
            )
        """
        logger.info(
            f"Finding substitutes for: {risky_ingredient} "
            f"(current health score: {current_health_score})"
        )
        
        # Step 1: Categorize ingredient
        normalized = normalize_ingredient_name(risky_ingredient)
        category = categorize_ingredient(normalized)
        
        logger.debug(f"Ingredient category: {category}")
        
        # Step 2: Get healthy alternative pool
        candidates = self.get_healthy_alternative_pool(category)
        
        if not candidates:
            logger.warning(
                f"No healthy alternatives found for category: {category}"
            )
            return []
        
        logger.debug(f"Found {len(candidates)} candidate substitutes")
        
        # Step 3: Rank substitutes
        ranked_substitutes = self.rank_substitutes(
            candidates,
            flavor_profile,
            current_health_score
        )
        
        logger.info(
            f"Identified {len(ranked_substitutes)} substitute option(s) "
            f"for {risky_ingredient}"
        )
        
        return ranked_substitutes
    
    def get_healthy_alternative_pool(self, ingredient_category: str) -> List[str]:
        """
        Get pool of healthy alternative ingredients for a category.
        
        Uses predefined database of healthy swaps from constants.py.
        Each category has a curated list of healthier alternatives.
        
        Args:
            ingredient_category: Category (e.g., "oil", "sweetener", "dairy")
            
        Returns:
            List[str]: List of healthier ingredient names for this category.
                      Returns empty list if category not found or no alternatives.
                      
        Example:
            alternatives = engine.get_healthy_alternative_pool("oil")
            # Returns: ["olive oil", "avocado oil", "coconut oil"]
        """
        logger.debug(f"Getting healthy alternatives for category: {ingredient_category}")
        
        # Get category-specific alternatives
        category_swaps = self.healthy_swaps.get(ingredient_category, {})
        
        if not category_swaps:
            logger.warning(
                f"No healthy swaps defined for category: {ingredient_category}"
            )
            return []
        
        # Flatten all alternatives from this category
        all_alternatives = []
        for original, alternatives in category_swaps.items():
            all_alternatives.extend(alternatives)
        
        # Remove duplicates while preserving order
        unique_alternatives = []
        seen = set()
        for alt in all_alternatives:
            normalized = normalize_ingredient_name(alt)
            if normalized not in seen:
                seen.add(normalized)
                unique_alternatives.append(alt)
        
        logger.debug(
            f"Found {len(unique_alternatives)} unique alternatives "
            f"for category: {ingredient_category}"
        )
        
        return unique_alternatives
    
    def rank_substitutes(
        self,
        candidates: List[str],
        target_flavor: Dict,
        current_health_score: float
    ) -> List[SubstituteOption]:
        """
        Rank substitute candidates by flavor match and health improvement.
        
        Uses a weighted scoring formula:
        rank_score = (flavor_similarity * 0.6) + (health_improvement * 0.4)
        
        This balances preserving taste (60%) with improving health (40%).
        
        Args:
            candidates: List of candidate ingredient names
            target_flavor: Flavor profile to match against
            current_health_score: Current recipe health score
            
        Returns:
            List[SubstituteOption]: Ranked substitutes (best first)
        """
        logger.info(
            f"Ranking {len(candidates)} substitute candidates "
            f"against target flavor"
        )
        
        substitute_options = []
        
        for candidate in candidates:
            # Skip if candidate is same as target
            if normalize_ingredient_name(candidate) == \
               normalize_ingredient_name(target_flavor.get("ingredient", "")):
                continue
            
            try:
                # Calculate flavor similarity
                flavor_match = self.flavordb_service.calculate_flavor_similarity(
                    target_flavor.get("ingredient", ""),
                    candidate
                )
                
                # Estimate health improvement
                health_improvement = self._estimate_health_improvement(
                    candidate,
                    current_health_score
                )
                
                # Calculate combined rank score
                rank_score = (
                    (flavor_match * self.flavor_weight) +
                    (health_improvement * self.health_weight)
                )
                
                # Generate explanation
                explanation = self._generate_swap_explanation(
                    target_flavor.get("ingredient", ""),
                    candidate,
                    flavor_match,
                    health_improvement
                )
                
                # Create SubstituteOption
                option = SubstituteOption(
                    name=candidate,
                    flavor_match=flavor_match,
                    health_improvement=health_improvement,
                    category=categorize_ingredient(candidate),
                    rank_score=rank_score,
                    explanation=explanation
                )
                
                substitute_options.append(option)
                
                logger.debug(
                    f"Ranked {candidate}: flavor={flavor_match:.1f}%, "
                    f"health_improvement={health_improvement:.1f}, "
                    f"rank_score={rank_score:.2f}"
                )
                
            except Exception as e:
                logger.warning(
                    f"Error processing candidate {candidate}: {str(e)}"
                )
                continue
        
        # Semantic re-ranking (Phase 1: transformer replacement)
        if self.use_semantic_rerank and substitute_options:
            original_ingredient = target_flavor.get("ingredient", "")
            candidate_names = [opt.name for opt in substitute_options]
            ranked_semantic = compute_similarity_scores(original_ingredient, candidate_names)
            if ranked_semantic:
                semantic_map = {name: score for name, score in ranked_semantic}
                for opt in substitute_options:
                    semantic_score = semantic_map.get(opt.name, 50.0)  # 50 = neutral if missing
                    opt.rank_score = (
                        (opt.flavor_match * self.flavor_weight) +
                        (opt.health_improvement * self.health_weight) +
                        (semantic_score * self.semantic_weight)
                    )
                logger.debug(
                    "Applied semantic re-ranking. Top semantic matches: %s",
                    ranked_semantic[:3] if len(ranked_semantic) >= 3 else ranked_semantic,
                )
        
        # Sort by rank score (descending)
        substitute_options.sort(key=lambda x: x.rank_score, reverse=True)
        
        logger.info(
            f"Ranked {len(substitute_options)} substitutes. "
            f"Top option: {substitute_options[0].name if substitute_options else 'None'}"
        )
        
        return substitute_options
    
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
        health_improvement: float
    ) -> str:
        """
        Generate human-readable explanation for a swap recommendation.
        
        Args:
            original: Original ingredient name
            substitute: Substitute ingredient name
            flavor_match: Flavor similarity percentage
            health_improvement: Estimated health score improvement
            
        Returns:
            str: Explanation text
        """
        # Flavor match description
        if flavor_match >= 80:
            flavor_desc = "very similar flavor"
        elif flavor_match >= 60:
            flavor_desc = "similar flavor"
        elif flavor_match >= 40:
            flavor_desc = "moderately different flavor"
        else:
            flavor_desc = "noticeably different flavor"
        
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
            f"Replace {original} with {substitute} ({flavor_desc}, "
            f"{health_desc})"
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

        Each swap only affects the proportional share of nutrition
        attributable to that ingredient (roughly 1/N of total, where N
        is the number of ingredients). This prevents a single swap from
        unrealistically changing the entire recipe's nutrition profile.

        Args:
            original_nutrition: Original nutrition data
            swaps: List of swap dictionaries
            total_ingredients: Total number of ingredients in recipe (used
                to estimate per-ingredient share; 0 = auto-estimate from swaps)

        Returns:
            Dict: Estimated new nutrition data
        """
        logger.info("Estimating nutrition with swaps applied")

        new_nutrition = original_nutrition.copy()

        accepted_swaps = [s for s in swaps if s.get("accepted", False)]
        if not accepted_swaps:
            return new_nutrition

        # Estimate per-ingredient share of total nutrition
        num_ingredients = max(total_ingredients, len(accepted_swaps) + 3)
        ingredient_share = 1.0 / num_ingredients

        for swap in accepted_swaps:
            substitute_obj = swap.get("substitute", {})

            if isinstance(substitute_obj, SubstituteOption):
                substitute_name = substitute_obj.name
            else:
                substitute_name = substitute_obj.get("name", "")

            adjustments = self._get_nutrition_adjustments(substitute_name)

            for nutrient, factor in adjustments.items():
                if nutrient in new_nutrition:
                    original_value = new_nutrition[nutrient]
                    # Only adjust the portion attributable to this ingredient
                    ingredient_contribution = original_value * ingredient_share
                    adjusted_contribution = ingredient_contribution * factor
                    new_nutrition[nutrient] = (
                        original_value - ingredient_contribution + adjusted_contribution
                    )

        logger.debug("Nutrition estimation complete")

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
        
        # Predefined adjustment factors
        # These are rough estimates for common substitutions
        adjustment_map = {
            "olive oil": {
                "saturated_fat": 0.7,  # 30% less saturated fat
                "trans_fat": 0.0,      # No trans fat
            },
            "avocado oil": {
                "saturated_fat": 0.6,
                "trans_fat": 0.0,
            },
            "honey": {
                "sugar": 0.9,          # Slightly less sugar impact
            },
            "stevia": {
                "sugar": 0.1,          # 90% less sugar
                "calories": 0.1,       # 90% fewer calories
            },
            "almond milk": {
                "saturated_fat": 0.3,  # 70% less saturated fat
                "cholesterol": 0.0,    # No cholesterol
            },
            "whole wheat flour": {
                "fiber": 1.5,          # 50% more fiber
            }
        }
        
        # Find matching adjustments
        for ingredient_pattern, adjustments in adjustment_map.items():
            if ingredient_pattern in normalized:
                return adjustments
        
        # Default: minimal improvement
        return {
            "saturated_fat": 0.9,
            "sodium": 0.9,
            "sugar": 0.9
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