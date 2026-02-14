"""
Ingredient risk analysis service.

This module identifies unhealthy or risky ingredients in recipes based on
nutritional content and ingredient keywords. It prioritizes ingredients
for substitution to maximize health improvements.

Risk categories:
- Trans fats and hydrogenated oils (highest priority)
- High sodium ingredients
- High sugar ingredients
- Refined/processed ingredients
- Artificial additives
- Allergens (when present)

The analyzer uses both nutrition data and keyword matching to provide
comprehensive ingredient risk assessment.
"""

import logging
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from app.utils.constants import (
    UNHEALTHY_KEYWORDS,
    NEGATIVE_FACTOR_THRESHOLDS,
    RISKY_INGREDIENT_CATEGORIES
)
from app.utils.helpers import normalize_ingredient_name, categorize_ingredient

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class RiskyIngredient:
    """
    Data class representing a risky or unhealthy ingredient.
    
    Attributes:
        name: Ingredient name as it appears in recipe
        reason: Explanation of why this ingredient is risky
        priority: Priority level for swapping (1-5, where 5 is highest)
        category: Ingredient category (e.g., "oil", "sweetener", "additive")
        health_impact: Estimated negative health impact score
        alternatives_available: Whether healthy substitutes exist
    """
    name: str
    reason: str
    priority: int
    category: str
    health_impact: float
    alternatives_available: bool = True
    
    def to_dict(self) -> Dict:
        """
        Convert risky ingredient to dictionary format.
        
        Returns:
            Dict: Ingredient data as dictionary
        """
        return {
            "name": self.name,
            "reason": self.reason,
            "priority": self.priority,
            "category": self.category,
            "health_impact": self.health_impact,
            "alternatives_available": self.alternatives_available
        }


