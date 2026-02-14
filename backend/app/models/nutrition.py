"""
Pydantic models for nutrition data.

This module defines data models for macronutrient and micronutrient
information used throughout the health scoring system.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Dict, Optional


class MacroNutrition(BaseModel):
    """
    Macronutrient data model.
    
    Contains macronutrient information (calories, protein, carbs, fats)
    and related negative factors (sodium, sugar, cholesterol).
    
    Attributes:
        calories: Total calories per serving
        protein: Protein in grams
        carbs: Carbohydrates in grams
        fat: Total fat in grams
        saturated_fat: Saturated fat in grams (optional)
        trans_fat: Trans fat in grams (optional)
        sodium: Sodium in milligrams (optional)
        sugar: Sugar in grams (optional)
        cholesterol: Cholesterol in milligrams (optional)
        fiber: Dietary fiber in grams (optional)
    """
    calories: float = Field(..., ge=0, description="Total calories per serving")
    protein: float = Field(..., ge=0, description="Protein in grams")
    carbs: float = Field(..., ge=0, description="Carbohydrates in grams")
    fat: float = Field(..., ge=0, description="Total fat in grams")
    saturated_fat: Optional[float] = Field(None, ge=0, description="Saturated fat in grams")
    trans_fat: Optional[float] = Field(None, ge=0, description="Trans fat in grams")
    sodium: Optional[float] = Field(None, ge=0, description="Sodium in milligrams")
    sugar: Optional[float] = Field(None, ge=0, description="Sugar in grams")
    cholesterol: Optional[float] = Field(None, ge=0, description="Cholesterol in milligrams")
    fiber: Optional[float] = Field(None, ge=0, description="Dietary fiber in grams")
    
    @field_validator('saturated_fat')
    @classmethod
    def validate_saturated_fat(cls, v: Optional[float], info) -> Optional[float]:
        """Ensure saturated fat does not exceed total fat."""
        if v is not None and 'fat' in info.data:
            if v > info.data['fat']:
                raise ValueError('Saturated fat cannot exceed total fat')
        return v
    
    @field_validator('trans_fat')
    @classmethod
    def validate_trans_fat(cls, v: Optional[float], info) -> Optional[float]:
        """Ensure trans fat does not exceed total fat."""
        if v is not None and 'fat' in info.data:
            if v > info.data['fat']:
                raise ValueError('Trans fat cannot exceed total fat')
        return v
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "calories": 350.0,
                "protein": 25.0,
                "carbs": 30.0,
                "fat": 15.0,
                "saturated_fat": 5.0,
                "trans_fat": 0.0,
                "sodium": 450.0,
                "sugar": 8.0,
                "cholesterol": 75.0,
                "fiber": 4.0
            }
        }
    }


class MicroNutrition(BaseModel):
    """
    Micronutrient data model.
    
    Contains vitamin and mineral information for comprehensive
    nutritional analysis.
    
    Attributes:
        vitamins: Dictionary of vitamin names to values
        minerals: Dictionary of mineral names to values
    """
    vitamins: Dict[str, float] = Field(
        default_factory=dict,
        description="Vitamin content (name: amount)"
    )
    minerals: Dict[str, float] = Field(
        default_factory=dict,
        description="Mineral content (name: amount)"
    )
    
    @field_validator('vitamins', 'minerals')
    @classmethod
    def validate_non_negative_values(cls, v: Dict[str, float]) -> Dict[str, float]:
        """Ensure all nutrient values are non-negative."""
        for nutrient, value in v.items():
            if value < 0:
                raise ValueError(f'{nutrient} value cannot be negative')
        return v
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "vitamins": {
                    "vitamin_a": 500.0,
                    "vitamin_c": 25.0,
                    "vitamin_d": 5.0,
                    "vitamin_e": 3.0,
                    "vitamin_k": 15.0,
                    "thiamin": 0.5,
                    "riboflavin": 0.6,
                    "niacin": 8.0,
                    "vitamin_b6": 1.0,
                    "folate": 100.0,
                    "vitamin_b12": 2.0
                },
                "minerals": {
                    "calcium": 200.0,
                    "iron": 5.0,
                    "magnesium": 80.0,
                    "phosphorus": 150.0,
                    "potassium": 400.0,
                    "zinc": 3.0,
                    "selenium": 20.0
                }
            }
        }
    }


class NutritionData(BaseModel):
    """
    Complete nutrition data model.
    
    Combines macronutrient and micronutrient information.
    
    Attributes:
        macros: Macronutrient data
        micros: Micronutrient data
    """
    macros: MacroNutrition = Field(..., description="Macronutrient information")
    micros: MicroNutrition = Field(..., description="Micronutrient information")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "macros": {
                    "calories": 350.0,
                    "protein": 25.0,
                    "carbs": 30.0,
                    "fat": 15.0,
                    "saturated_fat": 5.0,
                    "trans_fat": 0.0,
                    "sodium": 450.0,
                    "sugar": 8.0,
                    "cholesterol": 75.0,
                    "fiber": 4.0
                },
                "micros": {
                    "vitamins": {
                        "vitamin_c": 25.0,
                        "vitamin_d": 5.0
                    },
                    "minerals": {
                        "calcium": 200.0,
                        "iron": 5.0
                    }
                }
            }
        }
    }