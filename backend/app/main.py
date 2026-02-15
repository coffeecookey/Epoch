"""
FastAPI application entry point and endpoint definitions.

This module initializes the FastAPI application and defines all API routes
for the Recipe Health Analysis and Ingredient Swap system.

Responsibilities:
- Initialize FastAPI application with CORS and error handling
- Define all API endpoints for both workflows
- Coordinate service layer calls
- Handle request validation and error responses
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict
import logging
import uuid
import requests

from app.models.recipe import (
    RecipeAnalysisRequest,
    FullAnalysisRequest,
    RecipeRecommendation,
    QuickMealFilters,
    QuickMealResponse
)
from app.models.swap import (
    IngredientSwapRequest,
    IngredientSwapResponse,
    RecalculateRequest,
    RecalculateResponse
)
from app.models.health_score import HealthScore, RecipeAnalysisResponse, FullAnalysisResponse
from app.services.recipedb_service import RecipeDBService
from app.services.health_scorer import HealthScorer
from app.services.allergen_detector import AllergenDetector
from app.services.recommendation_engine import RecommendationEngine
from app.services.ingredient_analyzer import IngredientAnalyzer
from app.services.flavordb_service import FlavorDBService
from app.services.flavordb_extended import FlavorDBExtendedService
from app.services.swap_engine import SwapEngine
from app.services.llm_explainer import LLMExplainer
try:
    from app.services.llm_swap_agent import LLMSwapAgent, GENAI_AVAILABLE
except Exception:
    LLMSwapAgent = None
    GENAI_AVAILABLE = False
from app.services.quick_meal_service import QuickMealService
from app.services.craving_service import CravingService
from app.models.craving import (
    CravingRequest,
    CravingReplacement,
    CravingHistoryEntry,
    CravingPattern,
    CravingPatternAnalysis,
)
from app.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """
    Initialize and configure the FastAPI application.
    
    Sets up:
    - CORS middleware for frontend communication
    - Exception handlers for consistent error responses
    - Application metadata
    
    Returns:
        FastAPI: Configured FastAPI application instance
    """
    app = FastAPI(
        title="Recipe Health Analysis & Ingredient Swap API",
        description="MVP system for analyzing recipe health and suggesting ingredient swaps",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # Configure CORS to allow frontend communication
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:8080", "http://localhost:8081", "http://127.0.0.1:8080", "http://127.0.0.1:8081"],  # React / Vite / Frontend dev servers
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Global exception handler for consistent error responses
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        """
        Handle all uncaught exceptions with consistent error format.
        
        Args:
            request: The incoming request object
            exc: The exception that was raised
            
        Returns:
            JSONResponse: Formatted error response
        """
        logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Internal server error occurred",
                "error": str(exc)
            }
        )
    
    return app


# Initialize FastAPI application
app = create_app()

# Initialize service layer instances
recipedb_service = RecipeDBService()
health_scorer = HealthScorer()
allergen_detector = AllergenDetector()
recommendation_engine = RecommendationEngine(recipedb_service, health_scorer)
ingredient_analyzer = IngredientAnalyzer()
flavordb_service = FlavorDBService()
swap_engine = SwapEngine(
    flavordb_service,
    health_scorer,
    use_semantic_rerank=settings.USE_SEMANTIC_RERANK,
    semantic_weight=settings.SEMANTIC_WEIGHT,
)
llm_explainer = LLMExplainer() if settings.USE_LLM_EXPLANATIONS else None
quick_meal_service = QuickMealService(recipedb_service)

# Initialize Craving Replacement Service
_craving_llm = None
if settings.GEMINI_API_KEY:
    _craving_llm = LLMExplainer(use_templates=False, api_key=settings.GEMINI_API_KEY)
craving_service = CravingService(
    recipedb_service=recipedb_service,
    flavordb_service=flavordb_service,
    health_scorer=health_scorer,
    llm_explainer=_craving_llm,
)

# Initialize LLM swap agent (if configured)
llm_swap_agent = None
if settings.USE_LLM_AGENT and settings.GEMINI_API_KEY and GENAI_AVAILABLE and LLMSwapAgent is not None:
    try:
        flavordb_extended = FlavorDBExtendedService()
        llm_swap_agent = LLMSwapAgent(flavordb_extended, recipedb_service)
        logger.info("LLM swap agent initialized (Gemini)")
    except Exception as e:
        logger.warning(f"Failed to initialize LLM swap agent: {e}")
        llm_swap_agent = None
else:
    logger.info("LLM swap agent disabled — using rule-based swap engine")


# ==================== In-Memory Data Storage ====================
# Simple in-memory storage for user data (lost on server restart)
# In production, this would be replaced with a database
user_recipes: List[Dict] = []  # List of analyzed recipes
user_profiles: Dict[str, Dict] = {}  # Dict of user profiles by ID
profile_counter = 0  # Counter for generating profile IDs


@app.get("/")
async def root():
    """
    Root endpoint for health check.
    
    Returns:
        dict: API status and version information
    """
    return {
        "message": "Recipe Health Analysis & Ingredient Swap API",
        "version": "1.0.0",
        "status": "running"
    }


@app.post("/analyze", response_model=RecipeAnalysisResponse)
async def analyze_recipe(request: RecipeAnalysisRequest) -> RecipeAnalysisResponse:
    """
    Workflow 1: Analyze recipe health and provide recommendations.
    
    This endpoint performs a comprehensive health analysis of a recipe:
    1. Fetches recipe data from RecipeDB by name
    2. Retrieves nutrition and micronutrient information
    3. Calculates health score using rule-based system
    4. Detects allergens in ingredients
    5. If healthy (score >= 60) and no allergens, suggests similar recipes
    
    Args:
        request: RecipeAnalysisRequest containing recipe_name
        
    Returns:
        RecipeAnalysisResponse: Complete analysis including score, nutrition,
                                allergens, and recommendations (if applicable)
        
    Raises:
        HTTPException: 404 if recipe not found, 500 if processing fails
    """
    try:
        logger.info(f"Analyzing recipe: {request.recipe_name}")
        
        # Step 1: Fetch recipe data from RecipeDB
        recipe_data = recipedb_service.fetch_recipe_by_name(request.recipe_name)
        if not recipe_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recipe '{request.recipe_name}' not found in database"
            )
        
        recipe_id = recipe_data.get("id")
        ingredients = recipe_data.get("ingredients", [])
        
        # Step 2: Fetch nutrition data
        logger.info(f"Fetching nutrition data for recipe ID: {recipe_id}")
        nutrition_data = recipedb_service.fetch_nutrition_info(recipe_id)
        micro_nutrition_data = recipedb_service.fetch_micro_nutrition_info(recipe_id)
        
        # Step 3: Calculate health score using rule-based ML
        logger.info("Calculating health score")
        health_score = health_scorer.calculate_health_score(
            nutrition_data,
            micro_nutrition_data
        )
        
        # Step 4: Detect allergens
        logger.info("Detecting allergens")
        allergens = allergen_detector.detect_allergens(ingredients)
        
        # Step 5: Determine workflow path
        recommendations = None
        workflow_type = "healthy_recommendation"
        
        if health_score.score >= settings.MIN_HEALTHY_SCORE and len(allergens) == 0:
            # Recipe is healthy - provide similar recipe recommendations
            logger.info("Recipe is healthy, fetching recommendations")
            recommendations = recommendation_engine.find_similar_recipes(
                recipe_id=recipe_id,
                min_health_score=settings.MIN_HEALTHY_SCORE,
                limit=settings.MAX_RECOMMENDATIONS
            )
        else:
            # Recipe needs improvement - workflow will suggest swaps instead
            logger.info(
                f"Recipe needs improvement (score: {health_score.score}, "
                f"allergens: {len(allergens)}). Suggest using /swap endpoint."
            )
            workflow_type = "needs_improvement"
        
        # Build response
        response = RecipeAnalysisResponse(
            recipe=recipe_data,
            nutrition=nutrition_data,
            micro_nutrition=micro_nutrition_data,
            health_score=health_score,
            allergens=allergens,
            recommendations=recommendations,
            workflow=workflow_type
        )
        
        logger.info(f"Analysis complete. Score: {health_score.score}, Rating: {health_score.rating}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing recipe: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze recipe: {str(e)}"
        )


@app.post("/analyze-full", response_model=FullAnalysisResponse)
async def analyze_full(request: FullAnalysisRequest) -> FullAnalysisResponse:
    """
    Unified analysis endpoint: risk profile, allergens, RecipeDB search,
    ingredient swaps via FlavorDB, and improved profile comparison.

    When only recipe_name is provided (RecipeDB lookup mode):
    1. Recipe and ingredients are fetched from RecipeDB.
    2. Nutrition data (calories, protein, carbs, fat, etc.) is taken from RecipeDB.
    3. Health score is calculated from that nutrition via the health_scorer pipeline.
    4. Swap suggestions are generated (LLM agent or rule-based + FlavorDB) and
       projected health score is computed from the same pipeline.

    Custom input mode: provide recipe_name + ingredients (nutrition from RecipeDB if
    recipe is found, else ingredient-based estimate).
    """
    try:
        logger.info(f"Full analysis for: {request.recipe_name}")

        # ------------------------------------------------------------------
        # 0. Check API configuration
        # ------------------------------------------------------------------
        api_key_configured = settings.COSYLAB_API_KEY is not None and len(settings.COSYLAB_API_KEY) > 0
        if not api_key_configured:
            logger.error("❌ CosyLab API key is not configured!")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "CosyLab API key is not configured. "
                    "Please set COSYLAB_API_KEY in your .env file. "
                    "Without the API key, nutrition data cannot be fetched from RecipeDB."
                )
            )

        # ------------------------------------------------------------------
        # 1. Resolve recipe data (custom vs RecipeDB)
        # ------------------------------------------------------------------
        source = "custom"
        recipe_id = None
        nutrition_data = None
        micro_nutrition_data = None
        api_error_occurred = False
        api_error_details = []

        if request.ingredients:
            # Custom input mode
            ingredients = request.ingredients
            logger.info(f"Custom input mode with {len(ingredients)} ingredients")

            # Try to find this recipe in RecipeDB anyway (for nutrition data)
            recipe_data = recipedb_service.fetch_recipe_by_name(request.recipe_name)
            if recipe_data:
                recipe_id = recipe_data.get("id")
                source = "recipedb"
                logger.info(f"Found recipe in RecipeDB with ID: {recipe_id}, fetching nutrition data...")
                try:
                    nutrition_data = recipedb_service.fetch_nutrition_info(recipe_id)
                    logger.info(f"Successfully fetched nutrition data: {nutrition_data.get('calories', 0)} calories")
                    micro_nutrition_data = recipedb_service.fetch_micro_nutrition_info(recipe_id)
                    logger.info(f"Successfully fetched micronutrient data")
                except ValueError as e:
                    # ValueError is raised when API returns None (failed request)
                    error_msg = str(e)
                    logger.error(f"❌ CosyLab API failed to fetch nutrition data: {error_msg}")
                    api_error_occurred = True
                    api_error_details.append(f"Nutrition data fetch failed: {error_msg}")
                    nutrition_data = None
                    micro_nutrition_data = None
                except requests.exceptions.RequestException as e:
                    # Network/HTTP errors
                    error_msg = str(e)
                    logger.error(f"❌ CosyLab API network error: {error_msg}")
                    api_error_occurred = True
                    api_error_details.append(f"Network error connecting to CosyLab API: {error_msg}")
                    nutrition_data = None
                    micro_nutrition_data = None
                except Exception as e:
                    # Other unexpected errors
                    error_msg = str(e)
                    logger.error(f"❌ Unexpected error fetching nutrition data: {error_msg}")
                    api_error_occurred = True
                    api_error_details.append(f"Unexpected error: {error_msg}")
                    nutrition_data = None
                    micro_nutrition_data = None
            else:
                logger.info(f"Recipe '{request.recipe_name}' not found in RecipeDB, will use fallback nutrition data")
        else:
            # RecipeDB lookup mode
            logger.info(f"RecipeDB lookup mode: searching for '{request.recipe_name}'")
            recipe_data = recipedb_service.fetch_recipe_by_name(request.recipe_name)
            if not recipe_data:
                logger.error(f"Recipe '{request.recipe_name}' not found in RecipeDB")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=(
                        f"Recipe '{request.recipe_name}' not found in RecipeDB. "
                        "Try providing ingredients manually."
                    )
                )
            source = "recipedb"
            recipe_id = recipe_data.get("id")
            ingredients = recipe_data.get("ingredients", [])
            logger.info(f"Found recipe with ID: {recipe_id}, fetching nutrition data...")
            try:
                nutrition_data = recipedb_service.fetch_nutrition_info(recipe_id)
                logger.info(f"Successfully fetched nutrition data: {nutrition_data.get('calories', 0)} calories")
                micro_nutrition_data = recipedb_service.fetch_micro_nutrition_info(recipe_id)
                logger.info(f"Successfully fetched micronutrient data")
            except ValueError as e:
                # ValueError is raised when API returns None (failed request)
                error_msg = str(e)
                logger.error(f"❌ CosyLab API failed to fetch nutrition data: {error_msg}")
                api_error_occurred = True
                api_error_details.append(f"Nutrition data fetch failed: {error_msg}")
                nutrition_data = None
                micro_nutrition_data = None
            except requests.exceptions.RequestException as e:
                # Network/HTTP errors
                error_msg = str(e)
                logger.error(f"❌ CosyLab API network error: {error_msg}")
                api_error_occurred = True
                api_error_details.append(f"Network error connecting to CosyLab API: {error_msg}")
                nutrition_data = None
                micro_nutrition_data = None
            except Exception as e:
                # Other unexpected errors
                error_msg = str(e)
                logger.error(f"❌ Unexpected error fetching nutrition data: {error_msg}")
                api_error_occurred = True
                api_error_details.append(f"Unexpected error: {error_msg}")
                nutrition_data = None
                micro_nutrition_data = None

        # Check if API failed and raise error instead of using fallback
        # Only raise error if we actually tried to fetch nutrition data (recipe_id exists)
        if api_error_occurred and recipe_id:
            error_message = (
                "CosyLab API (RecipeDB) is not responding or returned an error. "
                "Unable to fetch nutrition data for accurate health scoring.\n\n"
                "Possible causes:\n"
                "1. API key is invalid or expired\n"
                "2. CosyLab API service is down\n"
                "3. Network connectivity issues\n"
                "4. API rate limit exceeded\n\n"
                f"Error details: {'; '.join(api_error_details)}\n\n"
                "Please check:\n"
                "- Your COSYLAB_API_KEY in .env file\n"
                "- Network connectivity to cosylab.iiitd.edu.in\n"
                "- Check /health endpoint for API status"
            )
            logger.error(f"❌ {error_message}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=error_message
            )

        # Fallback nutrition estimates when RecipeDB data unavailable (custom ingredients only)
        used_llm_fallback = False
        if nutrition_data is None:
            from app.utils.helpers import estimate_nutrition_from_ingredients
            logger.warning("⚠️ Using ingredient-based nutrition estimate (RecipeDB not available)")
            logger.warning("[COSYLAB API FALLBACK] RecipeDB nutrition endpoint did not return data for /analyze-full. Using ingredient-based estimation instead.")
            nutrition_data = estimate_nutrition_from_ingredients(ingredients)
            used_llm_fallback = True
        else:
            # Supplement missing negative-factor fields from ingredient estimates
            # recipe2-api only provides calories/protein/fat — sugar, sodium,
            # saturated_fat, cholesterol, carbs, fiber are all 0, which makes
            # swap rescoring impossible (multiplying 0 yields 0).
            _NEGATIVE_KEYS = ["sugar", "sodium", "saturated_fat", "trans_fat",
                              "cholesterol", "carbs", "fiber"]
            missing = [k for k in _NEGATIVE_KEYS if nutrition_data.get(k, 0) == 0]
            if missing and ingredients:
                from app.utils.helpers import estimate_nutrition_from_ingredients
                est = estimate_nutrition_from_ingredients(ingredients)
                supplemented = []
                for k in missing:
                    if est.get(k, 0) > 0:
                        nutrition_data[k] = est[k]
                        supplemented.append(f"{k}={est[k]}")
                if supplemented:
                    logger.info(
                        f"Supplemented missing nutrition fields from ingredient "
                        f"estimates: {', '.join(supplemented)}"
                    )
        if micro_nutrition_data is None:
            logger.warning("⚠️ Using FALLBACK micronutrient data - API call may have failed!")
            logger.warning("[COSYLAB API FALLBACK] RecipeDB micronutrient endpoint did not return data for /analyze-full. Using zeroed fallback values.")
            micro_nutrition_data = {
                "vitamins": {k: 0.0 for k in [
                    "vitamin_a", "vitamin_c", "vitamin_d", "vitamin_e",
                    "vitamin_k", "thiamin", "riboflavin", "niacin",
                    "vitamin_b6", "folate", "vitamin_b12",
                ]},
                "minerals": {k: 0.0 for k in [
                    "calcium", "iron", "magnesium", "phosphorus",
                    "potassium", "zinc", "selenium",
                ]},
            }

        # ------------------------------------------------------------------
        # 2. Generate original risk profile
        # ------------------------------------------------------------------
        logger.info(f"Calculating health score with nutrition data: {nutrition_data}")
        original_score = health_scorer.calculate_health_score(
            nutrition_data, micro_nutrition_data
        )
        logger.info(f"📊 Original score: {original_score.score:.2f} ({original_score.rating})")
        logger.info(f"📊 Score breakdown: {original_score.breakdown}")
        
        # Check if using fallback data
        if nutrition_data.get("calories") == 250.0 and nutrition_data.get("protein") == 10.0:
            logger.warning("⚠️ WARNING: Health score calculated using FALLBACK nutrition data!")
            logger.warning("[COSYLAB API FALLBACK] CosyLab API is not returning nutrition data. Check COSYLAB_API_KEY and network connectivity to cosylab.iiitd.edu.in.")

        # ------------------------------------------------------------------
        # 3. Detect allergens
        # ------------------------------------------------------------------
        detected_allergen_objs = allergen_detector.detect_allergens(ingredients)
        detected_allergens = [a.to_dict() for a in detected_allergen_objs]

        # Check user-declared allergen sensitivities against ingredients
        user_allergen_warnings = []
        if request.allergens:
            for allergen_cat in request.allergens:
                matching = allergen_detector.build_allergen_response(
                    [allergen_cat], ingredients
                )
                for m in matching:
                    m["user_declared"] = True
                    user_allergen_warnings.append(m)

        # ------------------------------------------------------------------
        # 4. Flag avoidance ingredients
        # ------------------------------------------------------------------
        flagged_avoid = []
        if request.avoid_ingredients:
            from app.utils.helpers import normalize_ingredient_name
            avoid_normalized = {
                normalize_ingredient_name(a) for a in request.avoid_ingredients
            }
            for ing in ingredients:
                if normalize_ingredient_name(ing) in avoid_normalized:
                    flagged_avoid.append(ing)

        # ------------------------------------------------------------------
        # 5. Query RecipeDB for a similar (healthier) recipe
        # ------------------------------------------------------------------
        similar_recipe = None
        if recipe_id:
            try:
                recs = recommendation_engine.find_similar_recipes(
                    recipe_id=recipe_id,
                    min_health_score=settings.MIN_HEALTHY_SCORE,
                    limit=1,
                )
                if recs:
                    similar_recipe = recs[0].to_dict()
            except Exception as e:
                logger.warning(f"Similar recipe search failed: {e}")
                logger.warning("[COSYLAB API FALLBACK] RecipeDB similar-recipe search failed for /analyze-full. Skipping healthier recipe suggestion.")

        # ------------------------------------------------------------------
        # 6-9. Swap discovery + scoring (LLM agent or rule-based fallback)
        # ------------------------------------------------------------------
        risky_ingredients = []
        swap_suggestions = []
        improved_score = None
        improved_ingredients = None
        score_improvement = None
        explanation = None
        agent_metadata = None

        if llm_swap_agent:
            # ── LLM Agent Path ─────────────────────────────────────────
            try:
                logger.info("🚨 [LLM] Running LLM swap agent (Gemini) for ingredient analysis and swap generation")
                agent_result = llm_swap_agent.run(
                    recipe_name=request.recipe_name,
                    ingredients=ingredients,
                    nutrition_data=nutrition_data,
                    original_health_score=original_score.score,
                    allergens=request.allergens,
                    avoid_ingredients=request.avoid_ingredients,
                )

                risky_ingredients = agent_result.to_risky_ingredients_dicts()
                swap_suggestions = agent_result.to_swap_suggestions_dicts()

                if agent_result.substitutions:
                    improved_ingredients = agent_result.apply_to_ingredients(ingredients)
                    projected_nutrition = agent_result.estimate_nutrition_changes(
                        nutrition_data, len(ingredients)
                    )
                    improved_score = health_scorer.calculate_health_score(
                        projected_nutrition, micro_nutrition_data
                    )
                    score_improvement = round(
                        improved_score.score - original_score.score, 2
                    )
                else:
                    # Agent found no substitutions
                    improved_score = original_score
                    improved_ingredients = ingredients
                    score_improvement = 0.0

                explanation = agent_result.generate_explanation(
                    original_score, improved_score or original_score
                )
                agent_metadata = agent_result.to_metadata_dict()

                logger.info(
                    f"🚨 [LLM] Agent done: {len(agent_result.substitutions)} subs, "
                    f"confidence={agent_result.overall_confidence:.2f}, "
                    f"completeness={agent_result.data_completeness}"
                )
            except Exception as e:
                logger.error(f"LLM agent failed, falling back to rules: {e}", exc_info=True)
                logger.warning("[LLM FALLBACK] Gemini LLM swap agent failed for /analyze-full. Falling back to rule-based swap engine.")
                # Reset so we fall through to the rule-based path
                risky_ingredients = []
                swap_suggestions = []
                improved_score = None
                improved_ingredients = None
                score_improvement = None
                explanation = None
                agent_metadata = None

        # ── Rule-Based Fallback (also used when agent is disabled) ────
        if not swap_suggestions:
            # 6. Identify unhealthy ingredients
            risky_objs = ingredient_analyzer.identify_risky_ingredients(
                ingredients, nutrition_data
            )
            if request.avoid_ingredients:
                already_flagged = {r.name.lower() for r in risky_objs}
                extra_risky = ingredient_analyzer.create_risky_from_list(
                    [a for a in request.avoid_ingredients if a.lower() not in already_flagged],
                    ingredients,
                )
                risky_objs.extend(extra_risky)
            risky_ingredients = [r.to_dict() for r in risky_objs]

            # 7. Generate swap suggestions via FlavorDB
            # Now returns ALL ranked alternatives per risky ingredient, not just top-1
            swap_objects_for_projection = []
            for risky_obj in risky_objs:
                try:
                    flavor_profile = flavordb_service.get_flavor_profile_by_ingredient(
                        risky_obj.name
                    )
                    substitutes = swap_engine.find_substitutes(
                        risky_obj.name, flavor_profile, original_score.score,
                        recipe_ingredients=ingredients,
                    )
                    if substitutes:
                        top = substitutes[0]
                        swap_dict = {
                            "original": risky_obj.name,
                            "substitute": top.to_dict(),
                            # All alternatives for the frontend to display
                            "alternatives": [s.to_dict() for s in substitutes],
                            "accepted": True,
                        }
                        swap_suggestions.append(swap_dict)
                        swap_objects_for_projection.append(swap_dict)
                except Exception as e:
                    logger.warning(f"Swap generation failed for {risky_obj.name}: {e}")

            # 8. Calculate improved risk profile
            if swap_objects_for_projection:
                improved_ingredients = swap_engine.apply_swaps(
                    ingredients, swap_objects_for_projection
                )
                projected_nutrition = swap_engine.estimate_nutrition_with_swaps(
                    nutrition_data, swap_objects_for_projection,
                    total_ingredients=len(ingredients),
                )
                improved_score = health_scorer.calculate_health_score(
                    projected_nutrition, micro_nutrition_data
                )
                score_improvement = round(improved_score.score - original_score.score, 2)
            else:
                improved_score = original_score
                improved_ingredients = ingredients
                score_improvement = 0.0

            # 9. Generate explanation (use LLM if available, else template)
            use_llm_explain = bool(settings.GEMINI_API_KEY)
            explainer = LLMExplainer(
                use_templates=not use_llm_explain,
                api_key=settings.GEMINI_API_KEY if use_llm_explain else None,
            )
            if swap_objects_for_projection and improved_score:
                if use_llm_explain:
                    explanation = explainer.generate_llm_swap_explanation(
                        swap_objects_for_projection,
                        original_score,
                        improved_score,
                        ingredients,
                    )
                else:
                    explanation = explainer.generate_swap_explanation(
                        swap_objects_for_projection, original_score, improved_score
                    )
            else:
                explanation = explainer.generate_health_explanation(
                    original_score.score, original_score.rating, nutrition_data
                )

        # ------------------------------------------------------------------
        # Build response
        # ------------------------------------------------------------------
        return FullAnalysisResponse(
            recipe_name=request.recipe_name,
            ingredients=ingredients,
            source=source,
            original_health_score=original_score,
            nutrition=nutrition_data,
            micro_nutrition=micro_nutrition_data,
            detected_allergens=detected_allergens,
            user_allergen_warnings=user_allergen_warnings,
            flagged_avoid_ingredients=flagged_avoid,
            similar_recipe=similar_recipe,
            risky_ingredients=risky_ingredients,
            swap_suggestions=swap_suggestions,
            improved_health_score=improved_score,
            improved_ingredients=improved_ingredients,
            score_improvement=score_improvement,
            explanation=explanation,
            agent_metadata=agent_metadata,
            used_llm_fallback=used_llm_fallback,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in full analysis: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Full analysis failed: {str(e)}",
        )


@app.post("/swap", response_model=IngredientSwapResponse)
async def swap_ingredients(request: IngredientSwapRequest) -> IngredientSwapResponse:
    """
    Workflow 2: Generate ingredient swap suggestions with flavor preservation.
    
    This endpoint handles ingredient substitution:
    1. Identifies risky/unhealthy ingredients (auto-detect or user-specified)
    2. Fetches flavor profiles from FlavorDB for each risky ingredient
    3. Finds healthier alternatives with similar flavor profiles
    4. Ranks substitutes by flavor match and health improvement
    5. Calculates projected health score with all swaps applied
    6. Optionally generates explanation using LLM
    
    Args:
        request: IngredientSwapRequest containing recipe_id and optional
                 ingredients_to_swap list
        
    Returns:
        IngredientSwapResponse: Swap suggestions, scores, and explanation
        
    Raises:
        HTTPException: 404 if recipe not found, 500 if processing fails
    """
    try:
        logger.info(f"Processing swap request for recipe ID: {request.recipe_id}")
        
        # Step 1: Fetch recipe data
        recipe_data = recipedb_service.get_recipe_by_id(request.recipe_id)
        if not recipe_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recipe with ID '{request.recipe_id}' not found"
            )
        
        ingredients = recipe_data.get("ingredients", [])
        
        # Step 2: Fetch current nutrition data
        nutrition_data = recipedb_service.fetch_nutrition_info(request.recipe_id)
        micro_nutrition_data = recipedb_service.fetch_micro_nutrition_info(request.recipe_id)
        
        # Step 3: Calculate original health score
        original_score = health_scorer.calculate_health_score(
            nutrition_data,
            micro_nutrition_data
        )
        
        # Step 4: Identify risky ingredients
        if request.ingredients_to_swap:
            # Use user-specified ingredients
            logger.info(f"Using user-specified ingredients to swap: {request.ingredients_to_swap}")
            risky_ingredients = ingredient_analyzer.create_risky_from_list(
                request.ingredients_to_swap,
                ingredients
            )
        else:
            # Auto-detect risky ingredients
            logger.info("Auto-detecting risky ingredients")
            risky_ingredients = ingredient_analyzer.identify_risky_ingredients(
                ingredients,
                nutrition_data
            )
        
        if not risky_ingredients:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No risky ingredients found to swap"
            )
        
        # Step 5: Generate swaps for each risky ingredient
        logger.info(f"Generating swaps for {len(risky_ingredients)} ingredients")
        swaps = []
        
        for risky_ingredient in risky_ingredients:
            # Fetch flavor profile from FlavorDB
            flavor_profile = flavordb_service.get_flavor_profile_by_ingredient(
                risky_ingredient.name
            )
            
            # Find and rank substitutes
            substitutes = swap_engine.find_substitutes(
                risky_ingredient.name,
                flavor_profile,
                original_score.score
            )
            
            if substitutes:
                # Use the top-ranked substitute
                swaps.append({
                    "original": risky_ingredient.name,
                    "substitute": substitutes[0],
                    "accepted": False
                })
        
        # Step 6: Apply all swaps and calculate projected score
        logger.info("Calculating projected health score with swaps")
        new_ingredients = swap_engine.apply_swaps(
            ingredients,
            swaps
        )
        
        # Estimate new nutrition data (simplified - use proportional adjustment)
        projected_nutrition = swap_engine.estimate_nutrition_with_swaps(
            nutrition_data,
            swaps
        )
        
        projected_score = health_scorer.calculate_health_score(
            projected_nutrition,
            micro_nutrition_data
        )
        
        # Step 7: Generate explanation (optional)
        explanation = None
        if llm_explainer and settings.USE_LLM_EXPLANATIONS:
            logger.info("Generating LLM explanation")
            explanation = llm_explainer.generate_swap_explanation(
                swaps,
                original_score,
                projected_score
            )
        
        # Build response
        response = IngredientSwapResponse(
            recipe=recipe_data,
            risky_ingredients=risky_ingredients,
            swaps=swaps,
            original_score=original_score,
            projected_score=projected_score,
            explanation=explanation,
            workflow="ingredient_swap"
        )
        
        logger.info(
            f"Swap suggestions generated. Original score: {original_score.score}, "
            f"Projected score: {projected_score.score}"
        )
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating swaps: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate ingredient swaps: {str(e)}"
        )


@app.get("/recommendations/{recipe_id}", response_model=List[RecipeRecommendation])
async def get_recommendations(
    recipe_id: str,
    limit: int = 5
) -> List[RecipeRecommendation]:
    """
    Fetch similar healthy recipe recommendations for a given recipe.
    
    This endpoint can be called independently to get recipe recommendations
    without performing a full analysis.
    
    Args:
        recipe_id: The ID of the recipe to find recommendations for
        limit: Maximum number of recommendations to return (default: 5)
        
    Returns:
        List[RecipeRecommendation]: List of similar healthy recipes
        
    Raises:
        HTTPException: 404 if recipe not found, 500 if processing fails
    """
    try:
        logger.info(f"Fetching recommendations for recipe ID: {recipe_id}")
        
        # Verify recipe exists
        recipe_data = recipedb_service.get_recipe_by_id(recipe_id)
        if not recipe_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recipe with ID '{recipe_id}' not found"
            )
        
        # Fetch recommendations
        recommendations = recommendation_engine.find_similar_recipes(
            recipe_id=recipe_id,
            min_health_score=settings.MIN_HEALTHY_SCORE,
            limit=min(limit, settings.MAX_RECOMMENDATIONS)
        )
        
        logger.info(f"Found {len(recommendations)} recommendations")
        return recommendations
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching recommendations: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch recommendations: {str(e)}"
        )


@app.post("/quick-meals", response_model=QuickMealResponse)
async def get_quick_meals(filters: QuickMealFilters) -> QuickMealResponse:
    """
    Get quick, healthy, practical meal suggestions filtered by preparation time,
    ingredient count, cost, and hostel-friendliness.
    
    This endpoint is designed to help users (especially students in hostels/PGs)
    find fast, budget-friendly recipes that prevent cravings by keeping blood
    sugar stable and removing the excuse of "nothing to eat".
    
    Psychological Benefits:
    - Prevents extreme hunger by providing quick meal options
    - Reduces decision fatigue with simple, clear choices
    - Makes healthy eating more convenient than junk food
    - Removes barriers to healthy eating (time, cost, equipment)
    
    Args:
        filters: QuickMealFilters with criteria:
            - max_prep_time: Maximum preparation time (default: 5 minutes)
            - max_ingredients: Maximum number of ingredients (default: 3)
            - max_cost: Maximum cost per serving in INR (default: ₹100)
            - hostel_friendly: Filter for hostel/PG-friendly recipes (default: True)
            - cuisine: Optional cuisine filter
            - diet_type: Optional diet type filter
            
    Returns:
        QuickMealResponse: List of quick meal recipes with practical information
        
    Raises:
        HTTPException: 500 if filtering fails
        
    Example:
        POST /quick-meals
        {
            "max_prep_time": 5,
            "max_ingredients": 3,
            "max_cost": 100,
            "hostel_friendly": true,
            "diet_type": "vegetarian"
        }
    """
    try:
        logger.info(f"Fetching quick meals with filters: {filters}")
        
        # Get filtered quick meals
        response = quick_meal_service.filter_quick_meals(
            filters=filters,
            limit=5  # Return up to 5 meals
        )
        
        logger.info(f"Found {response.total_found} quick meals matching criteria")
        return response
        
    except Exception as e:
        logger.error(f"Error fetching quick meals: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch quick meals: {str(e)}"
        )


@app.post("/recalculate", response_model=RecalculateResponse)
async def recalculate_score(request: RecalculateRequest) -> RecalculateResponse:
    """
    Recalculate health score with user-accepted ingredient swaps.

    This endpoint allows users to iteratively refine their recipe by
    accepting or rejecting individual swap suggestions. It recalculates
    the health score based only on the swaps the user has accepted.

    Args:
        request: RecalculateRequest containing recipe_name, original_ingredients,
                and accepted_swaps mapping

    Returns:
        RecalculateResponse: Updated health score and nutrition data

    Raises:
        HTTPException: 500 if processing fails
    """
    try:
        logger.info(
            f"Recalculating score for recipe: {request.recipe_name} "
            f"with {len(request.accepted_swaps)} accepted swaps"
        )

        original_ingredients = request.original_ingredients

        # Step 1: Convert accepted_swaps mapping to swap objects for processing
        # accepted_swaps is Dict[original_ingredient, substitute_ingredient]
        swap_objects_for_projection = []
        for original, substitute in request.accepted_swaps.items():
            swap_objects_for_projection.append({
                "original": original,
                "substitute": {"name": substitute},
                "accepted": True,
            })

        logger.info(f"Processing {len(swap_objects_for_projection)} accepted swaps")

        # Step 2: Try to get nutrition data from RecipeDB
        # If not found, use fallback estimates
        nutrition_data = None
        micro_nutrition_data = None
        try:
            recipe_data = recipedb_service.fetch_recipe_by_name(request.recipe_name)
            if recipe_data:
                recipe_id = recipe_data.get("id")
                nutrition_data = recipedb_service.fetch_nutrition_info(recipe_id)
                micro_nutrition_data = recipedb_service.fetch_micro_nutrition_info(recipe_id)
        except Exception as e:
            logger.warning(f"Could not fetch recipe from RecipeDB: {e}")
            logger.warning("[COSYLAB API FALLBACK] RecipeDB recipe fetch failed for /recalculate. Will use hardcoded fallback nutrition.")

        # Fallback nutrition estimates if not found
        if nutrition_data is None:
            logger.warning("[COSYLAB API FALLBACK] RecipeDB nutrition data unavailable for /recalculate. Using ingredient-based fallback values.")
            from app.utils.helpers import estimate_nutrition_from_ingredients
            nutrition_data = estimate_nutrition_from_ingredients(original_ingredients)
        else:
            # Supplement missing negative-factor fields from ingredient estimates
            _NEGATIVE_KEYS = ["sugar", "sodium", "saturated_fat", "trans_fat",
                              "cholesterol", "carbs", "fiber"]
            missing = [k for k in _NEGATIVE_KEYS if nutrition_data.get(k, 0) == 0]
            if missing and original_ingredients:
                from app.utils.helpers import estimate_nutrition_from_ingredients
                est = estimate_nutrition_from_ingredients(original_ingredients)
                supplemented = []
                for k in missing:
                    if est.get(k, 0) > 0:
                        nutrition_data[k] = est[k]
                        supplemented.append(f"{k}={est[k]}")
                if supplemented:
                    logger.info(
                        f"Supplemented missing nutrition fields for /recalculate: "
                        f"{', '.join(supplemented)}"
                    )
        if micro_nutrition_data is None:
            logger.warning("[COSYLAB API FALLBACK] RecipeDB micronutrient data unavailable for /recalculate. Using zeroed fallback values.")
            micro_nutrition_data = {
            }

        # Step 3: Calculate original score for comparison
        original_score = health_scorer.calculate_health_score(
            nutrition_data, micro_nutrition_data
        )

        # Step 4: Apply swaps and calculate new ingredients
        new_ingredients = swap_engine.apply_swaps(
            original_ingredients,
            swap_objects_for_projection
        )

        # Step 5: Estimate new nutrition data with accepted swaps
        projected_nutrition = swap_engine.estimate_nutrition_with_swaps(
            nutrition_data,
            swap_objects_for_projection,
            total_ingredients=len(original_ingredients)
        )

        # Step 6: Calculate new health score
        new_score = health_scorer.calculate_health_score(
            projected_nutrition,
            micro_nutrition_data
        )

        # Step 7: Calculate score improvement
        score_improvement = round(new_score.score - original_score.score, 2)

        # Step 8: Detect allergens in final ingredients
        detected_allergen_objs = allergen_detector.detect_allergens(new_ingredients)
        detected_allergens = [a.to_dict() if hasattr(a, 'to_dict') else a for a in detected_allergen_objs]

        # Step 9: Check user-declared allergens
        user_allergen_warnings = []
        if request.allergens:
            for allergen_cat in request.allergens:
                matching = allergen_detector.build_allergen_response(
                    [allergen_cat], new_ingredients
                )
                for m in matching:
                    m["user_declared"] = True
                    user_allergen_warnings.append(m)

        # Step 10: Flag avoidance ingredients
        flagged_avoid = []
        if request.avoid_ingredients:
            from app.utils.helpers import normalize_ingredient_name
            avoid_normalized = {
                normalize_ingredient_name(a) for a in request.avoid_ingredients
            }
            for ing in new_ingredients:
                if normalize_ingredient_name(ing) in avoid_normalized:
                    flagged_avoid.append(ing)

        # Step 11: Generate explanation
        explainer = LLMExplainer(use_templates=True)
        explanation = explainer.generate_swap_explanation(
            swap_objects_for_projection, original_score, new_score
        )

        # Build response
        response = RecalculateResponse(
            recipe_name=request.recipe_name,
            final_ingredients=new_ingredients,
            final_health_score=new_score,
            nutrition=projected_nutrition,
            micro_nutrition=micro_nutrition_data,
            detected_allergens=detected_allergens,
            user_allergen_warnings=user_allergen_warnings,
            flagged_avoid_ingredients=flagged_avoid,
            total_score_improvement=score_improvement,
            explanation=explanation
        )

        logger.info(
            f"Recalculation complete. Original score: {original_score.score}, "
            f"New score: {new_score.score}, Improvement: {score_improvement}"
        )
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recalculating score: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to recalculate score: {str(e)}"
        )


@app.get("/debug/cosylab-test")
async def cosylab_debug_test():
    """
    Debug endpoint to compare CosyLab API requests with Postman.
    
    Returns the exact URL, headers (key redacted), params, and raw response
    from CosyLab RecipeDB. Use this to align the app with your working
    Postman request.
    
    Compare:
    1. URL structure (base URL + endpoint path)
    2. Header name and format (x-api-key vs Authorization vs api_key query param)
    3. Query parameter names (title vs recipe_title, etc.)
    """
    base_url = (settings.RECIPEDB_BASE_URL or "").rstrip("/")
    use_bearer = getattr(settings, "RECIPEDB_USE_BEARER_AUTH", False)
    org_endpoint = getattr(settings, "RECIPEDB_ORG_ENDPOINT", "recipesinfo") or "recipesinfo"
    if use_bearer:
        endpoint = org_endpoint
        params = {"page": 1, "limit": 10}
    else:
        endpoint = "recipe_by_title"
        params = {"title": "pasta"}
    url = f"{base_url}/{endpoint}"
    api_key = settings.COSYLAB_API_KEY or ""
    headers = {"Accept": "application/json"}
    if api_key:
        if use_bearer:
            headers["Authorization"] = f"Bearer {api_key}"
        else:
            headers["x-api-key"] = api_key
    
    debug = {
        "request": {
            "method": "GET",
            "url": url,
            "params": params,
            "headers": {k: ("***REDACTED***" if k.lower() in ("x-api-key", "authorization") else v) for k, v in headers.items()},
            "api_key_loaded": bool(api_key),
            "api_key_length": len(api_key),
        },
        "response": None,
    }
    
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        debug["response"] = {
            "status_code": resp.status_code,
            "reason": resp.reason,
            "headers": dict(resp.headers),
            "body_preview": resp.text[:1000] if resp.text else None,
        }
        try:
            debug["response"]["body_json"] = resp.json()
        except Exception:
            pass
    except requests.exceptions.RequestException as e:
        debug["response"] = {"error": str(e), "error_type": type(e).__name__}
    
    return debug


@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring and deployment.

    Returns:
        dict: Service health status including API connectivity and configuration
    """
    api_key_configured = settings.COSYLAB_API_KEY is not None and len(settings.COSYLAB_API_KEY) > 0
    recipedb_status = recipedb_service.check_availability()
    flavordb_status = flavordb_service.check_availability()
    
    warnings = []
    if not api_key_configured:
        warnings.append("⚠️ CosyLab API key not configured - API calls will fail!")
    if not recipedb_status:
        warnings.append("⚠️ RecipeDB API not responding - check connectivity!")
    if not flavordb_status:
        warnings.append("⚠️ FlavorDB API not responding - check connectivity!")
    
    return {
        "status": "healthy",
        "service": "recipe-health-swap-api",
        "api_configuration": {
            "cosylab_api_key_configured": api_key_configured,
            "api_key_length": len(settings.COSYLAB_API_KEY) if settings.COSYLAB_API_KEY else 0,
            "recipedb_base_url": settings.RECIPEDB_BASE_URL,
            "flavordb_base_url": settings.FLAVORDB_BASE_URL,
        },
        "api_connectivity": {
            "recipedb_available": recipedb_status,
            "flavordb_available": flavordb_status,
        },
        "warnings": warnings if warnings else None
    }


