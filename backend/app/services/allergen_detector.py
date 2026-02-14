"""
Allergen detection service.

This module identifies common food allergens in recipe ingredients using
keyword matching against a comprehensive allergen database. It provides
severity classifications and detailed allergen information for user safety.

The system focuses on the "Big 8" allergens that account for ~90% of
food allergic reactions:
1. Milk
2. Eggs
3. Peanuts
4. Tree nuts
5. Soy
6. Wheat
7. Fish
8. Shellfish

Note: This is a simplified MVP implementation using keyword matching.
Production systems should use more sophisticated NLP and consider
cross-contamination risks more thoroughly.
"""

import logging
from typing import List, Dict, Set
import re

from app.utils.constants import ALLERGEN_KEYWORDS, ALLERGEN_SEVERITY_MAP
from app.utils.helpers import normalize_ingredient_name

# Configure logging
logger = logging.getLogger(__name__)


class Allergen:
    """
    Data class representing a detected allergen.
    
    Attributes:
        name: Allergen category (e.g., "milk", "peanuts")
        severity: Risk level ("high", "medium", "low")
        source_ingredient: The ingredient that triggered detection
        matched_keyword: The specific keyword that matched
    """
    
    def __init__(
        self,
        name: str,
        severity: str,
        source_ingredient: str,
        matched_keyword: str
    ):
        """
        Initialize an Allergen object.
        
        Args:
            name: Allergen category name
            severity: Severity level
            source_ingredient: Original ingredient string
            matched_keyword: Keyword that triggered detection
        """
        self.name = name
        self.severity = severity
        self.source_ingredient = source_ingredient
        self.matched_keyword = matched_keyword
    
    def to_dict(self) -> Dict:
        """
        Convert allergen to dictionary format.
        
        Returns:
            Dict: Allergen data as dictionary
        """
        return {
            "name": self.name,
            "severity": self.severity,
            "source_ingredient": self.source_ingredient,
            "matched_keyword": self.matched_keyword
        }


