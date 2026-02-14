"""
Pydantic models for ingredient swaps.

This module defines data models for ingredient substitution workflow
(Workflow 2), including risky ingredients, substitutes, and swap requests.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict

from app.models.recipe import RecipeBasic
from app.models.health_score import HealthScore
from app.models.nutrition import NutritionData


class RiskyIngredient(BaseModel):
    """
    Model for a risky or unhealthy ingredient.
    
    Represents an ingredient flagged for potential substitution.
    
    Attributes:
        name: Ingredient name
        reason: Explanation of health risk
        priority: Swap priority (1-5, where 5 is highest)
        category: Ingredient category (e.g., "oil", "sweetener")
        health_impact: Estimated negative health impact score
        alternatives_available: Whether substitutes exist
    """
    name: str = Field(..., description="Ingredient name")
    reason: str = Field(..., description="Health risk explanation")
    priority: int = Field(..., ge=1, le=5, description="Swap priority (1-5)")
    category: Optional[str] = Field(None, description="Ingredient category")
    health_impact: Optional[float] = Field(
        None,
        ge=0.0,
        le=10.0,
        description="Health impact score (0-10)"
    )
    alternatives_available: bool = Field(
        True,
        description="Whether healthy substitutes exist"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "butter",
                "reason": "High saturated fat content",
                "priority": 4,
                "category": "oil",
                "health_impact": 6.5,
                "alternatives_available": True
            }
        }
    }


class SubstituteOption(BaseModel):
    """
    Model for an ingredient substitute option.
    
    Represents a healthier alternative ingredient with flavor and
    health metrics.
    
    Attributes:
        name: Substitute ingredient name
        flavor_match: Flavor similarity to original (0-100)
        health_improvement: Expected health score gain
        category: Ingredient category
        rank_score: Combined ranking score
        explanation: Optional explanation for substitution
    """
    name: str = Field(..., description="Substitute ingredient name")
    flavor_match: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Flavor similarity percentage (0-100)"
    )
    health_improvement: float = Field(
        ...,
        ge=0.0,
        description="Expected health score improvement"
    )
    category: Optional[str] = Field(None, description="Ingredient category")
    rank_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=100.0,
        description="Combined ranking score"
    )
    explanation: Optional[str] = Field(
        None,
        description="Substitution explanation"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "olive oil",
                "flavor_match": 72.5,
                "health_improvement": 8.3,
                "category": "oil",
                "rank_score": 71.82,
                "explanation": "Replace butter with olive oil (similar flavor, significantly healthier)"
            }
        }
    }


class Swap(BaseModel):
    """
    Model for a single ingredient swap.
    
    Represents a proposed substitution of one ingredient for another.
    
    Attributes:
        original: Original ingredient name
        substitute: Substitute option
        accepted: Whether user has accepted this swap
    """
    original: str = Field(..., description="Original ingredient name")
    substitute: SubstituteOption = Field(..., description="Substitute option")
    accepted: bool = Field(False, description="Whether swap is accepted")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "original": "butter",
                "substitute": {
                    "name": "olive oil",
                    "flavor_match": 72.5,
                    "health_improvement": 8.3
                },
                "accepted": False
            }
        }
    }


class IngredientSwapRequest(BaseModel):
    """
    Request model for ingredient swap endpoint (Workflow 2).
    
    Attributes:
        recipe_id: Recipe identifier
        ingredients_to_swap: Optional list of specific ingredients to swap
                            (if None, auto-detect risky ingredients)
    """
    recipe_id: str = Field(..., description="Recipe identifier")
    ingredients_to_swap: Optional[List[str]] = Field(
        None,
        description="Specific ingredients to swap (None for auto-detect)"
    )
    
    @field_validator('ingredients_to_swap')
    @classmethod
    def validate_ingredients_list(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Ensure ingredients list is not empty if provided."""
        if v is not None and len(v) == 0:
            raise ValueError('ingredients_to_swap cannot be an empty list')
        return v
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "recipe_id": "12345",
                "ingredients_to_swap": ["butter", "white sugar"]
            }
        }
    }


