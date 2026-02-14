"""
Recipe recommendation engine.

This module finds similar healthy recipes for Workflow 1 (healthy recipe
recommendation). It queries RecipeDB for similar recipes, filters by
health criteria, and ranks them by relevance.

Similarity is calculated based on:
- Cuisine type (30%)
- Calorie similarity (20%)
- Protein similarity (20%)
- Shared ingredients (30%)

Recommendations are ranked by a combination of similarity and health score.
"""

import logging
from typing import List, Dict, Optional, Set
from dataclasses import dataclass

from app.services.recipedb_service import RecipeDBService
from app.services.health_scorer import HealthScorer
from app.utils.helpers import normalize_ingredient_name

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class RecipeRecommendation:
    """
    Data class representing a recipe recommendation.
    
    Attributes:
        recipe: Recipe data dictionary
        similarity_score: How similar to original recipe (0-100)
        health_score: Health score of this recipe (0-100)
        relevance_score: Combined ranking score
        reason: Explanation for why this was recommended
    """
    recipe: Dict
    similarity_score: float
    health_score: float
    relevance_score: float
    reason: str
    
    def to_dict(self) -> Dict:
        """
        Convert recommendation to dictionary format.
        
        Returns:
            Dict: Recommendation data as dictionary
        """
        return {
            "recipe": self.recipe,
            "similarity_score": round(self.similarity_score, 2),
            "health_score": round(self.health_score, 2),
            "relevance_score": round(self.relevance_score, 2),
            "reason": self.reason
        }


