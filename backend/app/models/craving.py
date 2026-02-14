"""
Pydantic models for the Craving Replacement System.

Defines request/response schemas for craving analysis, replacement suggestions,
pattern detection, and history tracking.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict
from enum import Enum


class FlavorType(str, Enum):
    sweet = "sweet"
    salty = "salty"
    crunchy = "crunchy"
    spicy = "spicy"
    umami = "umami"
    creamy = "creamy"


class MoodType(str, Enum):
    stressed = "stressed"
    bored = "bored"
    tired = "tired"
    happy = "happy"
    anxious = "anxious"
    sad = "sad"


class TimeOfDay(str, Enum):
    morning = "morning"
    afternoon = "afternoon"
    evening = "evening"
    late_night = "late-night"


class CravingRequest(BaseModel):
    """Request model for craving replacement endpoint."""
    craving_text: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Free-text craving description, e.g. 'chocolate at night'",
        examples=["chocolate", "something crunchy and salty"],
    )
    flavor_type: FlavorType = Field(
        ...,
        description="Primary flavor profile of the craving",
    )
    mood: Optional[MoodType] = Field(
        None,
        description="User's current mood (optional)",
    )
    time_of_day: TimeOfDay = Field(
        ...,
        description="Time of day the craving occurs",
    )
    context: Optional[str] = Field(
        None,
        max_length=300,
        description="Optional context, e.g. 'after studying for 4 hours'",
    )
    user_allergens: Optional[List[str]] = Field(
        None,
        description="Allergen categories to avoid",
    )
    user_avoid_ingredients: Optional[List[str]] = Field(
        None,
        description="Specific ingredients to avoid",
    )
    diet_type: Optional[str] = Field(
        None,
        description="Dietary restriction, e.g. 'vegetarian'",
    )

    @field_validator("craving_text")
    @classmethod
    def validate_craving_text(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Craving text cannot be empty")
        return v.strip()


class QuickCombo(BaseModel):
    """A fast 2-3 ingredient combination that satisfies a craving."""
    name: str
    ingredients: List[str]
    prep_time_minutes: int = Field(ge=0, le=30)
    why_it_works: str
    flavor_match: str
    calories_estimate: Optional[int] = None


class CravingRecipe(BaseModel):
    """A full recipe suggestion for a craving, with health score."""
    id: Optional[str] = None
    name: str
    cuisine: Optional[str] = None
    diet_type: Optional[str] = None
    ingredients: List[str] = []
    prep_time: Optional[int] = None
    health_score: Optional[float] = None


class CravingReplacement(BaseModel):
    """Complete craving replacement response."""
    original_craving: str
    flavor_type: str
    psychological_insight: str
    quick_combos: List[QuickCombo]
    full_recipes: List[CravingRecipe]
    science_explanation: str
    encouragement: Optional[str] = None


class CravingHistoryEntry(BaseModel):
    """A single craving log entry (sent from frontend localStorage)."""
    id: str
    craving_text: str
    flavor_type: str
    mood: Optional[str] = None
    time_of_day: str
    context: Optional[str] = None
    replacement_chosen: Optional[str] = None
    timestamp: str


class CravingPattern(BaseModel):
    """A detected pattern in craving history."""
    pattern_description: str
    frequency: int
    trigger: str
    top_time: str
    top_mood: Optional[str] = None


class CravingPatternAnalysis(BaseModel):
    """Analysis result for craving history."""
    patterns: List[CravingPattern]
    weekly_summary: Dict
    encouragement_messages: List[str]
