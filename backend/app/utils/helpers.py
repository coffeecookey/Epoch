"""
Common utility helper functions.

This module provides reusable utility functions for calculations,
formatting, and data manipulation used throughout the application.
"""

import re
import logging
from typing import Dict, List, Optional

from app.utils.constants import INGREDIENT_CATEGORY_KEYWORDS

# Configure logging
logger = logging.getLogger(__name__)


def calculate_percentage_of_calories(
    nutrient_grams: float,
    nutrient_type: str,
    total_calories: float
) -> float:
    """
    Convert nutrient grams to percentage of total calories.
    
    Uses standard calorie conversion factors:
    - Protein: 4 calories per gram
    - Carbohydrates: 4 calories per gram
    - Fat: 9 calories per gram
    
    Args:
        nutrient_grams: Amount of nutrient in grams
        nutrient_type: Type of nutrient ("protein", "carbs", "fat")
        total_calories: Total calories in the recipe
        
    Returns:
        float: Percentage of calories from this nutrient (0-100)
        
    Raises:
        ValueError: If nutrient_type is invalid or total_calories is zero
        
    Example:
        >>> calculate_percentage_of_calories(25, "protein", 400)
        25.0  # (25g * 4 cal/g) / 400 cal * 100 = 25%
    """
    if total_calories <= 0:
        raise ValueError("Total calories must be greater than zero")
    
    # Calories per gram for each macronutrient
    calorie_factors = {
        "protein": 4.0,
        "carbs": 4.0,
        "carbohydrates": 4.0,
        "fat": 9.0
    }
    
    nutrient_type_lower = nutrient_type.lower()
    
    if nutrient_type_lower not in calorie_factors:
        raise ValueError(
            f"Invalid nutrient type: {nutrient_type}. "
            f"Must be one of: {list(calorie_factors.keys())}"
        )
    
    # Calculate calories from this nutrient
    nutrient_calories = nutrient_grams * calorie_factors[nutrient_type_lower]
    
    # Calculate percentage
    percentage = (nutrient_calories / total_calories) * 100
    
    return round(percentage, 2)


def categorize_ingredient(ingredient: str) -> str:
    """
    Determine ingredient category based on name.
    
    Uses keyword matching to classify ingredients into predefined categories.
    Returns "other" if no category match is found.
    
    Args:
        ingredient: Ingredient name (normalized or raw)
        
    Returns:
        str: Category name (oil/sweetener/dairy/grain/protein/vegetable/
             fruit/spice/condiment/other)
             
    Example:
        >>> categorize_ingredient("olive oil")
        "oil"
        >>> categorize_ingredient("chicken breast")
        "protein"
    """
    ingredient_lower = ingredient.lower()
    
    # Check each category's keywords
    for category, keywords in INGREDIENT_CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in ingredient_lower:
                logger.debug(
                    f"Categorized '{ingredient}' as '{category}' "
                    f"(matched keyword: '{keyword}')"
                )
                return category
    
    # Default category
    logger.debug(f"Categorized '{ingredient}' as 'other' (no keyword match)")
    return "other"


