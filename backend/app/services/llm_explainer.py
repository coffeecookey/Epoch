"""
LLM-based explanation generator (OPTIONAL for MVP).

This module provides natural language explanations for health analysis
and ingredient swap recommendations. It can use either:
1. Template-based generation (recommended for MVP - implemented here)
2. External LLM API calls (Claude, GPT - can be added later)
3. Skip entirely (for minimal MVP)

Template-based generation is fast, free, and provides consistent,
understandable explanations without external dependencies.
"""

import logging
from typing import Dict, List, Optional

from app.models.health_score import HealthScore

# Configure logging
logger = logging.getLogger(__name__)


class LLMExplainer:
    """
    Service for generating natural language explanations.
    
    Uses template-based text generation for MVP. Can be extended to use
    actual LLM APIs in the future.
    
    Attributes:
        use_templates: Whether to use template-based generation (True for MVP)
        api_key: Optional API key for external LLM service
    """
    
    def __init__(self, use_templates: bool = True, api_key: Optional[str] = None):
        """
        Initialize LLM explainer.
        
        Args:
            use_templates: Use template-based generation (default: True)
            api_key: Optional API key for external LLM service
        """
        self.use_templates = use_templates
        self.api_key = api_key
        
        logger.info(
            f"LLMExplainer initialized with "
            f"use_templates={use_templates}, "
            f"api_available={bool(api_key)}"
        )
    
    def generate_health_explanation(
        self,
        score: float,
        rating: str,
        nutrition_data: Dict
    ) -> str:
        """
        Generate explanation for why a recipe received its health score.
        
        Provides 2-3 sentences explaining the health score in plain English,
        highlighting key nutritional strengths and weaknesses.
        
        Args:
            score: Health score (0-100)
            rating: Rating category (Excellent/Good/Decent/Bad/Poor)
            nutrition_data: Nutrition data dictionary
            
        Returns:
            str: Plain text explanation
            
        Example:
            explanation = explainer.generate_health_explanation(
                75.5,
                "Good",
                {"calories": 350, "protein": 25, "sodium": 450}
            )
            # Returns: "This recipe has a Good health rating (75.5/100). 
            #           It provides excellent protein content but has 
            #           moderately high sodium levels..."
        """
        logger.debug(f"Generating health explanation for score={score}, rating={rating}")
        
        if self.use_templates:
            return self._template_health_explanation(score, rating, nutrition_data)
        else:
            # Future: Call external LLM API
            return self._api_health_explanation(score, rating, nutrition_data)
    
    def _template_health_explanation(
        self,
        score: float,
        rating: str,
        nutrition_data: Dict
    ) -> str:
        """Generate health explanation using templates."""
        # Start with score and rating
        explanation = f"This recipe has a {rating} health rating ({score:.1f}/100). "
        
        # Analyze nutritional highlights
        highlights = []
        concerns = []
        
        # Check protein
        protein = nutrition_data.get("protein", 0)
        if protein >= 20:
            highlights.append("excellent protein content")
        elif protein >= 10:
            highlights.append("good protein content")
        
        # Check fiber
        fiber = nutrition_data.get("fiber", 0)
        if fiber >= 5:
            highlights.append("high fiber")
        
        # Check concerns
        sodium = nutrition_data.get("sodium", 0)
        if sodium > 400:
            concerns.append("moderately high sodium")
        elif sodium > 600:
            concerns.append("high sodium")
        
        sugar = nutrition_data.get("sugar", 0)
        if sugar > 25:
            concerns.append("high sugar content")
        
        saturated_fat = nutrition_data.get("saturated_fat", 0)
        if saturated_fat > 10:
            concerns.append("high saturated fat")
        
        # Build explanation
        if highlights:
            explanation += "It provides " + " and ".join(highlights) + ". "
        
        if concerns:
            explanation += "However, it has " + " and ".join(concerns) + ". "
        
        # Add recommendation based on rating
        if rating == "Excellent":
            explanation += "This is a very healthy recipe with minimal improvements needed."
        elif rating == "Good":
            explanation += "This is a healthy recipe overall with some room for improvement."
        elif rating == "Decent":
            explanation += "This recipe is acceptable but could benefit from healthier ingredients."
        elif rating == "Bad":
            explanation += "This recipe needs significant improvements to be considered healthy."
        else:  # Poor
            explanation += "This recipe requires major reformulation to improve its nutritional value."
        
        return explanation
    
    def generate_swap_explanation(
        self,
        swaps: List[Dict],
        original_score: HealthScore,
        projected_score: HealthScore
    ) -> str:
        """
        Generate explanation for ingredient swap suggestions.
        
        Explains why specific swaps were suggested and what improvements
        are expected.
        
        Args:
            swaps: List of swap dictionaries
            original_score: Original health score object
            projected_score: Projected score after swaps
            
        Returns:
            str: Plain text explanation
        """
        logger.debug("Generating swap explanation")
        
        if self.use_templates:
            return self._template_swap_explanation(swaps, original_score, projected_score)
        else:
            # Future: Call external LLM API
            return self._api_swap_explanation(swaps, original_score, projected_score)
    
    def _template_swap_explanation(
        self,
        swaps: List[Dict],
        original_score: HealthScore,
        projected_score: HealthScore
    ) -> str:
        """Generate swap explanation using templates."""
        score_improvement = projected_score.score - original_score.score
        
        explanation = (
            f"We suggest {len(swaps)} ingredient swap(s) to improve this recipe's "
            f"health score from {original_score.score:.1f} ({original_score.rating}) "
            f"to {projected_score.score:.1f} ({projected_score.rating}). "
        )
        
        # Highlight key swaps
        if swaps:
            swap_details = []
            for swap in swaps[:3]:  # Show top 3 swaps
                original = swap.get("original", "")
                substitute_obj = swap.get("substitute", {})
                substitute = substitute_obj.get("name", "")
                
                if original and substitute:
                    swap_details.append(f"{original} with {substitute}")
            
            if swap_details:
                explanation += (
                    "Key substitutions include replacing " +
                    ", ".join(swap_details) + ". "
                )
        
        # Add improvement context
        if score_improvement >= 15:
            explanation += "These changes will significantly improve the nutritional profile."
        elif score_improvement >= 8:
            explanation += "These changes will notably improve the recipe's healthiness."
        else:
            explanation += "These changes will provide modest health improvements."
        
        return explanation
    
    def summarize_analysis(self, full_analysis: Dict) -> str:
        """
        Create executive summary of complete analysis.
        
        Generates a 1-paragraph summary of the entire health analysis,
        suitable for display at the top of results.
        
        Args:
            full_analysis: Complete analysis result dictionary
            
        Returns:
            str: One-paragraph summary
        """
        logger.debug("Generating analysis summary")
        
        if self.use_templates:
            return self._template_analysis_summary(full_analysis)
        else:
            # Future: Call external LLM API
            return self._api_analysis_summary(full_analysis)
    
    def _template_analysis_summary(self, full_analysis: Dict) -> str:
        """Generate analysis summary using templates."""
        recipe_name = full_analysis.get("recipe", {}).get("name", "This recipe")
        health_score = full_analysis.get("health_score", {})
        score = health_score.get("score", 0)
        rating = health_score.get("rating", "Unknown")
        allergens = full_analysis.get("allergens", [])
        workflow = full_analysis.get("workflow", "")
        
        summary = f"{recipe_name} has a {rating} health rating ({score:.1f}/100). "
        
        if allergens:
            allergen_names = [a.get("name", "") for a in allergens]
            summary += f"Contains allergens: {', '.join(allergen_names)}. "
        else:
            summary += "No common allergens detected. "
        
        if workflow == "healthy_recommendation":
            summary += "We've found similar healthy recipes you might enjoy."
        elif workflow == "ingredient_swap":
            summary += "We suggest healthier ingredient substitutions to improve this recipe."
        
        return summary
    
    def _api_health_explanation(
        self,
        score: float,
        rating: str,
        nutrition_data: Dict
    ) -> str:
        """
        Generate health explanation using external LLM API.
        
        NOTE: Not implemented in MVP. This is a placeholder for future
        integration with Claude, GPT, or other LLM services.
        """
        logger.warning("LLM API not implemented - falling back to template")
        return self._template_health_explanation(score, rating, nutrition_data)
    
    def _api_swap_explanation(
        self,
        swaps: List[Dict],
        original_score: HealthScore,
        projected_score: HealthScore
    ) -> str:
        """
        Generate swap explanation using external LLM API.
        
        NOTE: Not implemented in MVP. Placeholder for future LLM integration.
        """
        logger.warning("LLM API not implemented - falling back to template")
        return self._template_swap_explanation(swaps, original_score, projected_score)
    
    def _api_analysis_summary(self, full_analysis: Dict) -> str:
        """
        Generate analysis summary using external LLM API.
        
        NOTE: Not implemented in MVP. Placeholder for future LLM integration.
        """
        logger.warning("LLM API not implemented - falling back to template")
        return self._template_analysis_summary(full_analysis)

    # ==================================================================
    # Craving Replacement System — LLM-backed insight generation
    # ==================================================================

    def generate_craving_insight(self, craving_request) -> Optional[str]:
        """
        Generate a 1-2 sentence psychological insight for a craving using Gemini.

        Falls back to None so the caller can use template constants.
        """
        if not self.api_key:
            return None

        try:
            from google import genai

            client = genai.Client(api_key=self.api_key)
            prompt = (
                "You are a nutrition psychologist. In 2 sentences, explain the "
                "psychological or physiological reason why someone would crave "
                f"'{craving_request.craving_text}' "
                f"(flavor: {craving_request.flavor_type.value}) "
                f"at {craving_request.time_of_day.value}"
            )
            if craving_request.mood:
                prompt += f" while feeling {craving_request.mood.value}"
            if craving_request.context:
                prompt += f" (context: {craving_request.context})"
            prompt += ". Be specific and evidence-based. No bullet points."

            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            text = response.text.strip() if response and response.text else None
            if text:
                logger.info("LLM craving insight generated successfully")
            return text
        except Exception as e:
            logger.warning(f"LLM craving insight failed: {e}")
            return None

    def generate_craving_pattern_insights(
        self, history_summary: Dict
    ) -> Optional[List[str]]:
        """
        Ask Gemini to identify non-obvious patterns in craving history.

        Args:
            history_summary: Aggregated stats dict (top_flavor, top_mood, etc.)

        Returns:
            List of human-readable pattern strings, or None on failure.
        """
        if not self.api_key:
            return None

        try:
            from google import genai

            client = genai.Client(api_key=self.api_key)
            prompt = (
                "You are a nutrition psychologist analysing a user's craving log "
                "summary. Identify up to 3 actionable behavioural patterns from:\n"
                f"{history_summary}\n"
                "Return each pattern as a single sentence. No intro text."
            )
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            if response and response.text:
                lines = [
                    line.strip().lstrip("•-0123456789. ")
                    for line in response.text.strip().split("\n")
                    if line.strip()
                ]
                return lines[:3] if lines else None
            return None
        except Exception as e:
            logger.warning(f"LLM pattern insight failed: {e}")
            return None