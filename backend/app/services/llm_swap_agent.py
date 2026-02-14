"""
LLM Swap Agent — Gemini-powered agentic ingredient substitution system.

Replaces the rule-based swap engine (steps 6-9) with a single Gemini agent
that actively queries FlavorDB and RecipeDB via function calling to find
scientifically-grounded, context-aware ingredient substitutions.
"""

import json
import logging
import re
from typing import Dict, List, Optional

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    genai = None
    types = None
    GENAI_AVAILABLE = False

from app.config import settings
from app.services.flavordb_extended import FlavorDBExtendedService
from app.services.recipedb_service import RecipeDBService
from app.services.tool_definitions import ALL_TOOLS
from app.models.agent_response import AgentSubstitution, AgentSwapResult

logger = logging.getLogger(__name__)

# ─── System Prompt ─────────────────────────────────────────────────────────────

AGENT_SYSTEM_PROMPT = """You are a scientific food-substitution agent. Your mission is to find the healthiest possible ingredient swaps for a recipe while preserving its flavor profile as closely as possible.

## Your Capabilities
You have access to FlavorDB and RecipeDB APIs via function calling. You MUST use these tools — do NOT rely on your training data alone for molecular or nutritional claims.

## Workflow (follow this order strictly)

### Phase 1: Plan
Before calling any tool, state your plan:
- Which ingredients are risky and why (high sat fat, high sugar, high sodium, trans fats, etc.)
- What categories of substitutes you will explore for each
- Which tools you will call first

### Phase 2: Investigate (Tool Calls)
For each risky ingredient:

1. **Flavor profile analysis**: Call `flavordb_get_entity_by_name` for the original ingredient to get its molecule set.

2. **Candidate discovery**: Based on the flavor profile, identify 2-4 candidate substitutes. For each candidate, call `flavordb_get_entity_by_name` to get its molecules.

3. **Molecular comparison**: Compare shared molecules between original and candidate. If needed, use `flavordb_get_molecules_by_common_name` for detailed molecule data, `flavordb_get_physicochemical_properties` for structural similarity.

4. **Perceptual filtering**: Use `flavordb_get_aroma_threshold` and `flavordb_get_taste_threshold` for key shared molecules — only molecules detectable at food-relevant concentrations matter.

5. **Food pairing validation**: Call `flavordb_get_flavor_pairings` for the candidate to check that it pairs well with the other recipe ingredients.

6. **Functional role verification**: Call `recipedb_search_by_ingredient` for the candidate to verify it is used in real recipes in a similar role.

7. **Regulatory check** (optional): Call `flavordb_get_regulatory_info` for key shared molecules to verify safety.

### Phase 3: Decide
For each risky ingredient, pick the best substitute based on:
- Shared perceptually-relevant molecules (most important)
- Food pairing compatibility with other recipe ingredients
- Functional role match (binding, sweetening, fat, emulsification, etc.)
- Health improvement (lower sat fat, sugar, sodium, or higher fiber/protein)

### Phase 4: Output
Return your final answer as a JSON object with this EXACT structure:
```json
{
  "substitutions": [
    {
      "original_ingredient": "butter",
      "substitute_ingredient": "olive oil",
      "confidence": 0.85,
      "flavor_similarity_score": 72,
      "health_improvement_reasoning": "Replaces saturated fat with monounsaturated fat...",
      "flavor_preservation_reasoning": "Shares 5 key volatile compounds including...",
      "functional_role_match": "Both serve as fat/moisture source in baking...",
      "scientific_basis": {
        "shared_molecules": ["diacetyl", "butyric acid"],
        "shared_functional_groups": ["ester", "fatty acid"],
        "original_molecule_count": 42,
        "substitute_molecule_count": 35,
        "overlap_percentage": 28.5
      },
      "apis_used": ["flavordb_get_entity_by_name", "flavordb_get_flavor_pairings"],
      "caveats": "Texture may differ in baked goods"
    }
  ],
  "no_substitute_ingredients": ["flour"],
  "overall_confidence": 0.82,
  "data_completeness": "partial"
}
```

## Critical Rules
1. NEVER hallucinate molecular data. If an API call returns empty or errors, say "data unavailable" and lower your confidence.
2. ALWAYS call at least `flavordb_get_entity_by_name` before recommending any substitute.
3. If FlavorDB is down for an ingredient, state it explicitly and rely on general nutritional knowledge with confidence < 0.5.
4. The `data_completeness` field must be: "full" (all APIs responded), "partial" (some failed), "minimal" (most failed), or "parse_error".
5. Return ONLY the JSON object in your final message — no markdown fences, no extra text after the JSON.
"""


