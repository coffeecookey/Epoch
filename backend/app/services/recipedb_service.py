"""
RecipeDB API service wrapper.

This module provides a clean interface for interacting with the RecipeDB API.
It handles all HTTP communication, response parsing, error handling, and
optional caching for frequently accessed data.

RecipeDB API Base URL: https://cosylab.iiitd.edu.in/recipedb/search_recipedb

Available endpoints:
- Recipe By Title
- Recipe Nutrition Info
- Recipe Micro Nutrition Info
- Recipe By Calories
- Recipe By Protein Range
- Recipe By Cuisine
- Recipe By Recipe Diet
- Recipe By Id
"""

import requests
import logging
from typing import Dict, List, Optional
from functools import lru_cache
import time

from app.config import settings

# Configure logging
logger = logging.getLogger(__name__)


class RecipeDBService:
    """
    Service class for interacting with RecipeDB API.
    
    Provides methods for fetching recipe data, nutrition information,
    and searching recipes by various criteria.
    
    Attributes:
        base_url: Base URL for RecipeDB API
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts for failed requests
    """
    
    def __init__(self):
        """Initialize RecipeDB service with configuration."""
        self.base_url = settings.RECIPEDB_BASE_URL
        self.timeout = settings.API_TIMEOUT
        self.api_key = settings.COSYLAB_API_KEY
        self.max_retries = 3
        self.retry_delay = 1  # seconds

        logger.info(f"RecipeDB service initialized with base URL: {self.base_url}")
        if self.api_key:
            logger.info(f"✅ CosyLab API key is configured (length: {len(self.api_key)} chars)")
        else:
            logger.warning("⚠️ CosyLab API key is NOT configured! Set COSYLAB_API_KEY in .env file")
            logger.warning("⚠️ API requests may fail without authentication")
    
    def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        retry_count: int = 0
    ) -> Optional[Dict]:
        """
        Make HTTP GET request to RecipeDB API with retry logic.
        
        Handles connection errors, timeouts, and HTTP errors with automatic
        retry mechanism. Implements exponential backoff for retries.
        
        Args:
            endpoint: API endpoint path (e.g., "recipe_by_title")
            params: Query parameters as dictionary
            retry_count: Current retry attempt number (for internal use)
            
        Returns:
            Dict: Parsed JSON response from API, or None if request fails
            
        Raises:
            No exceptions raised - errors are logged and None is returned
        """
        url = f"{self.base_url}/{endpoint}"
        
        try:
            logger.info(f"🌐 Making API request to {url} with params: {params}")
            logger.info(f"🔑 API Key present: {'Yes' if self.api_key else 'No'}")
            
            headers = {"Accept": "application/json"}
            if self.api_key:
                headers["x-api-key"] = self.api_key
            else:
                logger.warning("⚠️ No API key configured! Request may fail if API requires authentication.")

            response = requests.get(
                url,
                params=params,
                timeout=self.timeout,
                headers=headers,
            )
            
            logger.info(f"📡 API Response Status: {response.status_code}")
            
            # Check for HTTP errors
            response.raise_for_status()
            
            # Parse JSON response
            data = response.json()
            logger.info(f"✅ Request successful. Response size: {len(str(data))} bytes")
            logger.debug(f"Response data preview: {str(data)[:200]}...")
            
            return data
            
        except requests.exceptions.Timeout:
            logger.warning(f"Request timeout for {url}")
            return self._handle_retry(endpoint, params, retry_count, "timeout")
            
        except requests.exceptions.ConnectionError:
            logger.warning(f"Connection error for {url}")
            return self._handle_retry(endpoint, params, retry_count, "connection_error")
            
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else None
            logger.error(f"❌ HTTP error for {url}: Status {status_code if status_code else 'unknown'}")
            if e.response:
                try:
                    error_body = e.response.text[:500]
                    logger.error(f"Error response body: {error_body}")
                except:
                    pass
            # Don't retry on 4xx errors (client errors)
            if status_code and 400 <= status_code < 500:
                logger.error(f"❌ Client error (4xx) - likely API key issue or invalid request. Not retrying.")
                return None
            return self._handle_retry(endpoint, params, retry_count, "http_error")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {url}: {str(e)}")
            return self._handle_retry(endpoint, params, retry_count, "request_exception")
            
        except ValueError as e:
            logger.error(f"Failed to parse JSON response from {url}: {str(e)}")
            return None
    
    def _handle_retry(
        self,
        endpoint: str,
        params: Optional[Dict],
        retry_count: int,
        error_type: str
    ) -> Optional[Dict]:
        """
        Handle retry logic for failed requests.
        
        Implements exponential backoff strategy for retries.
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            retry_count: Current retry attempt
            error_type: Type of error that occurred
            
        Returns:
            Dict: Result of retry attempt, or None if max retries exceeded
        """
        if retry_count < self.max_retries:
            wait_time = self.retry_delay * (2 ** retry_count)  # Exponential backoff
            logger.info(
                f"Retrying request (attempt {retry_count + 1}/{self.max_retries}) "
                f"after {wait_time}s due to {error_type}"
            )
            time.sleep(wait_time)
            return self._make_request(endpoint, params, retry_count + 1)
        else:
            logger.error(f"Max retries ({self.max_retries}) exceeded for {endpoint}")
            return None
    
    def fetch_recipe_by_name(self, recipe_name: str) -> Optional[Dict]:
        """
        Search for a recipe by its name using RecipeDB "Recipe By Title" endpoint.
        
        This method searches for recipes matching the given name. If multiple
        recipes match, it returns the first result. The search is case-insensitive.
        
        Args:
            recipe_name: Name of the recipe to search for (e.g., "Chicken Curry")
            
        Returns:
            Dict: Recipe data containing id, name, ingredients, cuisine, etc.
                  Returns None if recipe not found or request fails.
                  
        Example return structure:
            {
                "id": "123",
                "name": "Chicken Curry",
                "ingredients": ["chicken", "curry powder", "onion"],
                "cuisine": "Indian",
                "diet_type": "non-vegetarian"
            }
        """
        logger.info(f"Fetching recipe by name: {recipe_name}")
        
        params = {"title": recipe_name}
        response = self._make_request("recipe_by_title", params)
        
        if not response:
            logger.warning(f"No recipe found for name: {recipe_name}")
            return None
        
        # Handle response format (assuming API returns list or single object)
        if isinstance(response, list) and len(response) > 0:
            recipe = response[0]
        elif isinstance(response, dict):
            recipe = response
        else:
            logger.warning(f"Unexpected response format for recipe: {recipe_name}")
            return None
        
        logger.info(f"Found recipe: {recipe.get('name', 'Unknown')} (ID: {recipe.get('id', 'Unknown')})")
        return recipe
    
    def fetch_nutrition_info(self, recipe_id: str) -> Dict:
        """
        Get macronutrient data for a recipe using "Recipe Nutrition Info" endpoint.
        
        Fetches comprehensive macronutrient information including calories,
        protein, carbohydrates, fats, sodium, sugar, and cholesterol.
        
        Args:
            recipe_id: Unique identifier for the recipe
            
        Returns:
            Dict: Macronutrient data with the following structure:
                {
                    "calories": float,
                    "protein": float (grams),
                    "carbs": float (grams),
                    "fat": float (grams),
                    "saturated_fat": float (grams),
                    "trans_fat": float (grams),
                    "sodium": float (mg),
                    "sugar": float (grams),
                    "cholesterol": float (mg),
                    "fiber": float (grams)
                }
                
        Raises:
            ValueError: If recipe_id is invalid or nutrition data unavailable
        """
        logger.info(f"Fetching nutrition info for recipe ID: {recipe_id}")
        
        params = {"id": recipe_id}
        response = self._make_request("recipe_nutrition_info", params)
        
        if not response:
            raise ValueError(f"Failed to fetch nutrition info for recipe ID: {recipe_id}")
        
        # Parse and standardize nutrition data
        nutrition_data = self._parse_nutrition_response(response)
        
        logger.debug(f"Nutrition data retrieved: {nutrition_data.get('calories', 0)} calories")
        return nutrition_data
    
    def _parse_nutrition_response(self, response: Dict) -> Dict:
        """
        Parse and standardize nutrition API response.

        Handles different possible response formats (including case variants)
        and ensures consistent output structure with default values for missing fields.

        Args:
            response: Raw API response

        Returns:
            Dict: Standardized nutrition data
        """
        def _get(d: Dict, *keys, default=0):
            """Get value by any of the keys (case-insensitive)."""
            d_lower = {str(k).lower(): v for k, v in d.items()} if isinstance(d, dict) else {}
            for key in keys:
                k = str(key).lower()
                if k in d_lower:
                    try:
                        return float(d_lower[k])
                    except (TypeError, ValueError):
                        pass
            return default

        # Handle nested response structure if present
        data = response.get("nutrition", response)
        if not isinstance(data, dict):
            data = {}

        return {
            "calories": _get(data, "calories", default=0),
            "protein": _get(data, "protein", default=0),
            "carbs": _get(data, "carbohydrates", "carbs", default=0),
            "fat": _get(data, "fat", "total_fat", default=0),
            "saturated_fat": _get(data, "saturated_fat", default=0),
            "trans_fat": _get(data, "trans_fat", default=0),
            "sodium": _get(data, "sodium", default=0),
            "sugar": _get(data, "sugar", "sugars", default=0),
            "cholesterol": _get(data, "cholesterol", default=0),
            "fiber": _get(data, "fiber", "dietary_fiber", default=0)
        }
    
    def fetch_micro_nutrition_info(self, recipe_id: str) -> Dict:
        """
        Get micronutrient data for a recipe using "Recipe Micro Nutrition Info" endpoint.
        
        Fetches vitamin and mineral content for comprehensive nutritional analysis.
        
        Args:
            recipe_id: Unique identifier for the recipe
            
        Returns:
            Dict: Micronutrient data with structure:
                {
                    "vitamins": {
                        "vitamin_a": float (IU or mcg),
                        "vitamin_c": float (mg),
                        "vitamin_d": float (IU or mcg),
                        "vitamin_e": float (mg),
                        "vitamin_k": float (mcg),
                        "thiamin": float (mg),
                        "riboflavin": float (mg),
                        "niacin": float (mg),
                        "vitamin_b6": float (mg),
                        "folate": float (mcg),
                        "vitamin_b12": float (mcg)
                    },
                    "minerals": {
                        "calcium": float (mg),
                        "iron": float (mg),
                        "magnesium": float (mg),
                        "phosphorus": float (mg),
                        "potassium": float (mg),
                        "zinc": float (mg),
                        "selenium": float (mcg)
                    }
                }
                
        Raises:
            ValueError: If recipe_id is invalid or micronutrient data unavailable
        """
        logger.info(f"Fetching micronutrient info for recipe ID: {recipe_id}")
        
        params = {"id": recipe_id}
        response = self._make_request("recipe_micro_nutrition_info", params)
        
        if not response:
            raise ValueError(f"Failed to fetch micronutrient info for recipe ID: {recipe_id}")
        
        # Parse and standardize micronutrient data
        micro_data = self._parse_micro_nutrition_response(response)
        
        logger.debug(f"Micronutrient data retrieved with {len(micro_data.get('vitamins', {}))} vitamins")
        return micro_data
    
    def _parse_micro_nutrition_response(self, response: Dict) -> Dict:
        """
        Parse and standardize micronutrient API response.
        
        Args:
            response: Raw API response
            
        Returns:
            Dict: Standardized micronutrient data
        """
        # Handle nested response structure
        data = response.get("micronutrients", response)
        
        vitamins = data.get("vitamins", {})
        minerals = data.get("minerals", {})
        
        return {
            "vitamins": {
                "vitamin_a": float(vitamins.get("vitamin_a", 0)),
                "vitamin_c": float(vitamins.get("vitamin_c", 0)),
                "vitamin_d": float(vitamins.get("vitamin_d", 0)),
                "vitamin_e": float(vitamins.get("vitamin_e", 0)),
                "vitamin_k": float(vitamins.get("vitamin_k", 0)),
                "thiamin": float(vitamins.get("thiamin", vitamins.get("vitamin_b1", 0))),
                "riboflavin": float(vitamins.get("riboflavin", vitamins.get("vitamin_b2", 0))),
                "niacin": float(vitamins.get("niacin", vitamins.get("vitamin_b3", 0))),
                "vitamin_b6": float(vitamins.get("vitamin_b6", 0)),
                "folate": float(vitamins.get("folate", vitamins.get("vitamin_b9", 0))),
                "vitamin_b12": float(vitamins.get("vitamin_b12", 0))
            },
            "minerals": {
                "calcium": float(minerals.get("calcium", 0)),
                "iron": float(minerals.get("iron", 0)),
                "magnesium": float(minerals.get("magnesium", 0)),
                "phosphorus": float(minerals.get("phosphorus", 0)),
                "potassium": float(minerals.get("potassium", 0)),
                "zinc": float(minerals.get("zinc", 0)),
                "selenium": float(minerals.get("selenium", 0))
            }
        }
    
    def search_by_calories(
        self,
        min_cal: int,
        max_cal: int,
        limit: int = 10
    ) -> List[Dict]:
        """
        Find recipes within a specific calorie range using "Recipe By Calories" endpoint.
        
        Useful for finding similar recipes with comparable calorie content
        for the recommendation engine.
        
        Args:
            min_cal: Minimum calories (inclusive)
            max_cal: Maximum calories (inclusive)
            limit: Maximum number of results to return (default: 10)
            
        Returns:
            List[Dict]: List of recipe dictionaries matching calorie criteria.
                        Each dict contains basic recipe info (id, name, calories).
                        Returns empty list if no recipes found.
                        
        Example:
            recipes = service.search_by_calories(200, 400, limit=5)
        """
        logger.info(f"Searching recipes by calories: {min_cal}-{max_cal} (limit: {limit})")
        
        params = {
            "min_calories": min_cal,
            "max_calories": max_cal,
            "limit": limit
        }
        
        response = self._make_request("recipe_by_calories", params)
        
        if not response:
            logger.warning(f"No recipes found in calorie range: {min_cal}-{max_cal}")
            return []
        
        # Ensure response is a list
        recipes = response if isinstance(response, list) else [response]
        
        logger.info(f"Found {len(recipes)} recipes in calorie range")
        return recipes
    
    def search_by_protein(
        self,
        min_protein: float,
        max_protein: float
    ) -> List[Dict]:
        """
        Find recipes within a specific protein range using "Recipe By Protein Range" endpoint.
        
        Useful for finding recipes with similar protein content for recommendations.
        
        Args:
            min_protein: Minimum protein in grams (inclusive)
            max_protein: Maximum protein in grams (inclusive)
            
        Returns:
            List[Dict]: List of recipe dictionaries matching protein criteria.
                        Returns empty list if no recipes found.
                        
        Example:
            recipes = service.search_by_protein(20.0, 35.0)
        """
        logger.info(f"Searching recipes by protein: {min_protein}g-{max_protein}g")
        
        params = {
            "min_protein": min_protein,
            "max_protein": max_protein
        }
        
        response = self._make_request("recipe_by_protein_range", params)
        
        if not response:
            logger.warning(f"No recipes found in protein range: {min_protein}g-{max_protein}g")
            return []
        
        recipes = response if isinstance(response, list) else [response]
        
        logger.info(f"Found {len(recipes)} recipes in protein range")
        return recipes
    
    def search_by_cuisine(self, cuisine: str) -> List[Dict]:
        """
        Find recipes by cuisine type using "Recipe By Cuisine" endpoint.
        
        Useful for finding similar recipes from the same culinary tradition.
        
        Args:
            cuisine: Cuisine type (e.g., "Indian", "Italian", "Mexican", "Chinese")
            
        Returns:
            List[Dict]: List of recipe dictionaries from specified cuisine.
                        Returns empty list if no recipes found.
                        
        Example:
            recipes = service.search_by_cuisine("Indian")
        """
        logger.info(f"Searching recipes by cuisine: {cuisine}")
        
        params = {"cuisine": cuisine}
        response = self._make_request("recipe_by_cuisine", params)
        
        if not response:
            logger.warning(f"No recipes found for cuisine: {cuisine}")
            return []
        
        recipes = response if isinstance(response, list) else [response]
        
        logger.info(f"Found {len(recipes)} recipes for cuisine: {cuisine}")
        return recipes
    
    def search_by_diet(self, diet_type: str) -> List[Dict]:
        """
        Find recipes by diet type using "Recipe By Recipe Diet" endpoint.
        
        Useful for finding recipes that match specific dietary requirements.
        
        Args:
            diet_type: Diet type (e.g., "vegan", "vegetarian", "keto", 
                       "paleo", "gluten-free", "dairy-free")
            
        Returns:
            List[Dict]: List of recipe dictionaries matching diet type.
                        Returns empty list if no recipes found.
                        
        Example:
            recipes = service.search_by_diet("vegan")
        """
        logger.info(f"Searching recipes by diet type: {diet_type}")
        
        params = {"diet": diet_type}
        response = self._make_request("recipe_by_diet", params)
        
        if not response:
            logger.warning(f"No recipes found for diet type: {diet_type}")
            return []
        
        recipes = response if isinstance(response, list) else [response]
        
        logger.info(f"Found {len(recipes)} recipes for diet type: {diet_type}")
        return recipes
    
    @lru_cache(maxsize=100)
    def get_recipe_by_id(self, recipe_id: str) -> Optional[Dict]:
        """
        Fetch complete recipe data by ID using "Recipe By Id" endpoint.
        
        This method is cached to avoid redundant API calls for frequently
        accessed recipes. Cache size is limited to 100 recipes.
        
        Args:
            recipe_id: Unique identifier for the recipe
            
        Returns:
            Dict: Complete recipe data including all fields:
                {
                    "id": str,
                    "name": str,
                    "ingredients": List[str],
                    "cuisine": str,
                    "diet_type": str,
                    "instructions": str,
                    "prep_time": int,
                    "cook_time": int,
                    "servings": int
                }
                Returns None if recipe not found.
                
        Example:
            recipe = service.get_recipe_by_id("12345")
        """
        logger.info(f"Fetching recipe by ID: {recipe_id}")
        
        params = {"id": recipe_id}
        response = self._make_request("recipe_by_id", params)
        
        if not response:
            logger.warning(f"No recipe found for ID: {recipe_id}")
            return None
        
        # Handle nested response if present
        recipe = response.get("recipe", response)
        
        logger.info(f"Retrieved recipe: {recipe.get('name', 'Unknown')}")
        return recipe
    
    def check_availability(self) -> bool:
        """
        Check if RecipeDB API is available and responding.
        
        Used for health checks and monitoring. Makes a simple request
        to verify API connectivity.
        
        Returns:
            bool: True if API is available, False otherwise
        """
        try:
            # Try a simple request to check availability
            response = self._make_request("recipe_by_id", {"id": "1"})
            return response is not None
        except Exception as e:
            logger.error(f"RecipeDB availability check failed: {str(e)}")
            return False
    
    def clear_cache(self):
        """
        Clear the LRU cache for get_recipe_by_id method.
        
        Call this method if you need to force refresh of cached recipe data.
        """
        self.get_recipe_by_id.cache_clear()
        logger.info("RecipeDB cache cleared")