class IngredientAnalyzer:
    """
    Service class for analyzing ingredient health risks.
    
    Identifies problematic ingredients based on:
    1. Keyword matching (trans fats, refined sugars, artificial additives)
    2. Nutritional analysis (high sodium, high sugar content)
    3. Processing level (highly processed vs whole foods)
    
    Prioritizes ingredients for swapping to maximize health improvements.
    
    Attributes:
        unhealthy_keywords: Dictionary of risk categories and their keywords
        risk_weights: Weight factors for different risk types
    """
    
    def __init__(self):
        """Initialize ingredient analyzer with keyword database."""
        self.unhealthy_keywords = UNHEALTHY_KEYWORDS
        self.risk_weights = {
            "trans_fat": 10.0,      # Highest risk
            "allergen": 9.0,         # Very high risk
            "artificial": 7.0,       # High risk
            "refined": 6.0,          # Medium-high risk
            "high_sodium": 5.0,      # Medium risk
            "high_sugar": 5.0,       # Medium risk
            "processed": 4.0,        # Medium-low risk
            "preservative": 3.0      # Low-medium risk
        }
        
        logger.info("IngredientAnalyzer initialized")
    
    def identify_risky_ingredients(
        self,
        ingredients: List[str],
        nutrition_data: Dict
    ) -> List[RiskyIngredient]:
        """
        Identify ingredients that need swapping based on health risks.
        
        This is the main entry point for ingredient analysis. It combines
        keyword-based detection with nutritional analysis to identify
        problematic ingredients.
        
        Algorithm:
        1. Check each ingredient for unhealthy keywords
        2. Analyze overall nutrition to identify high-risk categories
        3. Match risky categories to specific ingredients
        4. Calculate health impact scores
        5. Assign priority levels
        6. Sort by priority
        
        Args:
            ingredients: List of ingredient strings from recipe
                Example: ["butter", "white sugar", "refined flour"]
            nutrition_data: Dictionary with nutritional values
                {
                    "sodium": float,
                    "sugar": float,
                    "saturated_fat": float,
                    "trans_fat": float,
                    ...
                }
                
        Returns:
            List[RiskyIngredient]: Sorted list of risky ingredients
                                   (highest priority first).
                                   Returns empty list if no risky ingredients found.
                                   
        Example:
            analyzer = IngredientAnalyzer()
            risky = analyzer.identify_risky_ingredients(
                ["butter", "sugar", "hydrogenated oil"],
                {"sodium": 450, "sugar": 30, "trans_fat": 2}
            )
        """
        logger.info(f"Analyzing {len(ingredients)} ingredients for health risks")
        
        risky_ingredients = []
        detected_names = set()  # Avoid duplicates
        
        # Step 1: Keyword-based detection
        for ingredient in ingredients:
            normalized = normalize_ingredient_name(ingredient)
            
            # Check for unhealthy keywords
            risk_reason = self.check_for_unhealthy_keywords(normalized)
            
            if risk_reason:
                # Get ingredient category
                category = categorize_ingredient(normalized)
                
                # Calculate health impact
                health_impact = self._calculate_health_impact(
                    normalized,
                    risk_reason,
                    nutrition_data
                )
                
                # Create RiskyIngredient object
                risky_ing = RiskyIngredient(
                    name=ingredient,
                    reason=risk_reason,
                    priority=0,  # Will be assigned later
                    category=category,
                    health_impact=health_impact,
                    alternatives_available=self._check_alternatives_available(category)
                )
                
                risky_ingredients.append(risky_ing)
                detected_names.add(normalized)
                
                logger.debug(
                    f"Detected risky ingredient: {ingredient} "
                    f"(reason: {risk_reason}, impact: {health_impact:.1f})"
                )
        
        # Step 2: Nutrition-based detection
        nutrition_risky = self._identify_risky_by_nutrition(
            ingredients,
            nutrition_data,
            detected_names
        )
        
        risky_ingredients.extend(nutrition_risky)
        
        # Step 3: Prioritize swaps
        if risky_ingredients:
            risky_ingredients = self.prioritize_swaps(risky_ingredients)
        
        logger.info(
            f"Identified {len(risky_ingredients)} risky ingredient(s) "
            f"for potential swapping"
        )
        
        return risky_ingredients
    
    def check_for_unhealthy_keywords(self, ingredient: str) -> Optional[str]:
        """
        Detect unhealthy ingredients by keyword matching.
        
        Scans ingredient string for keywords indicating health risks
        such as trans fats, artificial additives, refined products, etc.
        
        Args:
            ingredient: Normalized ingredient string (lowercase, trimmed)
                Example: "partially hydrogenated soybean oil"
                
        Returns:
            str: Risk reason if unhealthy keywords found, None otherwise
                 Example: "Contains trans fats (hydrogenated oil)"
                 
        Keywords checked:
        - Trans fats: "hydrogenated", "partially hydrogenated"
        - Refined: "refined", "white flour", "white sugar"
        - Artificial: "artificial", "aspartame", "saccharin"
        - High sodium: "soy sauce", "salt", "sodium"
        - Processed: "processed", "packaged"
        """
        ingredient_lower = ingredient.lower()
        
        # Check each category of unhealthy keywords
        for risk_category, keywords in self.unhealthy_keywords.items():
            for keyword in keywords:
                # Use word boundary matching to avoid false positives
                pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
                
                if re.search(pattern, ingredient_lower):
                    # Generate appropriate reason message
                    reason = self._generate_risk_reason(risk_category, keyword)
                    
                    logger.debug(
                        f"Keyword match: '{keyword}' in '{ingredient}' "
                        f"(category: {risk_category})"
                    )
                    
                    return reason
        
        return None
    
    def _generate_risk_reason(self, risk_category: str, keyword: str) -> str:
        """
        Generate human-readable reason for ingredient risk.
        
        Args:
            risk_category: Category of risk (e.g., "trans_fat", "artificial")
            keyword: The specific keyword that matched
            
        Returns:
            str: Formatted risk reason
        """
        reason_templates = {
            "trans_fat": f"Contains trans fats ({keyword}) which increase heart disease risk",
            "refined": f"Highly refined product ({keyword}) with reduced nutritional value",
            "artificial": f"Contains artificial additives ({keyword}) with potential health concerns",
            "high_sodium": f"High sodium ingredient ({keyword}) may contribute to hypertension",
            "processed": f"Highly processed ingredient ({keyword}) with lower nutrient density",
            "preservative": f"Contains preservatives ({keyword}) that may cause sensitivities"
        }
        
        return reason_templates.get(
            risk_category,
            f"Contains {keyword} which may pose health concerns"
        )
    
    def _identify_risky_by_nutrition(
        self,
        ingredients: List[str],
        nutrition_data: Dict,
        already_detected: set
    ) -> List[RiskyIngredient]:
        """
        Identify risky ingredients based on overall nutritional profile.
        
        If the recipe has high sodium, sugar, or saturated fat, try to
        identify which specific ingredients are likely contributors.
        
        Args:
            ingredients: List of ingredient strings
            nutrition_data: Nutritional data for the recipe
            already_detected: Set of ingredients already flagged
            
        Returns:
            List[RiskyIngredient]: Additional risky ingredients identified
        """
        additional_risky = []
        
        # Check for high sodium
        if nutrition_data.get("sodium", 0) > NEGATIVE_FACTOR_THRESHOLDS["sodium"]:
            sodium_sources = self._find_sodium_sources(ingredients, already_detected)
            additional_risky.extend(sodium_sources)
        
        # Check for high sugar
        if nutrition_data.get("sugar", 0) > NEGATIVE_FACTOR_THRESHOLDS["sugar"]:
            sugar_sources = self._find_sugar_sources(ingredients, already_detected)
            additional_risky.extend(sugar_sources)
        
        # Check for high saturated fat
        if nutrition_data.get("saturated_fat", 0) > NEGATIVE_FACTOR_THRESHOLDS["saturated_fat"]:
            fat_sources = self._find_fat_sources(ingredients, already_detected)
            additional_risky.extend(fat_sources)
        
        return additional_risky
    
    def _find_sodium_sources(
        self,
        ingredients: List[str],
        already_detected: set
    ) -> List[RiskyIngredient]:
        """
        Identify ingredients likely to be high in sodium.
        
        Args:
            ingredients: List of ingredient strings
            already_detected: Set of ingredients already flagged
            
        Returns:
            List[RiskyIngredient]: Sodium-rich ingredients
        """
        high_sodium_indicators = [
            "salt", "soy sauce", "teriyaki", "broth", "stock",
            "bouillon", "pickle", "olive", "caper", "bacon",
            "ham", "sausage", "cheese", "miso"
        ]
        
        risky = []
        
        for ingredient in ingredients:
            normalized = normalize_ingredient_name(ingredient)
            
            if normalized in already_detected:
                continue
            
            # Check if ingredient is likely high in sodium
            for indicator in high_sodium_indicators:
                if indicator in normalized.lower():
                    risky.append(RiskyIngredient(
                        name=ingredient,
                        reason=f"High sodium content ({indicator})",
                        priority=0,
                        category=categorize_ingredient(normalized),
                        health_impact=self.risk_weights["high_sodium"],
                        alternatives_available=True
                    ))
                    already_detected.add(normalized)
                    break
        
        return risky
    
    def _find_sugar_sources(
        self,
        ingredients: List[str],
        already_detected: set
    ) -> List[RiskyIngredient]:
        """
        Identify ingredients likely to be high in sugar.
        
        Args:
            ingredients: List of ingredient strings
            already_detected: Set of ingredients already flagged
            
        Returns:
            List[RiskyIngredient]: Sugar-rich ingredients
        """
        high_sugar_indicators = [
            "sugar", "honey", "syrup", "molasses", "agave",
            "corn syrup", "fructose", "glucose", "dextrose",
            "maltose", "sucrose", "cane juice"
        ]
        
        risky = []
        
        for ingredient in ingredients:
            normalized = normalize_ingredient_name(ingredient)
            
            if normalized in already_detected:
                continue
            
            # Check if ingredient is likely high in sugar
            for indicator in high_sugar_indicators:
                if indicator in normalized.lower():
                    risky.append(RiskyIngredient(
                        name=ingredient,
                        reason=f"High sugar content ({indicator})",
                        priority=0,
                        category=categorize_ingredient(normalized),
                        health_impact=self.risk_weights["high_sugar"],
                        alternatives_available=True
                    ))
                    already_detected.add(normalized)
                    break
        
        return risky
    
    def _find_fat_sources(
        self,
        ingredients: List[str],
        already_detected: set
    ) -> List[RiskyIngredient]:
        """
        Identify ingredients likely to be high in saturated fat.
        
        Args:
            ingredients: List of ingredient strings
            already_detected: Set of ingredients already flagged
            
        Returns:
            List[RiskyIngredient]: High saturated fat ingredients
        """
        high_fat_indicators = [
            "butter", "cream", "lard", "shortening",
            "coconut oil", "palm oil", "cheese", "bacon"
        ]
        
        risky = []
        
        for ingredient in ingredients:
            normalized = normalize_ingredient_name(ingredient)
            
            if normalized in already_detected:
                continue
            
            # Check if ingredient is likely high in saturated fat
            for indicator in high_fat_indicators:
                if indicator in normalized.lower():
                    risky.append(RiskyIngredient(
                        name=ingredient,
                        reason=f"High saturated fat content ({indicator})",
                        priority=0,
                        category=categorize_ingredient(normalized),
                        health_impact=self.risk_weights["refined"],
                        alternatives_available=True
                    ))
                    already_detected.add(normalized)
                    break
        
        return risky
    
    def _calculate_health_impact(
        self,
        ingredient: str,
        risk_reason: str,
        nutrition_data: Dict
    ) -> float:
        """
        Calculate estimated health impact score for a risky ingredient.
        
        Higher scores indicate greater negative health impact.
        
        Args:
            ingredient: Ingredient name
            risk_reason: The risk reason string
            nutrition_data: Overall nutrition data
            
        Returns:
            float: Health impact score (0-10)
        """
        # Extract risk category from reason
        impact = 5.0  # Default medium impact
        
        if "trans fat" in risk_reason.lower():
            impact = self.risk_weights["trans_fat"]
        elif "artificial" in risk_reason.lower():
            impact = self.risk_weights["artificial"]
        elif "refined" in risk_reason.lower():
            impact = self.risk_weights["refined"]
        elif "sodium" in risk_reason.lower():
            impact = self.risk_weights["high_sodium"]
        elif "sugar" in risk_reason.lower():
            impact = self.risk_weights["high_sugar"]
        elif "processed" in risk_reason.lower():
            impact = self.risk_weights["processed"]
        
        return impact
    
    def prioritize_swaps(
        self,
        risky_ingredients: List[RiskyIngredient]
    ) -> List[RiskyIngredient]:
        """
        Sort ingredients by swap priority to maximize health improvements.
        
        Priority is determined by:
        1. Health impact score (higher impact = higher priority)
        2. Availability of healthy alternatives
        3. Ease of substitution
        
        Priority levels (1-5):
        - 5 (Critical): Trans fats, allergens
        - 4 (High): Artificial additives, highly refined
        - 3 (Medium): High sodium, high sugar
        - 2 (Low): Moderately processed
        - 1 (Optional): Minor improvements
        
        Args:
            risky_ingredients: Unsorted list of RiskyIngredient objects
            
        Returns:
            List[RiskyIngredient]: Sorted list (highest priority first)
        """
        logger.info(f"Prioritizing {len(risky_ingredients)} risky ingredients")
        
        # Assign priority levels based on health impact
        for ingredient in risky_ingredients:
            ingredient.priority = self._assign_priority_level(ingredient)
        
        # Sort by priority (descending), then by health impact (descending)
        sorted_ingredients = sorted(
            risky_ingredients,
            key=lambda x: (x.priority, x.health_impact),
            reverse=True
        )
        
        # Log priority distribution
        priority_counts = {}
        for ing in sorted_ingredients:
            priority_counts[ing.priority] = priority_counts.get(ing.priority, 0) + 1
        
        logger.info(f"Priority distribution: {priority_counts}")
        
        return sorted_ingredients
    
    def _assign_priority_level(self, ingredient: RiskyIngredient) -> int:
        """
        Assign priority level (1-5) based on health impact.
        
        Args:
            ingredient: RiskyIngredient object
            
        Returns:
            int: Priority level (1-5)
        """
        impact = ingredient.health_impact
        
        # Critical priority (5)
        if impact >= 9.0:
            return 5
        
        # High priority (4)
        elif impact >= 7.0:
            return 4
        
        # Medium priority (3)
        elif impact >= 5.0:
            return 3
        
        # Low priority (2)
        elif impact >= 3.0:
            return 2
        
        # Optional priority (1)
        else:
            return 1
    
    def _check_alternatives_available(self, category: str) -> bool:
        """
        Check if healthy alternatives exist for an ingredient category.
        
        Args:
            category: Ingredient category
            
        Returns:
            bool: True if alternatives available
        """
        # Most categories have alternatives
        categories_with_alternatives = [
            "oil", "sweetener", "dairy", "grain", "protein",
            "spice", "vegetable", "fruit"
        ]
        
        return category in categories_with_alternatives
    
    def create_risky_from_list(
        self,
        ingredient_names: List[str],
        full_ingredients: List[str]
    ) -> List[RiskyIngredient]:
        """
        Create RiskyIngredient objects from a list of ingredient names.
        
        Used when user manually specifies ingredients to swap rather than
        auto-detection. Matches names to full ingredient strings and
        creates appropriate RiskyIngredient objects.
        
        Args:
            ingredient_names: List of ingredient names to flag
            full_ingredients: Full ingredient list from recipe
            
        Returns:
            List[RiskyIngredient]: RiskyIngredient objects for specified ingredients
        """
        logger.info(f"Creating risky ingredients from {len(ingredient_names)} names")
        
        risky = []
        
        for name in ingredient_names:
            normalized_name = normalize_ingredient_name(name)
            
            # Find matching ingredient in full list
            matched_ingredient = None
            for ingredient in full_ingredients:
                if normalized_name in normalize_ingredient_name(ingredient):
                    matched_ingredient = ingredient
                    break
            
            if not matched_ingredient:
                matched_ingredient = name
            
            # Create RiskyIngredient with user-specified flag
            category = categorize_ingredient(normalized_name)
            
            risky.append(RiskyIngredient(
                name=matched_ingredient,
                reason="User-selected for substitution",
                priority=3,  # Medium priority for user-selected
                category=category,
                health_impact=5.0,
                alternatives_available=True
            ))
        
        logger.info(f"Created {len(risky)} risky ingredients from user selection")
        
        return risky
    
    def get_statistics(self) -> Dict:
        """
        Get statistics about the ingredient analyzer.
        
        Returns:
            Dict: Analyzer statistics
        """
        total_keywords = sum(
            len(keywords) for keywords in self.unhealthy_keywords.values()
        )
        
        return {
            "total_risk_categories": len(self.unhealthy_keywords),
            "total_keywords": total_keywords,
            "risk_categories": list(self.unhealthy_keywords.keys()),
            "risk_weights": self.risk_weights
        }