def normalize_ingredient_name(ingredient: str) -> str:
    """
    Standardize ingredient names for consistent matching.
    
    Performs the following normalization:
    1. Convert to lowercase
    2. Remove leading/trailing whitespace
    3. Remove quantity indicators (numbers, measurements)
    4. Remove common prefixes (chopped, diced, fresh, etc.)
    5. Collapse multiple spaces
    6. Remove special characters except hyphens and spaces
    
    Args:
        ingredient: Raw ingredient string
        
    Returns:
        str: Normalized ingredient name
        
    Example:
        >>> normalize_ingredient_name("2 cups Fresh Chopped Tomatoes")
        "tomatoes"
        >>> normalize_ingredient_name("1/2 lb. ground beef (85% lean)")
        "ground beef"
    """
    if not ingredient:
        return ""
    
    # Convert to lowercase
    normalized = ingredient.lower()
    
    # Remove parenthetical content
    normalized = re.sub(r'\([^)]*\)', '', normalized)
    
    # Remove common quantity patterns
    # Matches: "1 cup", "2.5 oz", "1/2 tbsp", etc.
    normalized = re.sub(
        r'\b\d+\.?\d*\s*(?:\/\s*\d+)?\s*(?:cup|cups|tablespoon|tablespoons|'
        r'tbsp|teaspoon|teaspoons|tsp|ounce|ounces|oz|pound|pounds|lb|lbs|'
        r'gram|grams|g|kilogram|kilograms|kg|milliliter|milliliters|ml|'
        r'liter|liters|l|pinch|dash|can|cans|package|packages|pkg)\b',
        '',
        normalized
    )
    
    # Remove standalone numbers
    normalized = re.sub(r'\b\d+\.?\d*\s*(?:\/\s*\d+)?\b', '', normalized)
    
    # Remove common preparation descriptors
    prep_words = [
        'fresh', 'frozen', 'dried', 'canned', 'chopped', 'diced', 'minced',
        'sliced', 'grated', 'shredded', 'ground', 'whole', 'raw', 'cooked',
        'large', 'small', 'medium', 'ripe', 'boneless', 'skinless',
        'organic', 'extra virgin', 'unsalted', 'salted', 'plain'
    ]
    
    for word in prep_words:
        normalized = re.sub(r'\b' + word + r'\b', '', normalized)
    
    # Remove special characters except hyphens and spaces
    normalized = re.sub(r'[^a-z\s-]', '', normalized)
    
    # Collapse multiple spaces and hyphens
    normalized = re.sub(r'\s+', ' ', normalized)
    normalized = re.sub(r'-+', '-', normalized)
    
    # Strip leading/trailing whitespace and hyphens
    normalized = normalized.strip(' -')
    
    logger.debug(f"Normalized '{ingredient}' -> '{normalized}'")
    
    return normalized


def format_nutrition_value(value: float, unit: str) -> str:
    """
    Format nutrition value for display.
    
    Args:
        value: Numeric nutrition value
        unit: Unit of measurement (g, mg, mcg, etc.)
        
    Returns:
        str: Formatted string (e.g., "25.5g", "450mg")
    """
    if value == 0:
        return f"0{unit}"
    
    # Round to appropriate decimal places
    if value >= 100:
        formatted_value = f"{value:.0f}"
    elif value >= 10:
        formatted_value = f"{value:.1f}"
    else:
        formatted_value = f"{value:.2f}"
    
    return f"{formatted_value}{unit}"


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to maximum length with suffix.
    
    Args:
        text: Text to truncate
        max_length: Maximum length including suffix
        suffix: Suffix to append if truncated (default: "...")
        
    Returns:
        str: Truncated text
    """
    if not text or len(text) <= max_length:
        return text
    
    truncate_at = max_length - len(suffix)
    return text[:truncate_at].rstrip() + suffix


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Safely divide two numbers, returning default if denominator is zero.
    
    Args:
        numerator: Numerator value
        denominator: Denominator value
        default: Default value to return if division by zero (default: 0.0)
        
    Returns:
        float: Result of division or default value
    """
    if denominator == 0:
        return default
    return numerator / denominator


