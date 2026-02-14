"""
Pydantic models for the LLM swap agent response.

Defines structured output types that the agent's JSON response
is parsed into, plus helper methods for converting to the existing
API response format.
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional


class AgentSubstitution(BaseModel):
    """A single ingredient substitution proposed by the agent."""

    original_ingredient: str = Field(..., description="Original risky ingredient")
    substitute_ingredient: str = Field(..., description="Proposed healthier substitute")
    confidence: float = Field(0.5, ge=0.0, le=1.0, description="Agent confidence 0-1")
    flavor_similarity_score: float = Field(
        50.0, ge=0.0, le=100.0, description="Flavor similarity 0-100"
    )
    health_improvement_reasoning: str = Field("", description="Why this is healthier")
    flavor_preservation_reasoning: str = Field("", description="Why flavor is preserved")
    functional_role_match: str = Field("", description="Culinary function comparison")
    scientific_basis: Dict = Field(
        default_factory=dict, description="Shared molecules, functional groups, etc."
    )
    apis_used: List[str] = Field(default_factory=list, description="Which APIs were consulted")
    caveats: Optional[str] = Field(None, description="Any warnings or limitations")


class AgentSwapResult(BaseModel):
    """Complete result from the LLM swap agent."""

    substitutions: List[AgentSubstitution] = Field(default_factory=list)
    overall_confidence: float = Field(0.5, ge=0.0, le=1.0)
    data_completeness: str = Field(
        "minimal",
        description="full / partial / minimal / parse_error",
    )
    no_substitute_ingredients: List[str] = Field(
        default_factory=list, description="Ingredients the agent could not find subs for"
    )
    apis_called: List[str] = Field(default_factory=list)
    iterations: int = Field(0)
    raw_reasoning: Optional[str] = Field(None, description="Raw text if JSON parse failed")

    # ── Conversion helpers ─────────────────────────────────────────────────

    def to_risky_ingredients_dicts(self) -> List[Dict]:
        """Convert to the format expected by FullAnalysisResponse.risky_ingredients."""
        results = []
        for sub in self.substitutions:
            results.append({
                "name": sub.original_ingredient,
                "reason": sub.health_improvement_reasoning or "Identified as risky by AI agent",
                "priority": min(5, max(1, int(sub.confidence * 5))),
                "category": None,
                "health_impact": round(sub.confidence * 10, 1),
                "alternatives_available": True,
            })
        for name in self.no_substitute_ingredients:
            results.append({
                "name": name,
                "reason": "Identified as risky but no suitable substitute found",
                "priority": 2,
                "category": None,
                "health_impact": 3.0,
                "alternatives_available": False,
            })
        return results

    def to_swap_suggestions_dicts(self) -> List[Dict]:
        """Convert to the format expected by FullAnalysisResponse.swap_suggestions."""
        return [
            {
                "original": sub.original_ingredient,
                "substitute": {
                    "name": sub.substitute_ingredient,
                    "flavor_match": sub.flavor_similarity_score,
                    "health_improvement": round(sub.confidence * 10, 1),
                    "category": None,
                    "rank_score": round(
                        sub.flavor_similarity_score * 0.6 + sub.confidence * 40, 2
                    ),
                    "explanation": (
                        sub.health_improvement_reasoning[:200]
                        if sub.health_improvement_reasoning
                        else None
                    ),
                },
                "accepted": False,
            }
            for sub in self.substitutions
        ]

    def apply_to_ingredients(self, original_ingredients: List[str]) -> List[str]:
        """Return the ingredient list with substitutions applied."""
        swap_map = {
            sub.original_ingredient.lower(): sub.substitute_ingredient
            for sub in self.substitutions
        }
        return [
            swap_map.get(ing.lower(), ing)
            for ing in original_ingredients
        ]

    def estimate_nutrition_changes(
        self, nutrition_data: Dict, n_ingredients: int
    ) -> Dict:
        """Rough proportional nutrition estimate after swaps."""
        if n_ingredients == 0:
            return nutrition_data
        result = dict(nutrition_data)
        proportion = 1.0 / n_ingredients
        for sub in self.substitutions:
            # Healthier substitutes generally lower calories, sat fat, sodium, sugar
            factor = max(0.3, 1.0 - sub.confidence * 0.5)
            for key in ["calories", "saturated_fat", "trans_fat", "sodium", "sugar", "cholesterol"]:
                if key in result:
                    result[key] = result[key] - (result[key] * proportion * (1 - factor))
            # Fiber may increase
            if "fiber" in result:
                result[key] = result.get("fiber", 0) + (result.get("fiber", 0) * proportion * 0.2)
        return result

    def generate_explanation(self, original_score, improved_score) -> str:
        """Generate a human-readable summary of all swaps."""
        if not self.substitutions:
            return "No ingredient swaps were identified for this recipe."

        orig = original_score if isinstance(original_score, (int, float)) else getattr(original_score, "score", 0)
        impr = improved_score if isinstance(improved_score, (int, float)) else getattr(improved_score, "score", 0)

        lines = [
            f"The AI agent analyzed this recipe and proposed {len(self.substitutions)} swap(s), "
            f"improving the health score from {orig:.1f} to {impr:.1f}.",
            "",
        ]
        for i, sub in enumerate(self.substitutions, 1):
            lines.append(
                f"{i}. Replace **{sub.original_ingredient}** with "
                f"**{sub.substitute_ingredient}** "
                f"(confidence: {sub.confidence:.0%}, "
                f"flavor similarity: {sub.flavor_similarity_score:.0f}/100)"
            )
            if sub.health_improvement_reasoning:
                lines.append(f"   Health: {sub.health_improvement_reasoning}")
            if sub.flavor_preservation_reasoning:
                lines.append(f"   Flavor: {sub.flavor_preservation_reasoning}")
            if sub.caveats:
                lines.append(f"   Note: {sub.caveats}")
            lines.append("")

        if self.no_substitute_ingredients:
            lines.append(
                f"No suitable substitutes found for: {', '.join(self.no_substitute_ingredients)}"
            )

        lines.append(f"\nData completeness: {self.data_completeness} | "
                      f"APIs called: {len(self.apis_called)} | "
                      f"Agent iterations: {self.iterations}")
        return "\n".join(lines)

    def to_metadata_dict(self) -> Dict:
        """Metadata for the response (included in FullAnalysisResponse.agent_metadata)."""
        return {
            "overall_confidence": self.overall_confidence,
            "data_completeness": self.data_completeness,
            "apis_called": self.apis_called,
            "iterations": self.iterations,
            "substitution_count": len(self.substitutions),
            "no_substitute_count": len(self.no_substitute_ingredients),
        }