# ==================== New User Data Endpoints ====================

@app.post("/recipes")
async def save_recipe(recipe_data: Dict):
    """
    Save an analyzed recipe to the user's collection.

    Args:
        recipe_data: Recipe analysis data including name, health score, ingredients

    Returns:
        dict: Saved recipe with ID
    """
    try:
        recipe_id = str(uuid.uuid4())
        saved_recipe = {
            "id": recipe_id,
            "name": recipe_data.get("recipe_name", "Unknown Recipe"),
            "health_score": recipe_data.get("original_health_score", {}).get("score", 0),
            "rating": recipe_data.get("original_health_score", {}).get("rating", "Unknown"),
            "ingredients": recipe_data.get("ingredients", []),
            "improved_score": recipe_data.get("improved_health_score", {}).get("score"),
            "detected_allergens": recipe_data.get("detected_allergens", []),
            "swap_suggestions": recipe_data.get("swap_suggestions", []),
            "timestamp": str(uuid.uuid4())
        }
        user_recipes.append(saved_recipe)
        logger.info(f"Saved recipe: {saved_recipe['name']}")
        return saved_recipe
    except Exception as e:
        logger.error(f"Error saving recipe: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save recipe: {str(e)}"
        )


@app.get("/recipes")
async def get_recipes():
    """
    Get all analyzed recipes for the current user.

    Returns:
        list: List of saved recipes with their health scores
    """
    try:
        logger.info(f"Fetching {len(user_recipes)} recipes")
        return user_recipes
    except Exception as e:
        logger.error(f"Error fetching recipes: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch recipes: {str(e)}"
        )