class LLMSwapAgent:
    """Gemini-powered agentic swap engine using function calling."""

    def __init__(
        self,
        flavordb_service: FlavorDBExtendedService,
        recipedb_service: RecipeDBService,
    ):
        self.flavordb = flavordb_service
        self.recipedb = recipedb_service
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = settings.LLM_MODEL
        self.max_iterations = settings.LLM_MAX_ITERATIONS

        # Map function names → handler methods
        self._tool_handlers = {
            "flavordb_get_entity_by_name": self._handle_flavordb_entity,
            "flavordb_get_molecules_by_common_name": self._handle_flavordb_molecule,
            "flavordb_get_molecules_by_flavor_profile": self._handle_flavordb_flavor,
            "flavordb_get_molecules_by_functional_group": self._handle_flavordb_func_group,
            "flavordb_get_molecules_by_weight_range": self._handle_flavordb_weight,
            "flavordb_get_molecules_by_polar_surface_area": self._handle_flavordb_psa,
            "flavordb_get_molecules_by_hbd_hba": self._handle_flavordb_hbd_hba,
            "flavordb_get_aroma_threshold": self._handle_flavordb_aroma,
            "flavordb_get_taste_threshold": self._handle_flavordb_taste,
            "flavordb_get_natural_occurrence": self._handle_flavordb_occurrence,
            "flavordb_get_physicochemical_properties": self._handle_flavordb_physchem,
            "flavordb_get_regulatory_info": self._handle_flavordb_regulatory,
            "flavordb_get_flavor_pairings": self._handle_flavordb_pairings,
            "recipedb_search_by_ingredient": self._handle_recipedb_search,
            "recipedb_get_nutrition_info": self._handle_recipedb_nutrition,
            "recipedb_search_by_cuisine": self._handle_recipedb_cuisine,
        }

    # ─── Public entry point ────────────────────────────────────────────────

    def run(
        self,
        recipe_name: str,
        ingredients: List[str],
        nutrition_data: Dict,
        original_health_score: float,
        allergens: Optional[List[str]] = None,
        avoid_ingredients: Optional[List[str]] = None,
    ) -> AgentSwapResult:
        """
        Run the agentic loop: send context → let Gemini call tools → parse final JSON.

        Returns an AgentSwapResult with substitutions, confidence, and metadata.
        """
        logger.info(f"LLM swap agent starting for recipe: {recipe_name}")

        user_message = self._build_user_message(
            recipe_name, ingredients, nutrition_data,
            original_health_score, allergens, avoid_ingredients,
        )

        # Build initial conversation
        contents: List[types.Content] = [
            types.Content(role="user", parts=[types.Part.from_text(text=user_message)])
        ]

        tools_called: List[str] = []
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1
            logger.info(f"Agent iteration {iteration}/{self.max_iterations}")

            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=AGENT_SYSTEM_PROMPT,
                        tools=[types.Tool(function_declarations=ALL_TOOLS)],
                        temperature=0.3,
                        max_output_tokens=settings.LLM_MAX_TOKENS,
                    ),
                )
            except Exception as e:
                logger.error(f"Gemini API call failed: {e}")
                return AgentSwapResult(
                    data_completeness="parse_error",
                    raw_reasoning=f"Gemini API error: {e}",
                    iterations=iteration,
                    apis_called=tools_called,
                )

            candidate = response.candidates[0] if response.candidates else None
            if not candidate or not candidate.content or not candidate.content.parts:
                logger.warning("Empty response from Gemini")
                break

            parts = candidate.content.parts

            # Check if there are function calls in this response
            function_calls = [p for p in parts if p.function_call]

            if not function_calls:
                # No tool calls — this is the final text response
                final_text = "".join(
                    p.text for p in parts if p.text
                )
                logger.info(f"Agent finished after {iteration} iterations")
                # Add assistant response to history for completeness
                contents.append(candidate.content)
                return self._parse_agent_response(final_text, tools_called, iteration)

            # There are function calls — execute them and continue the loop
            # First, add the model's response (with function_call parts) to history
            contents.append(candidate.content)

            # Execute each function call and build response parts
            function_response_parts: List[types.Part] = []
            for part in function_calls:
                fc = part.function_call
                fname = fc.name
                fargs = dict(fc.args) if fc.args else {}
                tools_called.append(fname)

                logger.info(f"  Tool call: {fname}({fargs})")
                result = self._execute_tool(fname, fargs)

                function_response_parts.append(
                    types.Part.from_function_response(
                        name=fname,
                        response=result,
                    )
                )

            # Add all function responses as a single user turn
            contents.append(
                types.Content(role="user", parts=function_response_parts)
            )

        # Hit max iterations
        logger.warning(f"Agent hit max iterations ({self.max_iterations})")
        return AgentSwapResult(
            data_completeness="partial",
            raw_reasoning="Agent reached maximum iteration limit",
            iterations=iteration,
            apis_called=tools_called,
        )

    # ─── Message building ──────────────────────────────────────────────────

    def _build_user_message(
        self,
        recipe_name: str,
        ingredients: List[str],
        nutrition_data: Dict,
        original_health_score: float,
        allergens: Optional[List[str]],
        avoid_ingredients: Optional[List[str]],
    ) -> str:
        return (
            f"Analyze this recipe and find healthier ingredient substitutions.\n\n"
            f"Recipe: {recipe_name}\n"
            f"Ingredients: {', '.join(ingredients)}\n"
            f"Current nutrition per serving: {json.dumps(nutrition_data)}\n"
            f"Current health score: {original_health_score}/100\n"
            f"Allergens to avoid: {', '.join(allergens) if allergens else 'none'}\n"
            f"Ingredients to definitely avoid: {', '.join(avoid_ingredients) if avoid_ingredients else 'none'}\n\n"
            f"Use the available FlavorDB and RecipeDB tools to ground your analysis. "
            f"Follow the workflow in your system instructions strictly."
        )

    # ─── Tool execution dispatch ───────────────────────────────────────────

    def _execute_tool(self, function_name: str, args: Dict) -> Dict:
        """Dispatch a tool call to the appropriate service method."""
        handler = self._tool_handlers.get(function_name)
        if not handler:
            return {"error": f"Unknown tool: {function_name}"}
        try:
            return handler(args)
        except Exception as e:
            logger.error(f"Tool {function_name} failed: {e}")
            return {
                "error": str(e),
                "note": "API call failed. Proceed with available data and lower confidence.",
            }

    # ─── FlavorDB tool handlers ────────────────────────────────────────────

    def _handle_flavordb_entity(self, args: Dict) -> Dict:
        return self.flavordb.get_flavor_profile_by_ingredient(args["ingredient_name"])

    def _handle_flavordb_molecule(self, args: Dict) -> Dict:
        return self.flavordb.get_molecules_by_name(args["molecule_name"])

    def _handle_flavordb_flavor(self, args: Dict) -> Dict:
        molecules = self.flavordb.get_molecules_by_flavor(args["flavor"])
        return {"molecules": molecules}

    def _handle_flavordb_func_group(self, args: Dict) -> Dict:
        molecules = self.flavordb.get_molecules_by_functional_group(args["group"])
        return {"molecules": molecules}

    def _handle_flavordb_weight(self, args: Dict) -> Dict:
        molecules = self.flavordb.get_molecules_by_weight_range(
            args["min_weight"], args["max_weight"]
        )
        return {"molecules": molecules}

    def _handle_flavordb_psa(self, args: Dict) -> Dict:
        molecules = self.flavordb.get_molecules_by_polar_surface_area(
            args["min_psa"], args["max_psa"]
        )
        return {"molecules": molecules}

    def _handle_flavordb_hbd_hba(self, args: Dict) -> Dict:
        molecules = self.flavordb.get_molecules_by_hbd_hba(
            args["min_hbd"], args["max_hbd"], args["min_hba"], args["max_hba"]
        )
        return {"molecules": molecules}

    def _handle_flavordb_aroma(self, args: Dict) -> Dict:
        return self.flavordb.get_aroma_threshold(args["molecule_name"])

    def _handle_flavordb_taste(self, args: Dict) -> Dict:
        return self.flavordb.get_taste_threshold(args["molecule_name"])

    def _handle_flavordb_occurrence(self, args: Dict) -> Dict:
        return self.flavordb.get_natural_occurrence(args["molecule_name"])

    def _handle_flavordb_physchem(self, args: Dict) -> Dict:
        return self.flavordb.get_physicochemical_properties(args["molecule_name"])

    def _handle_flavordb_regulatory(self, args: Dict) -> Dict:
        return self.flavordb.get_regulatory_info(args["molecule_name"])

    def _handle_flavordb_pairings(self, args: Dict) -> Dict:
        pairings = self.flavordb.get_flavor_pairings(args["ingredient_name"])
        return {"pairings": pairings}

    # ─── RecipeDB tool handlers ────────────────────────────────────────────

    def _handle_recipedb_search(self, args: Dict) -> Dict:
        result = self.recipedb.fetch_recipe_by_name(args["ingredient_name"])
        return result if result else {"error": "No recipes found", "note": "RecipeDB may be down"}

    def _handle_recipedb_nutrition(self, args: Dict) -> Dict:
        try:
            return self.recipedb.fetch_nutrition_info(args["recipe_id"])
        except ValueError as e:
            return {"error": str(e)}

    def _handle_recipedb_cuisine(self, args: Dict) -> Dict:
        recipes = self.recipedb.search_by_cuisine(args["cuisine"])
        return {"recipes": recipes[:10]}  # Cap at 10 to control token usage

    # ─── Response parsing ──────────────────────────────────────────────────

    def _parse_agent_response(
        self, text: str, tools_called: List[str], iterations: int
    ) -> AgentSwapResult:
        """Parse the agent's final JSON text into an AgentSwapResult."""
        # Try to extract JSON from the text
        json_str = self._extract_json(text)

        if not json_str:
            logger.warning("Could not extract JSON from agent response")
            return AgentSwapResult(
                data_completeness="parse_error",
                raw_reasoning=text,
                apis_called=tools_called,
                iterations=iterations,
            )

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return AgentSwapResult(
                data_completeness="parse_error",
                raw_reasoning=text,
                apis_called=tools_called,
                iterations=iterations,
            )

        # Parse substitutions
        substitutions = []
        for sub_data in data.get("substitutions", []):
            try:
                substitutions.append(AgentSubstitution(
                    original_ingredient=sub_data.get("original_ingredient", ""),
                    substitute_ingredient=sub_data.get("substitute_ingredient", ""),
                    confidence=float(sub_data.get("confidence", 0.5)),
                    flavor_similarity_score=float(sub_data.get("flavor_similarity_score", 50)),
                    health_improvement_reasoning=sub_data.get("health_improvement_reasoning", ""),
                    flavor_preservation_reasoning=sub_data.get("flavor_preservation_reasoning", ""),
                    functional_role_match=sub_data.get("functional_role_match", ""),
                    scientific_basis=sub_data.get("scientific_basis", {}),
                    apis_used=sub_data.get("apis_used", []),
                    caveats=sub_data.get("caveats"),
                ))
            except Exception as e:
                logger.warning(f"Failed to parse substitution: {e}")

        return AgentSwapResult(
            substitutions=substitutions,
            overall_confidence=float(data.get("overall_confidence", 0.5)),
            data_completeness=data.get("data_completeness", "partial"),
            no_substitute_ingredients=data.get("no_substitute_ingredients", []),
            apis_called=tools_called,
            iterations=iterations,
        )

    def _extract_json(self, text: str) -> Optional[str]:
        """Extract JSON object from text, handling markdown fences and surrounding text."""
        # Try: raw text is valid JSON
        stripped = text.strip()
        if stripped.startswith("{"):
            # Find the matching closing brace
            depth = 0
            for i, ch in enumerate(stripped):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        return stripped[: i + 1]

        # Try: JSON inside markdown code fence
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            return match.group(1)

        # Try: first { to last }
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            return text[first_brace: last_brace + 1]

        return None