# Ingredient-to-nutrition heuristics for fallback estimation (per serving)
_ESTIMATE_SUGAR_KEYWORDS = [
    "sugar", "honey", "syrup", "molasses", "maple", "corn syrup",
    "dextrose", "fructose", "sweetener", "chocolate", "cocoa"
]
_ESTIMATE_SODIUM_KEYWORDS = [
    "salt", "soy sauce", "fish sauce", "bouillon", "broth", "stock",
    "bacon", "ham", "sausage", "pickle", "capers", "anchovy"
]
_ESTIMATE_SAT_FAT_KEYWORDS = [
    "butter", "cream", "cheese", "bacon", "lard", "shortening",
    "coconut milk", "coconut cream", "sour cream"
]
_ESTIMATE_PROTEIN_KEYWORDS = [
    "chicken", "beef", "pork", "lamb", "fish", "shrimp", "tofu",
    "egg", "lentil", "bean", "chickpea", "quinoa", "tempeh"
]
_ESTIMATE_FIBER_KEYWORDS = [
    "oat", "bran", "whole wheat", "whole grain", "quinoa", "barley",
    "broccoli", "spinach", "kale", "carrot", "bean", "lentil",
    "chickpea", "apple", "berry", "avocado"
]
_ESTIMATE_TRANS_FAT_KEYWORDS = [
    "shortening", "margarine", "hydrogenated", "partially hydrogenated"
]


def estimate_nutrition_from_ingredients(ingredients: List[str]) -> Dict[str, float]:
    """
    Estimate nutrition per serving from ingredient names when RecipeDB is unavailable.

    Uses keyword matching to detect sugar, sodium, saturated fat, protein, fiber,
    and trans fat. Produces varied scores so health score is not always 60.

    Args:
        ingredients: List of ingredient strings

    Returns:
        Dict with keys: calories, protein, carbs, fat, saturated_fat, trans_fat,
        sodium, sugar, cholesterol, fiber
    """
    if not ingredients:
        return {
            "calories": 200.0, "protein": 8.0, "carbs": 25.0, "fat": 8.0,
            "saturated_fat": 2.0, "trans_fat": 0.0, "sodium": 200.0,
            "sugar": 5.0, "cholesterol": 20.0, "fiber": 2.0,
        }

    all_text = " ".join(i.lower() for i in ingredients)
    n = max(1, len(ingredients))

    # Base per serving (moderate recipe)
    base_cal = 200 + 40 * n
    protein = 12.0
    carbs = 25.0
    fat = 8.0
    saturated_fat = 2.5
    trans_fat = 0.0
    sodium = 200.0
    sugar = 6.0
    fiber = 3.0

    # Accumulate contributions from detected ingredients (drives score differentiation)
    sugar_count = sum(1 for kw in _ESTIMATE_SUGAR_KEYWORDS if kw in all_text)
    if sugar_count:
        sugar += 20 * sugar_count  # Push over 25g threshold → penalty
        carbs += 10 * sugar_count

    sodium_count = sum(1 for kw in _ESTIMATE_SODIUM_KEYWORDS if kw in all_text)
    if sodium_count:
        sodium += 300 * sodium_count  # Push over 400mg → penalty

    sat_fat_count = sum(1 for kw in _ESTIMATE_SAT_FAT_KEYWORDS if kw in all_text)
    if sat_fat_count:
        saturated_fat += 8 * sat_fat_count  # Push over 10g → penalty
        fat += 10 * sat_fat_count

    protein_count = sum(1 for kw in _ESTIMATE_PROTEIN_KEYWORDS if kw in all_text)
    if protein_count:
        protein += 10 * protein_count  # Improves macro balance

    fiber_count = sum(1 for kw in _ESTIMATE_FIBER_KEYWORDS if kw in all_text)
    if fiber_count:
        fiber += 5 * fiber_count  # Bonus points

    trans_count = sum(1 for kw in _ESTIMATE_TRANS_FAT_KEYWORDS if kw in all_text)
    if trans_count:
        trans_fat += 1.0 * trans_count  # Severe penalty

    return {
        "calories": min(base_cal, 600.0),
        "protein": min(protein, 50.0),
        "carbs": min(carbs, 80.0),
        "fat": min(fat, 45.0),
        "saturated_fat": min(saturated_fat, 25.0),
        "trans_fat": trans_fat,
        "sodium": min(sodium, 2000.0),
        "sugar": min(sugar, 70.0),
        "cholesterol": 80.0 if any(k in all_text for k in ["egg", "butter", "cream"]) else 30.0,
        "fiber": min(fiber, 15.0),
    }