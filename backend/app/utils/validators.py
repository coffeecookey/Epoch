"""
Input validation utilities.

This module provides validation functions for user input to ensure
data integrity and security throughout the application.
"""

import re
import logging
from typing import List

# Configure logging
logger = logging.getLogger(__name__)


def validate_recipe_name(name: str) -> bool:
    """
    Validate recipe name input.
    
    Ensures recipe name:
    - Is not empty or whitespace only
    - Does not exceed maximum length
    - Does not contain dangerous characters
    - Contains only allowed characters
    
    Args:
        name: Recipe name string
        
    Returns:
        bool: True if valid
        
    Raises:
        ValueError: If validation fails with specific error message
    """
    # Check for empty or whitespace
    if not name or not name.strip():
        raise ValueError("Recipe name cannot be empty")
    
    # Check length
    if len(name) > 200:
        raise ValueError("Recipe name cannot exceed 200 characters")
    
    if len(name) < 2:
        raise ValueError("Recipe name must be at least 2 characters")
    
    # Check for dangerous characters (basic sanitization)
    dangerous_patterns = [
        r'<script',  # Script tags
        r'javascript:',  # JavaScript protocol
        r'on\w+\s*=',  # Event handlers (onclick, onload, etc)
        r'\.\./',  # Path traversal
        r'[<>]'  # HTML tags
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, name, re.IGNORECASE):
            raise ValueError(
                f"Recipe name contains invalid characters or patterns"
            )
    
    logger.debug(f"Recipe name validated: {name}")
    return True


def validate_ingredient_list(ingredients: List[str]) -> bool:
    """
    Validate ingredient list.
    
    Ensures ingredient list:
    - Is not empty
    - Each ingredient is valid string
    - No ingredient is excessively long
    - Total number is reasonable
    
    Args:
        ingredients: List of ingredient strings
        
    Returns:
        bool: True if valid
        
    Raises:
        ValueError: If validation fails with specific error message
    """
    # Check for empty list
    if not ingredients or len(ingredients) == 0:
        raise ValueError("Ingredient list cannot be empty")
    
    # Check maximum number of ingredients
    if len(ingredients) > 100:
        raise ValueError(
            "Ingredient list cannot exceed 100 items "
            "(got {})".format(len(ingredients))
        )
    
    # Validate each ingredient
    for i, ingredient in enumerate(ingredients):
        # Check type
        if not isinstance(ingredient, str):
            raise ValueError(
                f"Ingredient at index {i} must be a string, "
                f"got {type(ingredient).__name__}"
            )
        
        # Check for empty strings
        if not ingredient.strip():
            raise ValueError(f"Ingredient at index {i} cannot be empty")
        
        # Check length
        if len(ingredient) > 500:
            raise ValueError(
                f"Ingredient at index {i} exceeds maximum length of 500 characters"
            )
        
        # Check for dangerous characters
        dangerous_patterns = [
            r'<script',
            r'javascript:',
            r'on\w+\s*='
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, ingredient, re.IGNORECASE):
                raise ValueError(
                    f"Ingredient at index {i} contains invalid characters"
                )
    
    logger.debug(f"Ingredient list validated: {len(ingredients)} ingredients")
    return True


def sanitize_input(text: str) -> str:
    """
    Remove dangerous characters from user input.
    
    Strips potentially harmful content while preserving
    legitimate input for recipe names and ingredients.
    
    Args:
        text: Raw user input string
        
    Returns:
        str: Sanitized string
    """
    if not text:
        return ""
    
    # Remove leading/trailing whitespace
    sanitized = text.strip()
    
    # Remove null bytes
    sanitized = sanitized.replace('\0', '')
    
    # Remove control characters except newlines and tabs
    sanitized = ''.join(
        char for char in sanitized
        if ord(char) >= 32 or char in '\n\t'
    )
    
    # Remove excessive whitespace
    sanitized = re.sub(r'\s+', ' ', sanitized)
    
    # Remove HTML/XML tags
    sanitized = re.sub(r'<[^>]+>', '', sanitized)
    
    # Remove script-related content
    sanitized = re.sub(r'javascript:', '', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'on\w+\s*=', '', sanitized, flags=re.IGNORECASE)
    
    logger.debug("Input sanitized")
    return sanitized


def validate_recipe_id(recipe_id: str) -> bool:
    """
    Validate recipe ID format.
    
    Ensures recipe ID is a valid identifier without dangerous characters.
    
    Args:
        recipe_id: Recipe identifier string
        
    Returns:
        bool: True if valid
        
    Raises:
        ValueError: If validation fails
    """
    if not recipe_id or not recipe_id.strip():
        raise ValueError("Recipe ID cannot be empty")
    
    if len(recipe_id) > 100:
        raise ValueError("Recipe ID cannot exceed 100 characters")
    
    # Allow alphanumeric, hyphens, and underscores only
    if not re.match(r'^[a-zA-Z0-9_-]+$', recipe_id):
        raise ValueError(
            "Recipe ID must contain only alphanumeric characters, "
            "hyphens, and underscores"
        )
    
    return True


def validate_score_range(score: float, min_val: float = 0.0, max_val: float = 100.0) -> bool:
    """
    Validate score is within acceptable range.
    
    Args:
        score: Score value to validate
        min_val: Minimum acceptable value (default: 0.0)
        max_val: Maximum acceptable value (default: 100.0)
        
    Returns:
        bool: True if valid
        
    Raises:
        ValueError: If score is out of range
    """
    if not isinstance(score, (int, float)):
        raise ValueError(f"Score must be a number, got {type(score).__name__}")
    
    if score < min_val or score > max_val:
        raise ValueError(
            f"Score must be between {min_val} and {max_val}, got {score}"
        )
    
    return True