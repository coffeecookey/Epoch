"""
Pydantic models for health scoring.

This module defines data models for health score calculations and
recipe analysis responses.
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Dict, List, Optional

from app.models.recipe import RecipeBasic, RecipeRecommendation
from app.models.nutrition import NutritionData


class HealthScore(BaseModel):
    """
    Health score model.
    
    Represents the calculated health score for a recipe with detailed
    breakdown of component scores.
    
    Attributes:
        score: Overall health score (0-100)
        rating: Categorical rating (Excellent/Good/Decent/Bad/Poor)
        breakdown: Detailed breakdown of score components
    """
    score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Overall health score (0-100)"
    )
    rating: str = Field(
        ...,
        description="Health rating category"
    )
    breakdown: Dict = Field(
        default_factory=dict,
        description="Detailed score breakdown"
    )
    
    @field_validator('rating')
    @classmethod
    def validate_rating(cls, v: str) -> str:
        """Ensure rating is one of the valid categories."""
        valid_ratings = ["Excellent", "Good", "Decent", "Bad", "Poor"]
        if v not in valid_ratings:
            raise ValueError(f'Rating must be one of: {", ".join(valid_ratings)}')
        return v
    
    @model_validator(mode='after')
    def validate_score_rating_consistency(self):
        """Ensure score and rating are consistent."""
        score = self.score
        rating = self.rating
        
        # Check consistency
        if score >= 80 and rating != "Excellent":
            raise ValueError(f'Score {score} should have rating "Excellent", got "{rating}"')
        elif 60 <= score < 80 and rating != "Good":
            raise ValueError(f'Score {score} should have rating "Good", got "{rating}"')
        elif 40 <= score < 60 and rating != "Decent":
            raise ValueError(f'Score {score} should have rating "Decent", got "{rating}"')
        elif 20 <= score < 40 and rating != "Bad":
            raise ValueError(f'Score {score} should have rating "Bad", got "{rating}"')
        elif score < 20 and rating != "Poor":
            raise ValueError(f'Score {score} should have rating "Poor", got "{rating}"')
        
        return self
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "score": 75.5,
                "rating": "Good",
                "breakdown": {
                    "macronutrient_score": 32.0,
                    "micronutrient_score": 24.0,
                    "negative_factors_penalty": -8.0,
                    "raw_total": 48.0,
                    "normalized_score": 75.5
                }
            }
        }
    }


class RecipeAnalysisResponse(BaseModel):
    """
    Response model for recipe health analysis (Workflow 1).
    
    Contains complete analysis results including nutrition data,
    health score, allergen warnings, and recommendations (if applicable).
    
    Attributes:
        recipe: Basic recipe information
        nutrition: Complete nutrition data
        micro_nutrition: Micronutrient data
        health_score: Calculated health score
        allergens: List of detected allergens
        recommendations: Similar healthy recipes (if score >= 60 and no allergens)
        workflow: Workflow identifier
        explanation: Optional LLM-generated explanation
    """
    recipe: RecipeBasic = Field(..., description="Recipe information")
    nutrition: Dict = Field(..., description="Macronutrient data")
    micro_nutrition: Dict = Field(..., description="Micronutrient data")
    health_score: HealthScore = Field(..., description="Health score data")
    allergens: List[Dict] = Field(
        default_factory=list,
        description="Detected allergens"
    )
    recommendations: Optional[List[RecipeRecommendation]] = Field(
        None,
        description="Similar healthy recipe recommendations"
    )
    workflow: str = Field(
        ...,
        description="Workflow type identifier"
    )
    explanation: Optional[str] = Field(
        None,
        description="Optional LLM-generated explanation"
    )
    
    @field_validator('workflow')
    @classmethod
    def validate_workflow(cls, v: str) -> str:
        """Ensure workflow is valid."""
        valid_workflows = ["healthy_recommendation", "needs_improvement"]
        if v not in valid_workflows:
            raise ValueError(f'Workflow must be one of: {", ".join(valid_workflows)}')
        return v
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "recipe": {
                    "id": "12345",
                    "name": "Chicken Curry",
                    "cuisine": "Indian",
                    "diet_type": "non-vegetarian",
                    "ingredients": ["chicken", "curry powder", "onion"]
                },
                "nutrition": {
                    "calories": 350.0,
                    "protein": 25.0,
                    "carbs": 30.0,
                    "fat": 15.0
                },
                "micro_nutrition": {
                    "vitamins": {"vitamin_c": 25.0},
                    "minerals": {"iron": 5.0}
                },
                "health_score": {
                    "score": 75.5,
                    "rating": "Good",
                    "breakdown": {}
                },
                "allergens": [],
                "recommendations": [],
                "workflow": "healthy_recommendation",
                "explanation": "This recipe has a Good health rating..."
            }
        }
    }


class FullAnalysisResponse(BaseModel):
    """
    Response model for the unified analysis endpoint (/analyze-full).

    Contains the complete pipeline results: original risk profile,
    allergen warnings, similar recipe search, swap suggestions,
    and improved risk profile with before/after comparison.
    """
    # Recipe info
    recipe_name: str = Field(..., description="Recipe name")
    ingredients: List[str] = Field(..., description="Ingredients used for analysis")
    source: str = Field(
        ...,
        description="Where recipe data came from: 'recipedb' or 'custom'"
    )

    # Original risk profile
    original_health_score: HealthScore = Field(..., description="Original health score")
    nutrition: Optional[Dict] = Field(None, description="Macronutrient data")
    micro_nutrition: Optional[Dict] = Field(None, description="Micronutrient data")

    # Allergens
    detected_allergens: List[Dict] = Field(
        default_factory=list,
        description="Allergens detected in ingredients"
    )
    user_allergen_warnings: List[Dict] = Field(
        default_factory=list,
        description="Ingredients that match user-declared allergen sensitivities"
    )

    # Avoidance
    flagged_avoid_ingredients: List[str] = Field(
        default_factory=list,
        description="Ingredients the user wanted to avoid that are present in the recipe"
    )

    # Similar recipe from RecipeDB
    similar_recipe: Optional[Dict] = Field(
        None,
        description="Similar recipe found in RecipeDB (if any)"
    )

    # Ingredient analysis and swaps
    risky_ingredients: List[Dict] = Field(
        default_factory=list,
        description="Unhealthy ingredients identified for swapping"
    )
    swap_suggestions: List[Dict] = Field(
        default_factory=list,
        description="Suggested ingredient swaps with flavor and health scores"
    )

    # Improved risk profile
    improved_health_score: Optional[HealthScore] = Field(
        None,
        description="Projected health score after applying all swaps"
    )
    improved_ingredients: Optional[List[str]] = Field(
        None,
        description="Ingredient list after swaps applied"
    )

    # Comparison
    score_improvement: Optional[float] = Field(
        None,
        description="Points of health score improvement (improved - original)"
    )

    # Explanation
    explanation: Optional[str] = Field(
        None,
        description="Template-based explanation of the analysis"
    )

    # LLM agent metadata (only present when USE_LLM_AGENT=True)
    agent_metadata: Optional[Dict] = Field(
        None,
        description="LLM swap agent metadata (confidence, APIs called, iterations, etc.)"
    )

    # Indicates CosyLab was unavailable and fallback (LLM/rule-based) was used
    used_llm_fallback: bool = Field(
        default=False,
        description="True when CosyLab API was not responsive and fallback was used"
    )