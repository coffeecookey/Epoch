"""
Rule-based health scoring engine.

This module implements the core "ML" component of the system using
rule-based logic rather than trained statistical models. It calculates
health scores based on nutritional data using predefined thresholds
and weighted scoring rules.

The scoring system is:
- Transparent: All rules are explicitly defined
- Explainable: Score breakdown shows exactly why a recipe got its score
- Modifiable: Rules can be easily adjusted without retraining
- Fast: No model inference overhead

Total possible score: 100 points
- Macronutrients: 0-40 points
- Micronutrients: 0-30 points
- Negative factors: 0 to -30 points (penalties)
"""

import logging
from typing import Dict, List, Tuple

from app.models.health_score import HealthScore
from app.utils.constants import (
    RATING_THRESHOLDS,
    MACRO_TARGETS,
    RDA_VALUES,
    NEGATIVE_FACTOR_THRESHOLDS
)
from app.utils.helpers import calculate_percentage_of_calories

# Configure logging
logger = logging.getLogger(__name__)


class HealthScorer:
    """
    Rule-based health scoring engine for recipes.
    
    Implements a transparent, explainable scoring system that evaluates
    recipes based on macronutrient balance, micronutrient content,
    and negative health factors.
    
    Attributes:
        macro_weight: Weight for macronutrient score (default: 40 points)
        micro_weight: Weight for micronutrient score (default: 30 points)
        negative_weight: Maximum penalty for negative factors (default: -30 points)
    """
    
    def __init__(self):
        """Initialize the health scorer with default weights."""
        self.macro_weight = 40
        self.micro_weight = 30
        self.negative_weight = -30
        
        logger.info(
            f"HealthScorer initialized with weights: "
            f"macro={self.macro_weight}, micro={self.micro_weight}, "
            f"negative={self.negative_weight}"
        )
    
    def calculate_health_score(
        self,
        nutrition_data: Dict,
        micro_nutrition: Dict
    ) -> HealthScore:
        """
        Calculate comprehensive health score for a recipe.
        
        This is the main entry point for health scoring. It orchestrates
        all scoring components and produces a final score with detailed
        breakdown.
        
        Algorithm:
        1. Score macronutrient balance (0-40 points)
        2. Score micronutrient content (0-30 points)
        3. Apply penalties for negative factors (0 to -30 points)
        4. Combine scores and normalize to 0-100 scale
        5. Assign rating category
        
        Args:
            nutrition_data: Dictionary containing macronutrient data
                {
                    "calories": float,
                    "protein": float,
                    "carbs": float,
                    "fat": float,
                    "saturated_fat": float,
                    "trans_fat": float,
                    "sodium": float,
                    "sugar": float,
                    "cholesterol": float,
                    "fiber": float
                }
            micro_nutrition: Dictionary containing micronutrient data
                {
                    "vitamins": {...},
                    "minerals": {...}
                }
                
        Returns:
            HealthScore: Object containing:
                - score: float (0-100)
                - rating: str (Excellent/Good/Decent/Bad/Poor)
                - breakdown: Dict with component scores
                
        Example:
            scorer = HealthScorer()
            score = scorer.calculate_health_score(nutrition, micro_nutrition)
            print(f"Score: {score.score}, Rating: {score.rating}")
        """
        logger.info("Calculating health score")
        
        # Extract macronutrient values
        calories = nutrition_data.get("calories", 0)
        protein = nutrition_data.get("protein", 0)
        carbs = nutrition_data.get("carbs", 0)
        fat = nutrition_data.get("fat", 0)
        
        # Step 1: Score macronutrients
        macro_score = self.score_macronutrients(calories, protein, carbs, fat)
        logger.debug(f"Macronutrient score: {macro_score}/{self.macro_weight}")
        
        # Step 2: Score micronutrients
        micro_score = self.score_micronutrients(micro_nutrition)
        logger.debug(f"Micronutrient score: {micro_score}/{self.micro_weight}")
        
        # Step 3: Apply negative factor penalties
        negative_score = self.score_negative_factors(nutrition_data)
        logger.debug(f"Negative factors penalty: {negative_score}")
        
        # Step 4: Calculate total score
        # Note: negative_score is already negative, so we add it
        raw_score = macro_score + micro_score + negative_score
        
        # Normalize to 0-100 scale
        # Maximum possible: macro_weight + micro_weight = 70
        # Minimum possible: 0 + negative_weight = -30
        # Range: -30 to 70 (total range: 100)
        max_possible = self.macro_weight + self.micro_weight
        min_possible = self.negative_weight
        
        # Shift and scale to 0-100
        normalized_score = ((raw_score - min_possible) / (max_possible - min_possible)) * 100
        
        # Clamp to 0-100 range
        final_score = max(0.0, min(100.0, normalized_score))
        
        # Step 5: Assign rating
        rating = self.assign_rating(final_score)
        
        # Build detailed breakdown
        breakdown = {
            "macronutrient_score": round(macro_score, 2),
            "micronutrient_score": round(micro_score, 2),
            "negative_factors_penalty": round(negative_score, 2),
            "raw_total": round(raw_score, 2),
            "normalized_score": round(final_score, 2),
            "components": {
                "protein_balance": self._check_protein_balance(calories, protein),
                "carb_balance": self._check_carb_balance(calories, carbs),
                "fat_balance": self._check_fat_balance(calories, fat),
                "calorie_density": self._check_calorie_density(calories),
                "micronutrient_adequacy": self._calculate_micronutrient_adequacy(micro_nutrition),
                "negative_factors": self._get_negative_factor_details(nutrition_data)
            }
        }
        
        logger.info(f"Final health score: {final_score:.2f} ({rating})")
        
        return HealthScore(
            score=round(final_score, 2),
            rating=rating,
            breakdown=breakdown
        )
    
    def score_macronutrients(
        self,
        calories: float,
        protein: float,
        carbs: float,
        fat: float
    ) -> float:
        """
        Score recipe based on macronutrient balance.
        
        Evaluates whether macronutrients fall within healthy ranges
        as percentages of total calories. Also considers calorie density.
        
        Scoring rules:
        - Protein 10-35% of calories: +10 points
        - Carbs 45-65% of calories: +10 points
        - Fat 20-35% of calories: +10 points
        - Calorie density <500 cal: +10 points
        
        Partial credit given for near-misses using linear scaling.
        
        Args:
            calories: Total calories per serving
            protein: Protein in grams
            carbs: Carbohydrates in grams
            fat: Fat in grams
            
        Returns:
            float: Macronutrient score (0-40 points)
        """
        score = 0.0
        
        # Avoid division by zero
        if calories <= 0:
            logger.warning("Calories is 0 or negative, cannot score macronutrients")
            return 0.0
        
        # Calculate macronutrient percentages
        protein_percent = calculate_percentage_of_calories(protein, "protein", calories)
        carbs_percent = calculate_percentage_of_calories(carbs, "carbs", calories)
        fat_percent = calculate_percentage_of_calories(fat, "fat", calories)
        
        logger.debug(
            f"Macro percentages - Protein: {protein_percent:.1f}%, "
            f"Carbs: {carbs_percent:.1f}%, Fat: {fat_percent:.1f}%"
        )
        
        # Score protein balance (0-10 points)
        protein_score = self._score_nutrient_range(
            protein_percent,
            MACRO_TARGETS["protein_percent"],
            max_points=10
        )
        score += protein_score
        
        # Score carb balance (0-10 points)
        carbs_score = self._score_nutrient_range(
            carbs_percent,
            MACRO_TARGETS["carbs_percent"],
            max_points=10
        )
        score += carbs_score
        
        # Score fat balance (0-10 points)
        fat_score = self._score_nutrient_range(
            fat_percent,
            MACRO_TARGETS["fat_percent"],
            max_points=10
        )
        score += fat_score
        
        # Score calorie density (0-10 points)
        # Lower calorie density is better (more volume, fewer calories)
        calorie_threshold = 500
        if calories <= calorie_threshold:
            # Full points if below threshold
            calorie_score = 10
        elif calories <= calorie_threshold * 1.5:
            # Partial credit for moderately high calories
            calorie_score = 10 * (1 - (calories - calorie_threshold) / (calorie_threshold * 0.5))
        else:
            # No points for very high calorie recipes
            calorie_score = 0
        
        score += calorie_score
        
        logger.debug(
            f"Macro component scores - Protein: {protein_score:.1f}, "
            f"Carbs: {carbs_score:.1f}, Fat: {fat_score:.1f}, "
            f"Calorie density: {calorie_score:.1f}"
        )
        
        return round(score, 2)
    
    def _score_nutrient_range(
        self,
        value: float,
        target_range: Tuple[float, float],
        max_points: float
    ) -> float:
        """
        Score a nutrient value based on target range with partial credit.
        
        Gives full points if within range, partial credit if close,
        zero points if far outside range.
        
        Args:
            value: Actual nutrient percentage
            target_range: Tuple of (min, max) acceptable values
            max_points: Maximum points for perfect score
            
        Returns:
            float: Points earned (0 to max_points)
        """
        min_val, max_val = target_range
        
        if min_val <= value <= max_val:
            # Within target range - full points
            return max_points
        
        # Calculate distance from range
        if value < min_val:
            distance = min_val - value
            tolerance = min_val * 0.2  # 20% tolerance below minimum
        else:  # value > max_val
            distance = value - max_val
            tolerance = max_val * 0.2  # 20% tolerance above maximum
        
        # Give partial credit if within tolerance
        if distance <= tolerance:
            # Linear decay from max_points to 0
            return max_points * (1 - distance / tolerance)
        
        # Too far outside range - no points
        return 0.0
    
    def score_micronutrients(self, micro_data: Dict) -> float:
        """
        Score recipe based on vitamin and mineral content.
        
        Evaluates micronutrient content against Recommended Daily Allowances (RDA).
        Higher scores indicate better micronutrient density.
        
        Scoring rules:
        - Each vitamin/mineral meeting >=100% RDA: +2 points
        - Each vitamin/mineral meeting 50-99% RDA: +1 point
        - Maximum total: 30 points
        
        Args:
            micro_data: Dictionary with structure:
                {
                    "vitamins": {"vitamin_c": 90, "vitamin_d": 20, ...},
                    "minerals": {"calcium": 1000, "iron": 18, ...}
                }
                
        Returns:
            float: Micronutrient score (0-30 points)
        """
        score = 0.0
        nutrients_evaluated = 0
        nutrients_adequate = 0
        
        vitamins = micro_data.get("vitamins", {})
        minerals = micro_data.get("minerals", {})
        
        # Combine all micronutrients
        all_nutrients = {**vitamins, **minerals}
        
        for nutrient_name, nutrient_value in all_nutrients.items():
            # Get RDA for this nutrient
            rda = RDA_VALUES.get(nutrient_name)
            
            if rda is None or rda <= 0:
                # Skip nutrients without defined RDA
                continue
            
            nutrients_evaluated += 1
            
            # Calculate percentage of RDA
            percent_rda = (nutrient_value / rda) * 100
            
            # Score based on RDA percentage
            if percent_rda >= 100:
                # Meets or exceeds RDA - full points
                score += 2
                nutrients_adequate += 1
            elif percent_rda >= 50:
                # Meets 50-99% of RDA - partial points
                score += 1
            # else: Below 50% RDA - no points
        
        # Cap at maximum points
        score = min(score, self.micro_weight)
        
        logger.debug(
            f"Micronutrient scoring: {nutrients_adequate}/{nutrients_evaluated} "
            f"nutrients adequate, score: {score:.1f}/{self.micro_weight}"
        )
        
        return round(score, 2)
    
    def score_negative_factors(self, nutrition_data: Dict) -> float:
        """
        Apply penalties for unhealthy nutritional elements.
        
        Deducts points for excessive amounts of sodium, sugar, saturated fat,
        trans fat, and cholesterol. These are health risk factors.
        
        Penalty rules:
        - Sodium >400mg: -5 points
        - Sugar >25g: -5 points
        - Saturated fat >10g: -5 points
        - Trans fat >0.5g: -10 points (severe penalty)
        - Cholesterol >100mg: -5 points
        
        Maximum total penalty: -30 points
        
        Args:
            nutrition_data: Dictionary containing negative factor values
            
        Returns:
            float: Penalty score (0 to -30 points)
        """
        penalty = 0.0
        
        # Check sodium
        sodium = nutrition_data.get("sodium", 0)
        if sodium > NEGATIVE_FACTOR_THRESHOLDS["sodium"]:
            penalty -= 5
            logger.debug(f"Sodium penalty applied: {sodium}mg > threshold")
        
        # Check sugar
        sugar = nutrition_data.get("sugar", 0)
        if sugar > NEGATIVE_FACTOR_THRESHOLDS["sugar"]:
            penalty -= 5
            logger.debug(f"Sugar penalty applied: {sugar}g > threshold")
        
        # Check saturated fat
        saturated_fat = nutrition_data.get("saturated_fat", 0)
        if saturated_fat > NEGATIVE_FACTOR_THRESHOLDS["saturated_fat"]:
            penalty -= 5
            logger.debug(f"Saturated fat penalty applied: {saturated_fat}g > threshold")
        
        # Check trans fat (severe penalty)
        trans_fat = nutrition_data.get("trans_fat", 0)
        if trans_fat > NEGATIVE_FACTOR_THRESHOLDS["trans_fat"]:
            penalty -= 10
            logger.debug(f"Trans fat penalty applied: {trans_fat}g > threshold (severe)")
        
        # Check cholesterol
        cholesterol = nutrition_data.get("cholesterol", 0)
        if cholesterol > NEGATIVE_FACTOR_THRESHOLDS["cholesterol"]:
            penalty -= 5
            logger.debug(f"Cholesterol penalty applied: {cholesterol}mg > threshold")
        
        # Cap penalty at minimum (most negative allowed)
        penalty = max(penalty, self.negative_weight)
        
        logger.debug(f"Total negative factors penalty: {penalty}")
        
        return round(penalty, 2)
    
    def assign_rating(self, score: float) -> str:
        """
        Convert numeric health score to categorical rating.
        
        Uses predefined thresholds to assign human-readable ratings.
        
        Rating thresholds:
        - 80-100: "Excellent" (Very healthy, minimal improvements needed)
        - 60-79: "Good" (Healthy overall, some room for improvement)
        - 40-59: "Decent" (Acceptable, significant improvements possible)
        - 20-39: "Bad" (Unhealthy, major changes recommended)
        - 0-19: "Poor" (Very unhealthy, complete reformulation needed)
        
        Args:
            score: Health score (0-100)
            
        Returns:
            str: Rating category
        """
        if score >= RATING_THRESHOLDS["Excellent"]:
            return "Excellent"
        elif score >= RATING_THRESHOLDS["Good"]:
            return "Good"
        elif score >= RATING_THRESHOLDS["Decent"]:
            return "Decent"
        elif score >= RATING_THRESHOLDS["Bad"]:
            return "Bad"
        else:
            return "Poor"
    
    def _check_protein_balance(self, calories: float, protein: float) -> Dict:
        """
        Get detailed protein balance information.
        
        Args:
            calories: Total calories
            protein: Protein in grams
            
        Returns:
            Dict: Protein balance details
        """
        if calories <= 0:
            return {"status": "unknown", "percentage": 0, "target": "10-35%"}
        
        percent = calculate_percentage_of_calories(protein, "protein", calories)
        min_target, max_target = MACRO_TARGETS["protein_percent"]
        
        if min_target <= percent <= max_target:
            status = "optimal"
        elif percent < min_target:
            status = "low"
        else:
            status = "high"
        
        return {
            "status": status,
            "percentage": round(percent, 1),
            "target": f"{min_target}-{max_target}%",
            "actual_grams": protein
        }
    
    def _check_carb_balance(self, calories: float, carbs: float) -> Dict:
        """
        Get detailed carbohydrate balance information.
        
        Args:
            calories: Total calories
            carbs: Carbohydrates in grams
            
        Returns:
            Dict: Carbohydrate balance details
        """
        if calories <= 0:
            return {"status": "unknown", "percentage": 0, "target": "45-65%"}
        
        percent = calculate_percentage_of_calories(carbs, "carbs", calories)
        min_target, max_target = MACRO_TARGETS["carbs_percent"]
        
        if min_target <= percent <= max_target:
            status = "optimal"
        elif percent < min_target:
            status = "low"
        else:
            status = "high"
        
        return {
            "status": status,
            "percentage": round(percent, 1),
            "target": f"{min_target}-{max_target}%",
            "actual_grams": carbs
        }
    
    def _check_fat_balance(self, calories: float, fat: float) -> Dict:
        """
        Get detailed fat balance information.
        
        Args:
            calories: Total calories
            fat: Fat in grams
            
        Returns:
            Dict: Fat balance details
        """
        if calories <= 0:
            return {"status": "unknown", "percentage": 0, "target": "20-35%"}
        
        percent = calculate_percentage_of_calories(fat, "fat", calories)
        min_target, max_target = MACRO_TARGETS["fat_percent"]
        
        if min_target <= percent <= max_target:
            status = "optimal"
        elif percent < min_target:
            status = "low"
        else:
            status = "high"
        
        return {
            "status": status,
            "percentage": round(percent, 1),
            "target": f"{min_target}-{max_target}%",
            "actual_grams": fat
        }
    
    def _check_calorie_density(self, calories: float) -> Dict:
        """
        Get calorie density assessment.
        
        Args:
            calories: Total calories per serving
            
        Returns:
            Dict: Calorie density information
        """
        threshold = 500
        
        if calories <= threshold:
            status = "good"
        elif calories <= threshold * 1.5:
            status = "moderate"
        else:
            status = "high"
        
        return {
            "status": status,
            "calories": calories,
            "threshold": threshold
        }
    
    def _calculate_micronutrient_adequacy(self, micro_data: Dict) -> Dict:
        """
        Calculate overall micronutrient adequacy.
        
        Args:
            micro_data: Micronutrient dictionary
            
        Returns:
            Dict: Adequacy summary
        """
        vitamins = micro_data.get("vitamins", {})
        minerals = micro_data.get("minerals", {})
        
        all_nutrients = {**vitamins, **minerals}
        
        total_count = 0
        adequate_count = 0
        
        for nutrient_name, nutrient_value in all_nutrients.items():
            rda = RDA_VALUES.get(nutrient_name)
            if rda and rda > 0:
                total_count += 1
                percent_rda = (nutrient_value / rda) * 100
                if percent_rda >= 100:
                    adequate_count += 1
        
        adequacy_percent = (adequate_count / total_count * 100) if total_count > 0 else 0
        
        return {
            "adequate_count": adequate_count,
            "total_count": total_count,
            "adequacy_percentage": round(adequacy_percent, 1)
        }
    
    def _get_negative_factor_details(self, nutrition_data: Dict) -> List[Dict]:
        """
        Get detailed information about triggered negative factors.
        
        Args:
            nutrition_data: Nutrition dictionary
            
        Returns:
            List[Dict]: List of triggered negative factors
        """
        factors = []
        
        sodium = nutrition_data.get("sodium", 0)
        if sodium > NEGATIVE_FACTOR_THRESHOLDS["sodium"]:
            factors.append({
                "factor": "sodium",
                "value": sodium,
                "threshold": NEGATIVE_FACTOR_THRESHOLDS["sodium"],
                "unit": "mg",
                "penalty": -5
            })
        
        sugar = nutrition_data.get("sugar", 0)
        if sugar > NEGATIVE_FACTOR_THRESHOLDS["sugar"]:
            factors.append({
                "factor": "sugar",
                "value": sugar,
                "threshold": NEGATIVE_FACTOR_THRESHOLDS["sugar"],
                "unit": "g",
                "penalty": -5
            })
        
        saturated_fat = nutrition_data.get("saturated_fat", 0)
        if saturated_fat > NEGATIVE_FACTOR_THRESHOLDS["saturated_fat"]:
            factors.append({
                "factor": "saturated_fat",
                "value": saturated_fat,
                "threshold": NEGATIVE_FACTOR_THRESHOLDS["saturated_fat"],
                "unit": "g",
                "penalty": -5
            })
        
        trans_fat = nutrition_data.get("trans_fat", 0)
        if trans_fat > NEGATIVE_FACTOR_THRESHOLDS["trans_fat"]:
            factors.append({
                "factor": "trans_fat",
                "value": trans_fat,
                "threshold": NEGATIVE_FACTOR_THRESHOLDS["trans_fat"],
                "unit": "g",
                "penalty": -10
            })
        
        cholesterol = nutrition_data.get("cholesterol", 0)
        if cholesterol > NEGATIVE_FACTOR_THRESHOLDS["cholesterol"]:
            factors.append({
                "factor": "cholesterol",
                "value": cholesterol,
                "threshold": NEGATIVE_FACTOR_THRESHOLDS["cholesterol"],
                "unit": "mg",
                "penalty": -5
            })
        
        return factors