@app.get("/dashboard/stats")
async def get_dashboard_stats():
    """
    Get aggregated user statistics for the dashboard.

    Returns:
        dict: Stats including total recipes, average health score, profile count
    """
    try:
        total_recipes = len(user_recipes)
        avg_health_score = 0.0
        max_improved_score = 0.0

        if total_recipes > 0:
            scores = [r["health_score"] for r in user_recipes if "health_score" in r]
            avg_health_score = sum(scores) / len(scores) if scores else 0.0
            max_improved_score = max([r.get("improved_score", 0) for r in user_recipes if r.get("improved_score")], default=0.0)

        total_profiles = len(user_profiles)

        stats = {
            "total_recipes": total_recipes,
            "average_health_score": round(avg_health_score, 1),
            "best_improved_score": round(max_improved_score, 1),
            "total_profiles": total_profiles,
            "app_status": "running"
        }

        logger.info(f"Dashboard stats: {stats}")
        return stats
    except Exception as e:
        logger.error(f"Error fetching dashboard stats: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch dashboard stats: {str(e)}"
        )


@app.post("/profiles")
async def create_profile(profile_data: Dict):
    """
    Create and save a user profile.

    Args:
        profile_data: Profile information (name, age, archetype, allergens, avoid_ingredients)

    Returns:
        dict: Created profile with ID
    """
    global profile_counter
    try:
        profile_counter_val = len(user_profiles) + 1
        profile_id = str(profile_counter_val)

        saved_profile = {
            "id": profile_id,
            "name": profile_data.get("name", "Default Profile"),
            "age": profile_data.get("age"),
            "archetype": profile_data.get("archetype", "General"),
            "allergens": profile_data.get("allergens", []),
            "avoid_ingredients": profile_data.get("avoid_ingredients", []),
            "created_at": str(uuid.uuid4())
        }

        user_profiles[profile_id] = saved_profile
        logger.info(f"Created profile: {saved_profile['name']} (ID: {profile_id})")
        return saved_profile
    except Exception as e:
        logger.error(f"Error creating profile: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create profile: {str(e)}"
        )