class IngredientSwapResponse(BaseModel):
    """
    Response model for ingredient swap endpoint (Workflow 2).
    
    Contains swap suggestions, health scores, and optional explanation.
    
    Attributes:
        recipe: Basic recipe information
        risky_ingredients: Identified risky ingredients
        swaps: Proposed ingredient swaps
        original_score: Original health score
        projected_score: Projected score with swaps applied
        explanation: Optional LLM-generated explanation
        workflow: Workflow identifier
    """
    recipe: RecipeBasic = Field(..., description="Recipe information")
    risky_ingredients: List[RiskyIngredient] = Field(
        ...,
        description="Identified risky ingredients"
    )
    swaps: List[Swap] = Field(..., description="Proposed swaps")
    original_score: HealthScore = Field(..., description="Original health score")
    projected_score: HealthScore = Field(..., description="Projected health score")
    explanation: Optional[str] = Field(
        None,
        description="Optional explanation"
    )
    workflow: str = Field(
        default="ingredient_swap",
        description="Workflow identifier"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "recipe": {
                    "id": "12345",
                    "name": "Chocolate Chip Cookies",
                    "ingredients": ["butter", "white sugar", "flour"]
                },
                "risky_ingredients": [
                    {
                        "name": "butter",
                        "reason": "High saturated fat",
                        "priority": 4
                    }
                ],
                "swaps": [
                    {
                        "original": "butter",
                        "substitute": {
                            "name": "olive oil",
                            "flavor_match": 72.5,
                            "health_improvement": 8.3
                        },
                        "accepted": False
                    }
                ],
                "original_score": {"score": 45.0, "rating": "Decent"},
                "projected_score": {"score": 68.0, "rating": "Good"},
                "workflow": "ingredient_swap"
            }
        }
    }


class RecalculateRequest(BaseModel):
    """
    Request model for score recalculation endpoint.

    Used when user accepts specific swaps and wants updated score.

    Attributes:
        recipe_name: Recipe name
        original_ingredients: List of original ingredients
        accepted_swaps: Mapping of original ingredient to accepted substitute
        allergens: Optional list of allergens user is sensitive to
        avoid_ingredients: Optional list of ingredients to avoid
    """
    recipe_name: str = Field(..., description="Recipe name")
    original_ingredients: List[str] = Field(..., description="Original ingredient list")
    accepted_swaps: Dict[str, str] = Field(
        ...,
        description="Mapping of original ingredient to accepted substitute"
    )
    allergens: Optional[List[str]] = Field(None, description="User allergens")
    avoid_ingredients: Optional[List[str]] = Field(None, description="Ingredients to avoid")

    model_config = {
        "json_schema_extra": {
            "example": {
                "recipe_name": "Chocolate Chip Cookies",
                "original_ingredients": ["butter", "white sugar", "flour"],
                "accepted_swaps": {"butter": "olive oil", "white sugar": "honey"},
                "allergens": ["milk"],
                "avoid_ingredients": None
            }
        }
    }


class RecalculateResponse(BaseModel):
    """
    Response model for score recalculation endpoint.

    Contains updated health score and nutrition data after applying
    accepted swaps.

    Attributes:
        recipe_name: Recipe name
        final_ingredients: Modified ingredient list after swaps
        final_health_score: Recalculated health score
        nutrition: Updated nutrition data
        micro_nutrition: Updated micronutrient data
        detected_allergens: Allergens detected in final ingredient list
        user_allergen_warnings: User allergen warnings
        flagged_avoid_ingredients: Ingredients that match user avoidance list
        total_score_improvement: Points of improvement from original score
        explanation: Explanation of the improvements
    """
    recipe_name: str = Field(..., description="Recipe name")
    final_ingredients: List[str] = Field(..., description="Modified ingredient list")
    final_health_score: HealthScore = Field(..., description="Recalculated health score")
    nutrition: Dict = Field(..., description="Updated nutrition data")
    micro_nutrition: Dict = Field(..., description="Updated micronutrient data")
    detected_allergens: List[Dict] = Field(
        default_factory=list,
        description="Detected allergens in final ingredients"
    )
    user_allergen_warnings: List[Dict] = Field(
        default_factory=list,
        description="User allergen warnings"
    )
    flagged_avoid_ingredients: List[str] = Field(
        default_factory=list,
        description="Flagged avoid ingredients"
    )
    total_score_improvement: float = Field(
        ...,
        description="Score improvement from original"
    )
    explanation: Optional[str] = Field(
        None,
        description="Explanation of improvements"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "recipe_name": "Chocolate Chip Cookies",
                "final_ingredients": ["olive oil", "honey", "flour", "eggs"],
                "final_health_score": {
                    "score": 68.0,
                    "rating": "Good",
                    "breakdown": {}
                },
                "nutrition": {
                    "calories": 320.0,
                    "protein": 25.0,
                    "saturated_fat": 3.5
                },
                "micro_nutrition": {
                    "vitamins": {},
                    "minerals": {}
                },
                "detected_allergens": [],
                "user_allergen_warnings": [],
                "flagged_avoid_ingredients": [],
                "total_score_improvement": 8.5,
                "explanation": "Swaps improved your recipe..."
            }
        }
    }