class AllergenDetector:
    """
    Service class for detecting allergens in recipe ingredients.
    
    Uses keyword matching to identify potential allergens and assigns
    severity levels based on allergen type and detection confidence.
    
    Attributes:
        allergen_keywords: Dictionary mapping allergen names to keyword lists
        severity_map: Dictionary mapping allergen names to severity levels
    """
    
    def __init__(self):
        """Initialize allergen detector with keyword database."""
        self.allergen_keywords = ALLERGEN_KEYWORDS
        self.severity_map = ALLERGEN_SEVERITY_MAP
        
        logger.info(
            f"AllergenDetector initialized with {len(self.allergen_keywords)} "
            f"allergen categories"
        )
    
    def detect_allergens(self, ingredients: List[str]) -> List[Allergen]:
        """
        Scan a list of ingredients for allergens.
        
        This is the main entry point for allergen detection. It processes
        all ingredients and returns a deduplicated list of detected allergens
        with their severity levels and source ingredients.
        
        Algorithm:
        1. Normalize each ingredient name
        2. Check against all allergen keyword lists
        3. Create Allergen objects for matches
        4. Deduplicate (same allergen from multiple ingredients)
        5. Sort by severity (high > medium > low)
        
        Args:
            ingredients: List of ingredient strings from recipe
                Example: ["milk", "wheat flour", "eggs", "butter"]
                
        Returns:
            List[Allergen]: List of detected allergen objects, sorted by severity.
                           Returns empty list if no allergens found.
                           
        Example:
            detector = AllergenDetector()
            allergens = detector.detect_allergens(["milk", "peanut butter", "flour"])
            for allergen in allergens:
                print(f"Found {allergen.name} in {allergen.source_ingredient}")
        """
        logger.info(f"Scanning {len(ingredients)} ingredients for allergens")
        
        detected_allergens = []
        allergen_set = set()  # Track unique allergen-ingredient pairs
        
        for ingredient in ingredients:
            # Normalize ingredient name for matching
            normalized = normalize_ingredient_name(ingredient)
            
            # Check for allergens in this ingredient
            allergen_names = self.check_ingredient_for_allergens(normalized)
            
            for allergen_name in allergen_names:
                # Create unique key to avoid duplicates
                unique_key = f"{allergen_name}:{ingredient}"
                
                if unique_key not in allergen_set:
                    allergen_set.add(unique_key)
                    
                    # Get severity for this allergen
                    severity = self.get_allergen_severity(allergen_name)
                    
                    # Find which keyword triggered the match (for transparency)
                    matched_keyword = self._find_matched_keyword(
                        normalized,
                        allergen_name
                    )
                    
                    # Create Allergen object
                    allergen = Allergen(
                        name=allergen_name,
                        severity=severity,
                        source_ingredient=ingredient,
                        matched_keyword=matched_keyword
                    )
                    
                    detected_allergens.append(allergen)
                    
                    logger.debug(
                        f"Detected {allergen_name} (severity: {severity}) "
                        f"in ingredient: {ingredient}"
                    )
        
        # Sort by severity (high first, then medium, then low)
        severity_order = {"high": 0, "medium": 1, "low": 2}
        detected_allergens.sort(key=lambda a: severity_order.get(a.severity, 3))
        
        logger.info(f"Found {len(detected_allergens)} allergen(s)")
        
        return detected_allergens
    
    def check_ingredient_for_allergens(self, ingredient: str) -> List[str]:
        """
        Match a single ingredient against the allergen keyword database.
        
        Uses case-insensitive substring matching to detect allergen keywords
        within ingredient names. Handles compound ingredients and variations.
        
        Args:
            ingredient: Normalized ingredient string (lowercase, trimmed)
                Example: "almond milk", "peanut butter", "wheat flour"
                
        Returns:
            List[str]: List of allergen category names found in the ingredient.
                      Empty list if no allergens detected.
                      
        Example:
            allergens = detector.check_ingredient_for_allergens("almond milk")
            # Returns: ["tree_nuts", "milk"]
        """
        found_allergens = []
        
        # Check against each allergen category
        for allergen_name, keywords in self.allergen_keywords.items():
            # Check if any keyword appears in the ingredient
            for keyword in keywords:
                # Use word boundary matching to avoid false positives
                # Example: "wheat" should match "wheat flour" but not "buckwheat"
                pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
                
                if re.search(pattern, ingredient.lower()):
                    found_allergens.append(allergen_name)
                    # Only add allergen once even if multiple keywords match
                    break
        
        return found_allergens
    
    def get_allergen_severity(self, allergen: str) -> str:
        """
        Assign severity level to an allergen based on type.
        
        Severity is determined by:
        - Prevalence of severe reactions
        - Difficulty in avoiding the allergen
        - Cross-contamination risk
        
        Severity levels:
        - "high": Common, severe reactions, hard to avoid
        - "medium": Moderately common or severe
        - "low": Less common or typically milder reactions
        
        Args:
            allergen: Allergen category name (e.g., "peanuts", "milk")
            
        Returns:
            str: Severity level ("high", "medium", or "low")
            
        Example:
            severity = detector.get_allergen_severity("peanuts")
            # Returns: "high"
        """
        # Use predefined severity map from constants
        severity = self.severity_map.get(allergen, "medium")
        
        logger.debug(f"Allergen '{allergen}' assigned severity: {severity}")
        
        return severity
    
    def _find_matched_keyword(self, ingredient: str, allergen_name: str) -> str:
        """
        Find which specific keyword triggered an allergen match.
        
        Used for transparency and detailed reporting. Helps users understand
        exactly why an ingredient was flagged.
        
        Args:
            ingredient: Normalized ingredient string
            allergen_name: Name of the allergen category
            
        Returns:
            str: The keyword that matched, or empty string if not found
        """
        keywords = self.allergen_keywords.get(allergen_name, [])
        
        for keyword in keywords:
            pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
            if re.search(pattern, ingredient.lower()):
                return keyword
        
        return ""
    
    def build_allergen_response(
        self,
        allergens: List[str],
        ingredients: List[str]
    ) -> List[Dict]:
        """
        Format allergen data for API response.
        
        Takes raw allergen names and ingredients, creates full Allergen objects,
        and formats them into dictionaries suitable for JSON response.
        
        This method is useful when you have allergen names but need to
        reconstruct full allergen information with severity and sources.
        
        Args:
            allergens: List of allergen category names
            ingredients: List of recipe ingredients to match against
            
        Returns:
            List[Dict]: Formatted allergen warnings with structure:
                [
                    {
                        "name": str,
                        "severity": str,
                        "source_ingredient": str,
                        "matched_keyword": str
                    }
                ]
                
        Example:
            response = detector.build_allergen_response(
                ["milk", "wheat"],
                ["whole milk", "wheat flour", "sugar"]
            )
        """
        logger.info(
            f"Building allergen response for {len(allergens)} allergen(s) "
            f"and {len(ingredients)} ingredient(s)"
        )
        
        # Detect allergens with full details
        allergen_objects = self.detect_allergens(ingredients)
        
        # Filter to only requested allergen categories if specified
        if allergens:
            allergen_set = set(allergens)
            allergen_objects = [
                a for a in allergen_objects
                if a.name in allergen_set
            ]
        
        # Convert to dictionary format
        response = [allergen.to_dict() for allergen in allergen_objects]
        
        logger.info(f"Built response with {len(response)} allergen warning(s)")
        
        return response
    
    def get_allergen_description(self, allergen_name: str) -> str:
        """
        Get a human-readable description of an allergen.
        
        Provides context about the allergen for user education.
        
        Args:
            allergen_name: Allergen category name
            
        Returns:
            str: Description of the allergen
        """
        descriptions = {
            "milk": "Dairy products including milk, cream, butter, cheese, and yogurt. "
                   "One of the most common food allergies, especially in children.",
            
            "eggs": "Chicken eggs and egg-containing products. May be present in "
                   "baked goods, mayonnaise, and some pasta.",
            
            "peanuts": "Peanuts and peanut-derived products. Can cause severe, "
                      "life-threatening reactions. Not the same as tree nuts.",
            
            "tree_nuts": "Includes almonds, walnuts, cashews, pecans, pistachios, "
                        "and other tree nuts. Different from peanuts.",
            
            "soy": "Soybeans and soy-derived products including tofu, soy sauce, "
                  "and many processed foods.",
            
            "wheat": "Wheat and wheat-containing products. Note: This is different "
                    "from gluten sensitivity or celiac disease.",
            
            "fish": "Fish and fish-derived products. Does not include shellfish, "
                   "which is a separate allergen category.",
            
            "shellfish": "Includes crustaceans (shrimp, crab, lobster) and mollusks "
                        "(clams, oysters, squid). Different from fish allergy."
        }
        
        return descriptions.get(allergen_name, f"Allergen: {allergen_name}")
    
    def check_cross_contamination_risk(
        self,
        ingredients: List[str],
        known_allergens: List[str]
    ) -> List[Dict]:
        """
        Check for potential cross-contamination risks (simplified MVP version).
        
        In a production system, this would check for:
        - Shared processing facilities
        - Similar ingredient families
        - Common cross-contact scenarios
        
        For MVP, we use simple keyword matching for obvious risks.
        
        Args:
            ingredients: List of recipe ingredients
            known_allergens: List of allergen names to check for
            
        Returns:
            List[Dict]: List of potential cross-contamination warnings
        """
        logger.info("Checking for cross-contamination risks (simplified)")
        
        risks = []
        
        # Simple cross-contamination patterns
        cross_contamination_keywords = {
            "may contain": ["may contain", "processed in", "manufactured in"],
            "shared equipment": ["shared equipment", "shared facility"],
        }
        
        for ingredient in ingredients:
            normalized = normalize_ingredient_name(ingredient)
            
            for risk_type, keywords in cross_contamination_keywords.items():
                for keyword in keywords:
                    if keyword in normalized.lower():
                        risks.append({
                            "type": "cross_contamination",
                            "risk_level": "medium",
                            "source": ingredient,
                            "description": f"Ingredient mentions '{keyword}' which may "
                                         f"indicate cross-contamination risk"
                        })
        
        logger.info(f"Found {len(risks)} potential cross-contamination risk(s)")
        
        return risks
    
    def get_allergen_alternatives(self, allergen_name: str) -> List[str]:
        """
        Get common allergen-free alternatives for cooking.
        
        Provides suggestions for ingredient substitutions to avoid allergens.
        Useful for the ingredient swap workflow.
        
        Args:
            allergen_name: Name of allergen to find alternatives for
            
        Returns:
            List[str]: List of allergen-free alternative ingredients
        """
        alternatives = {
            "milk": [
                "almond milk",
                "oat milk",
                "coconut milk",
                "soy milk (if not allergic to soy)",
                "rice milk"
            ],
            "eggs": [
                "flax eggs (1 tbsp ground flax + 3 tbsp water)",
                "chia eggs",
                "applesauce (for baking)",
                "mashed banana (for baking)",
                "commercial egg replacer"
            ],
            "peanuts": [
                "sunflower seed butter",
                "tahini (sesame paste)",
                "soy nut butter (if not allergic to soy)"
            ],
            "tree_nuts": [
                "sunflower seeds",
                "pumpkin seeds",
                "sesame seeds"
            ],
            "soy": [
                "coconut aminos (instead of soy sauce)",
                "coconut milk (instead of soy milk)",
                "other plant-based milks"
            ],
            "wheat": [
                "rice flour",
                "almond flour",
                "oat flour",
                "cornstarch",
                "gluten-free flour blend"
            ],
            "fish": [
                "tofu (for texture)",
                "seaweed (for umami flavor)",
                "mushrooms (for umami)"
            ],
            "shellfish": [
                "fish (if not allergic)",
                "tofu",
                "mushrooms (for texture)"
            ]
        }
        
        return alternatives.get(allergen_name, [])
    
    def get_statistics(self) -> Dict:
        """
        Get statistics about the allergen detection system.
        
        Useful for monitoring and reporting.
        
        Returns:
            Dict: Statistics about allergen categories and keywords
        """
        total_keywords = sum(len(keywords) for keywords in self.allergen_keywords.values())
        
        severity_counts = {
            "high": 0,
            "medium": 0,
            "low": 0
        }
        
        for allergen in self.allergen_keywords.keys():
            severity = self.get_allergen_severity(allergen)
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        return {
            "total_allergen_categories": len(self.allergen_keywords),
            "total_keywords": total_keywords,
            "severity_distribution": severity_counts,
            "categories": list(self.allergen_keywords.keys())
        }