@app.get("/profiles")
async def get_profiles():
    """
    Get all user profiles.

    Returns:
        list: List of all user profiles
    """
    try:
        profiles_list = list(user_profiles.values())
        logger.info(f"Fetching {len(profiles_list)} profiles")
        return profiles_list
    except Exception as e:
        logger.error(f"Error fetching profiles: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch profiles: {str(e)}"
        )


@app.get("/profiles/{profile_id}")
async def get_profile(profile_id: str):
    """
    Get a specific user profile by ID.

    Args:
        profile_id: The ID of the profile to retrieve

    Returns:
        dict: The requested profile

    Raises:
        HTTPException: 404 if profile not found
    """
    try:
        if profile_id not in user_profiles:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Profile with ID '{profile_id}' not found"
            )

        profile = user_profiles[profile_id]
        logger.info(f"Fetched profile: {profile['name']}")
        return profile
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching profile: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch profile: {str(e)}"
        )


@app.put("/profiles/{profile_id}")
async def update_profile(profile_id: str, profile_data: Dict):
    """
    Update an existing user profile.

    Args:
        profile_id: The ID of the profile to update
        profile_data: Updated profile fields (name, age, archetype, allergens, avoid_ingredients)

    Returns:
        dict: The updated profile
    """
    try:
        if profile_id not in user_profiles:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Profile with ID '{profile_id}' not found"
            )
        profile = user_profiles[profile_id]
        profile["name"] = profile_data.get("name", profile["name"])
        profile["age"] = profile_data.get("age", profile.get("age"))
        profile["archetype"] = profile_data.get("archetype", profile.get("archetype", "General"))
        profile["allergens"] = profile_data.get("allergens", profile.get("allergens", []))
        profile["avoid_ingredients"] = profile_data.get("avoid_ingredients", profile.get("avoid_ingredients", []))
        logger.info(f"Updated profile: {profile['name']} (ID: {profile_id})")
        return profile
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile: {str(e)}"
        )