class RecommendationEngine:
    """
    Engine for finding and ranking similar healthy recipes.
    
    Uses RecipeDB to find recipes with similar characteristics and
    HealthScorer to evaluate their nutritional quality.
    
    Attributes:
        recipedb_service: Service for recipe queries
        health_scorer: Service for health scoring
        similarity_weight: Weight for similarity in ranking (0-1)
        health_weight: Weight for health score in ranking (0-1)
    """
    
    def __init__(
        self,
        recipedb_service: RecipeDBService,
        health_scorer: HealthScorer
    ):
        """
        Initialize recommendation engine with required services.
        
        Args:
            recipedb_service: RecipeDB service instance
            health_scorer: Health scorer instance
        """
        self.recipedb_service = recipedb_service
        self.health_scorer = health_scorer
        
        # Ranking weights (must sum to 1.0)
        self.similarity_weight = 0.5  # 50% weight on similarity
        self.health_weight = 0.5      # 50% weight on health score
        
        logger.info(
            f"RecommendationEngine initialized with "
            f"similarity_weight={self.similarity_weight}, "
            f"health_weight={self.health_weight}"
        )
    
    def find_similar_recipes(
        self,
        recipe_id: str,
        min_health_score: float = 60.0,
        limit: int = 5
    ) -> List[RecipeRecommendation]:
        """
        Find similar healthy recipes for Workflow 1.
        
        This is the main entry point for recipe recommendations. It queries
        RecipeDB for similar recipes, filters by health criteria, scores
        them, and returns the top recommendations.
        
        Algorithm:
        1. Fetch original recipe data
        2. Query RecipeDB for similar recipes (by cuisine, calories, protein)
        3. Score health of each candidate recipe
        4. Filter by minimum health score
        5. Calculate similarity scores
        6. Rank by combined similarity + health score
        7. Return top N recommendations
        
        Args:
            recipe_id: ID of the original recipe to find alternatives for
            min_health_score: Minimum health score threshold (default: 60.0)
            limit: Maximum number of recommendations to return (default: 5)
            
        Returns:
            List[RecipeRecommendation]: Ranked list of recipe recommendations
                                        (best matches first).
                                        Returns empty list if no suitable recipes found.
                                        
        Example:
            engine = RecommendationEngine(recipedb_service, health_scorer)
            recommendations = engine.find_similar_recipes(
                recipe_id="12345",
                min_health_score=60.0,
                limit=5
            )
        """
        logger.info(
            f"Finding similar recipes for recipe_id={recipe_id}, "
            f"min_health_score={min_health_score}, limit={limit}"
        )
        
        # Step 1: Fetch original recipe
        original_recipe = self.recipedb_service.get_recipe_by_id(recipe_id)
        
        if not original_recipe:
            logger.warning(f"Recipe not found: {recipe_id}")
            return []
        
        # Get nutrition data for original recipe
        try:
            original_nutrition = self.recipedb_service.fetch_nutrition_info(recipe_id)
            original_micro = self.recipedb_service.fetch_micro_nutrition_info(recipe_id)
        except Exception as e:
            logger.error(f"Failed to fetch nutrition for original recipe: {str(e)}")
            original_nutrition = {}
            original_micro = {}
        
        # Step 2: Query for similar recipes
        candidate_recipes = self._query_similar_recipes(original_recipe, original_nutrition)
        
        if not candidate_recipes:
            logger.warning("No candidate recipes found")
            return []
        
        logger.info(f"Found {len(candidate_recipes)} candidate recipes")
        
        # Step 3 & 4: Score health and filter
        healthy_recipes = self.filter_by_health_criteria(
            candidate_recipes,
            min_health_score
        )
        
        logger.info(
            f"{len(healthy_recipes)} recipes passed health criteria "
            f"(min_score={min_health_score})"
        )
        
        if not healthy_recipes:
            logger.warning("No recipes met health criteria")
            return []
        
        # Step 5 & 6: Calculate similarity and rank
        recommendations = self.rank_recommendations(
            healthy_recipes,
            original_recipe
        )
        
        # Step 7: Return top N
        top_recommendations = recommendations[:limit]
        
        logger.info(
            f"Returning {len(top_recommendations)} recommendation(s) "
            f"out of {len(recommendations)} candidates"
        )
        
        return top_recommendations
    
    def _query_similar_recipes(
        self,
        original_recipe: Dict,
        original_nutrition: Dict
    ) -> List[Dict]:
        """
        Query RecipeDB for recipes similar to the original.
        
        Uses multiple search criteria:
        - Same cuisine
        - Similar calorie range
        - Similar protein range
        
        Args:
            original_recipe: Original recipe data
            original_nutrition: Original nutrition data
            
        Returns:
            List[Dict]: Candidate recipes (may contain duplicates)
        """
        candidates = []
        seen_ids = set()
        
        # Query 1: By cuisine
        cuisine = original_recipe.get("cuisine")
        if cuisine:
            logger.debug(f"Querying recipes by cuisine: {cuisine}")
            try:
                cuisine_recipes = self.recipedb_service.search_by_cuisine(cuisine)
                for recipe in cuisine_recipes:
                    recipe_id = recipe.get("id")
                    if recipe_id and recipe_id not in seen_ids:
                        candidates.append(recipe)
                        seen_ids.add(recipe_id)
            except Exception as e:
                logger.warning(f"Cuisine search failed: {str(e)}")
        
        # Query 2: By calories
        calories = original_nutrition.get("calories", 0)
        if calories > 0:
            calorie_min = max(0, calories - 100)
            calorie_max = calories + 100
            logger.debug(f"Querying recipes by calories: {calorie_min}-{calorie_max}")
            try:
                calorie_recipes = self.recipedb_service.search_by_calories(
                    int(calorie_min),
                    int(calorie_max),
                    limit=20
                )
                for recipe in calorie_recipes:
                    recipe_id = recipe.get("id")
                    if recipe_id and recipe_id not in seen_ids:
                        candidates.append(recipe)
                        seen_ids.add(recipe_id)
            except Exception as e:
                logger.warning(f"Calorie search failed: {str(e)}")
        
        # Query 3: By protein
        protein = original_nutrition.get("protein", 0)
        if protein > 0:
            protein_min = max(0, protein - 5)
            protein_max = protein + 5
            logger.debug(f"Querying recipes by protein: {protein_min}g-{protein_max}g")
            try:
                protein_recipes = self.recipedb_service.search_by_protein(
                    protein_min,
                    protein_max
                )
                for recipe in protein_recipes:
                    recipe_id = recipe.get("id")
                    if recipe_id and recipe_id not in seen_ids:
                        candidates.append(recipe)
                        seen_ids.add(recipe_id)
            except Exception as e:
                logger.warning(f"Protein search failed: {str(e)}")
        
        # Query 4: By diet type if available
        diet_type = original_recipe.get("diet_type")
        if diet_type:
            logger.debug(f"Querying recipes by diet: {diet_type}")
            try:
                diet_recipes = self.recipedb_service.search_by_diet(diet_type)
                for recipe in diet_recipes:
                    recipe_id = recipe.get("id")
                    if recipe_id and recipe_id not in seen_ids:
                        candidates.append(recipe)
                        seen_ids.add(recipe_id)
            except Exception as e:
                logger.warning(f"Diet search failed: {str(e)}")
        
        logger.debug(f"Collected {len(candidates)} unique candidate recipes")
        
        return candidates
    
    def calculate_similarity(self, recipe1: Dict, recipe2: Dict) -> float:
        """
        Calculate similarity score between two recipes.
        
        Uses multiple factors with weighted scoring:
        - Cuisine match: 30 points
        - Calorie similarity: 20 points (within +/- 100 cal)
        - Protein similarity: 20 points (within +/- 5g)
        - Shared ingredients: 30 points
        
        Args:
            recipe1: First recipe data dict
            recipe2: Second recipe data dict
            
        Returns:
            float: Similarity percentage (0-100)
            
        Example:
            similarity = engine.calculate_similarity(recipe1, recipe2)
            # Returns: 75.5 (high similarity)
        """
        score = 0.0
        
        # Factor 1: Cuisine match (30 points)
        cuisine1 = recipe1.get("cuisine", "").lower()
        cuisine2 = recipe2.get("cuisine", "").lower()
        
        if cuisine1 and cuisine2 and cuisine1 == cuisine2:
            score += 30
            logger.debug("Cuisine match: +30 points")
        
        # Factor 2: Calorie similarity (20 points)
        # Need to fetch nutrition data
        try:
            nutrition1 = self.recipedb_service.fetch_nutrition_info(recipe1.get("id"))
            nutrition2 = self.recipedb_service.fetch_nutrition_info(recipe2.get("id"))
            
            calories1 = nutrition1.get("calories", 0)
            calories2 = nutrition2.get("calories", 0)
            
            if calories1 > 0 and calories2 > 0:
                calorie_diff = abs(calories1 - calories2)
                if calorie_diff <= 100:
                    # Linear scaling: 0 diff = 20 points, 100 diff = 0 points
                    calorie_score = 20 * (1 - calorie_diff / 100)
                    score += calorie_score
                    logger.debug(f"Calorie similarity: +{calorie_score:.1f} points")
            
            # Factor 3: Protein similarity (20 points)
            protein1 = nutrition1.get("protein", 0)
            protein2 = nutrition2.get("protein", 0)
            
            if protein1 > 0 and protein2 > 0:
                protein_diff = abs(protein1 - protein2)
                if protein_diff <= 5:
                    # Linear scaling: 0 diff = 20 points, 5 diff = 0 points
                    protein_score = 20 * (1 - protein_diff / 5)
                    score += protein_score
                    logger.debug(f"Protein similarity: +{protein_score:.1f} points")
        
        except Exception as e:
            logger.warning(f"Could not fetch nutrition for similarity calc: {str(e)}")
        
        # Factor 4: Shared ingredients (30 points)
        ingredients1 = recipe1.get("ingredients", [])
        ingredients2 = recipe2.get("ingredients", [])
        
        if ingredients1 and ingredients2:
            # Normalize ingredient names for comparison
            set1 = {normalize_ingredient_name(ing) for ing in ingredients1}
            set2 = {normalize_ingredient_name(ing) for ing in ingredients2}
            
            # Jaccard similarity
            intersection = set1.intersection(set2)
            union = set1.union(set2)
            
            if union:
                ingredient_similarity = len(intersection) / len(union)
                ingredient_score = 30 * ingredient_similarity
                score += ingredient_score
                logger.debug(
                    f"Ingredient similarity: +{ingredient_score:.1f} points "
                    f"({len(intersection)}/{len(union)} shared)"
                )
        
        return round(score, 2)
    
    def filter_by_health_criteria(
        self,
        recipes: List[Dict],
        min_score: float
    ) -> List[Dict]:
        """
        Filter recipes by minimum health score threshold.
        
        Fetches nutrition data and calculates health scores for all
        candidate recipes, then filters out those below the threshold.
        
        Args:
            recipes: List of recipe data dictionaries
            min_score: Minimum acceptable health score (0-100)
            
        Returns:
            List[Dict]: Recipes meeting health criteria, with health_score added
        """
        logger.info(
            f"Filtering {len(recipes)} recipes by min_health_score={min_score}"
        )
        
        healthy_recipes = []
        
        for recipe in recipes:
            recipe_id = recipe.get("id")
            
            try:
                # Fetch nutrition data
                nutrition = self.recipedb_service.fetch_nutrition_info(recipe_id)
                micro_nutrition = self.recipedb_service.fetch_micro_nutrition_info(recipe_id)
                
                # Calculate health score
                health_score_obj = self.health_scorer.calculate_health_score(
                    nutrition,
                    micro_nutrition
                )
                
                # Check if meets threshold
                if health_score_obj.score >= min_score:
                    # Add health score to recipe data
                    recipe_with_score = recipe.copy()
                    recipe_with_score["health_score"] = health_score_obj.score
                    recipe_with_score["health_rating"] = health_score_obj.rating
                    recipe_with_score["nutrition"] = nutrition
                    
                    healthy_recipes.append(recipe_with_score)
                    
                    logger.debug(
                        f"Recipe {recipe.get('name', 'Unknown')} passed filter: "
                        f"score={health_score_obj.score:.1f}"
                    )
                else:
                    logger.debug(
                        f"Recipe {recipe.get('name', 'Unknown')} filtered out: "
                        f"score={health_score_obj.score:.1f} < {min_score}"
                    )
            
            except Exception as e:
                logger.warning(
                    f"Could not score recipe {recipe_id}: {str(e)}"
                )
                continue
        
        logger.info(
            f"{len(healthy_recipes)} out of {len(recipes)} recipes passed filter"
        )
        
        return healthy_recipes
    
    def rank_recommendations(
        self,
        recipes: List[Dict],
        original_recipe: Dict
    ) -> List[RecipeRecommendation]:
        """
        Rank recommendations by relevance (similarity + health score).
        
        Uses weighted formula:
        relevance_score = (similarity * 0.5) + (health_score * 0.5)
        
        This balances finding similar recipes (50%) with finding healthy
        ones (50%).
        
        Args:
            recipes: List of candidate recipes (with health_score already calculated)
            original_recipe: Original recipe for similarity calculation
            
        Returns:
            List[RecipeRecommendation]: Sorted recommendations (best first)
        """
        logger.info(f"Ranking {len(recipes)} recipe recommendations")
        
        recommendations = []
        
        for recipe in recipes:
            # Calculate similarity to original
            similarity_score = self.calculate_similarity(original_recipe, recipe)
            
            # Get health score (already calculated during filtering)
            health_score = recipe.get("health_score", 0.0)
            
            # Calculate combined relevance score
            relevance_score = (
                (similarity_score * self.similarity_weight) +
                (health_score * self.health_weight)
            )
            
            # Generate recommendation reason
            reason = self._generate_recommendation_reason(
                recipe,
                original_recipe,
                similarity_score,
                health_score
            )
            
            # Create RecipeRecommendation object
            recommendation = RecipeRecommendation(
                recipe=recipe,
                similarity_score=similarity_score,
                health_score=health_score,
                relevance_score=relevance_score,
                reason=reason
            )
            
            recommendations.append(recommendation)
            
            logger.debug(
                f"Ranked {recipe.get('name', 'Unknown')}: "
                f"similarity={similarity_score:.1f}, health={health_score:.1f}, "
                f"relevance={relevance_score:.1f}"
            )
        
        # Sort by relevance score (descending)
        recommendations.sort(key=lambda x: x.relevance_score, reverse=True)
        
        logger.info(
            f"Top recommendation: {recommendations[0].recipe.get('name', 'Unknown')} "
            f"(relevance={recommendations[0].relevance_score:.1f})"
            if recommendations else "No recommendations"
        )
        
        return recommendations
    
    def _generate_recommendation_reason(
        self,
        recipe: Dict,
        original_recipe: Dict,
        similarity_score: float,
        health_score: float
    ) -> str:
        """
        Generate human-readable reason for recommending this recipe.
        
        Args:
            recipe: Recommended recipe
            original_recipe: Original recipe
            similarity_score: Similarity percentage
            health_score: Health score
            
        Returns:
            str: Recommendation reason
        """
        reasons = []
        
        # Cuisine match
        if recipe.get("cuisine") == original_recipe.get("cuisine"):
            reasons.append(f"same {recipe.get('cuisine', '')} cuisine")
        
        # Health score
        health_rating = recipe.get("health_rating", "")
        if health_rating:
            reasons.append(f"{health_rating.lower()} health rating")
        
        # Similarity
        if similarity_score >= 70:
            reasons.append("very similar recipe")
        elif similarity_score >= 50:
            reasons.append("similar recipe")
        
        # Combine reasons
        if reasons:
            return "Recommended: " + ", ".join(reasons)
        else:
            return "Healthy alternative recipe"
    
    def get_statistics(self) -> Dict:
        """
        Get statistics about the recommendation engine.
        
        Returns:
            Dict: Recommendation engine statistics
        """
        return {
            "similarity_weight": self.similarity_weight,
            "health_weight": self.health_weight,
            "similarity_factors": {
                "cuisine_match": 30,
                "calorie_similarity": 20,
                "protein_similarity": 20,
                "shared_ingredients": 30
            }
        }