@app.delete("/profiles/{profile_id}")
async def delete_profile(profile_id: str):
    """
    Delete a user profile.

    Args:
        profile_id: The ID of the profile to delete

    Returns:
        dict: Confirmation message
    """
    try:
        if profile_id not in user_profiles:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Profile with ID '{profile_id}' not found"
            )
        name = user_profiles[profile_id].get("name", "Unknown")
        del user_profiles[profile_id]
        logger.info(f"Deleted profile: {name} (ID: {profile_id})")
        return {"message": "Profile deleted successfully", "id": profile_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting profile: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete profile: {str(e)}"
        )


# ==================== Craving Replacement Endpoints ====================

@app.post("/cravings/replace", response_model=CravingReplacement)
async def craving_replace(request: CravingRequest) -> CravingReplacement:
    """
    Process a craving and return personalised healthier replacements.

    Returns quick combos (2-3 ingredient ideas) and full RecipeDB recipes,
    along with a psychological insight and science explanation.
    """
    try:
        logger.info(f"Craving replacement request: {request.craving_text}")
        result = craving_service.process_craving(request)
        return result
    except Exception as e:
        logger.error(f"Error processing craving: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process craving: {str(e)}",
        )


@app.post("/cravings/patterns", response_model=CravingPatternAnalysis)
async def craving_patterns(history: List[CravingHistoryEntry]) -> CravingPatternAnalysis:
    """
    Analyse craving history (sent from frontend localStorage) and return
    detected patterns, weekly summary, and encouragement messages.
    """
    try:
        logger.info(f"Craving pattern analysis for {len(history)} entries")
        result = craving_service.analyze_patterns(history)

        # Optionally enrich with LLM insights
        if _craving_llm and result.weekly_summary:
            try:
                llm_patterns = _craving_llm.generate_craving_pattern_insights(
                    result.weekly_summary
                )
                if llm_patterns:
                    for desc in llm_patterns:
                        result.patterns.append(
                            CravingPattern(
                                pattern_description=desc,
                                frequency=0,
                                trigger="ai-detected",
                                top_time="various",
                            )
                        )
            except Exception as e:
                logger.warning(f"LLM pattern enrichment failed: {e}")

        return result
    except Exception as e:
        logger.error(f"Error analysing craving patterns: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyse craving patterns: {str(e)}",
        )


if __name__ == "__main__":
    import uvicorn

    # Run the application
    # For development only - use uvicorn command in production
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )