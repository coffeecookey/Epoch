"""
RecipeDB API service wrapper.

Uses the dedicated RecipeDB endpoints so that nutrition and health score are
correctly loaded and updated:

- Recipe By Title (recipe_by_title) – lookup by name
- Recipe By Id (recipe_by_id) – full recipe by ID
- Recipe Nutrition Info (recipe_nutrition_info) – calories, protein, carbs, fat, etc.
- Recipe Micro Nutrition Info (recipe_micro_nutrition_info) – vitamins/minerals

Fallback: when using org API (Bearer), recipesinfo paginated list is used
if the dedicated endpoints are not available. Response payload.data (single
object or list) is unwrapped and parsed; RecipeDB field names (e.g. Protein (g),
Carbohydrate, by difference (g), Total lipid (fat) (g)) are mapped to the
standard keys expected by the health scorer and swap pipeline.
"""

import re
import threading
import time
import requests
import logging
from typing import Dict, List, Optional, Tuple, Union
from functools import lru_cache

from app.config import settings

# Stopwords to ignore when matching recipe name by words (order doesn't matter)
_RECIPE_NAME_STOPWORDS = frozenset({"a", "an", "and", "the", "with", "for", "or", "in", "on", "to"})

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
        self.base_url = (settings.RECIPEDB_BASE_URL or "").rstrip("/")
        rdb_timeout = getattr(settings, "RECIPEDB_TIMEOUT", None)
        self.timeout = (rdb_timeout if rdb_timeout and rdb_timeout > 0 else None) or settings.API_TIMEOUT
        self.api_key = settings.COSYLAB_API_KEY
        self.use_bearer = getattr(settings, "RECIPEDB_USE_BEARER_AUTH", False)
        self.org_endpoint = getattr(settings, "RECIPEDB_ORG_ENDPOINT", "recipesinfo") or "recipesinfo"
        fallback = getattr(settings, "RECIPEDB_FALLBACK_BASE_URL", None)
        self.fallback_base_url = (fallback or "").strip().rstrip("/") or None
        self.max_retries = 3
        self.retry_delay = 1  # seconds
        # Rate limiting to avoid IP blocking
        self._rate_limit_delay = max(0.0, getattr(settings, "RECIPEDB_RATE_LIMIT_DELAY", 0.5))
        self._max_search_pages = max(1, min(20, getattr(settings, "RECIPEDB_MAX_SEARCH_PAGES", 5)))
        self._rate_limit_lock = threading.Lock()
        self._last_request_time = 0.0

        logger.info(
            f"RecipeDB service initialized with base URL: {self.base_url} "
            f"(Bearer: {self.use_bearer}, org endpoint: {self.org_endpoint}, "
            f"rate_limit_delay: {self._rate_limit_delay}s, max_search_pages: {self._max_search_pages})"
        )
        if self.api_key:
            logger.info(f"CosyLab API key is configured (length: {len(self.api_key)} chars)")
        else:
            logger.warning("CosyLab API key is NOT configured! Set COSYLAB_API_KEY in .env file")
            logger.warning("API requests may fail without authentication")
    
    def _wait_rate_limit(self) -> None:
        """Enforce minimum delay between requests to avoid IP blocking. Thread-safe."""
        if self._rate_limit_delay <= 0:
            return
        with self._rate_limit_lock:
            now = time.monotonic()
            wait = max(0.0, self._rate_limit_delay - (now - self._last_request_time))
            self._last_request_time = now + wait
        if wait > 0:
            time.sleep(wait)
            logger.debug(f"Rate limit: waited {wait:.2f}s before RecipeDB request")

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
        Respects RECIPEDB_RATE_LIMIT_DELAY between requests.
        
        Args:
            endpoint: API endpoint path (e.g., "recipe_by_title")
            params: Query parameters as dictionary
            retry_count: Current retry attempt number (for internal use)
            
        Returns:
            Dict: Parsed JSON response from API, or None if request fails
            
        Raises:
            No exceptions raised - errors are logged and None is returned
        """
        self._wait_rate_limit()
        url = f"{self.base_url}/{endpoint}"
        
        try:
            logger.info(f"Making API request to {url} with params: {params}")
            logger.info(f"API Key present: {'Yes' if self.api_key else 'No'}")
            
            headers = {"Accept": "application/json"}
            if self.api_key:
                if self.use_bearer:
                    headers["Authorization"] = f"Bearer {self.api_key}"
                else:
                    headers["x-api-key"] = self.api_key
            else:
                logger.warning("No API key configured! Request may fail if API requires authentication.")

            response = requests.get(
                url,
                params=params,
                timeout=self.timeout,
                headers=headers,
            )
            
            logger.info(f"API Response Status: {response.status_code}")
            
            # Check for HTTP errors
            response.raise_for_status()
            
            # Parse JSON response
            data = response.json()
            logger.info(f"Request successful. Response size: {len(str(data))} bytes")
            logger.debug(f"Response data preview: {str(data)[:200]}...")
            
            return data
            
        except requests.exceptions.Timeout:
            logger.warning(f"Request timeout for {url}")
            out = self._try_fallback(url, endpoint, params, headers)
            if out is not None:
                return out
            return self._handle_retry(endpoint, params, retry_count, "timeout")
            
        except requests.exceptions.ConnectionError:
            logger.warning(f"Connection error for {url}")
            out = self._try_fallback(url, endpoint, params, headers)
            if out is not None:
                return out
            return self._handle_retry(endpoint, params, retry_count, "connection_error")
            
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else None
            logger.error(f"HTTP error for {url}: Status {status_code if status_code else 'unknown'}")
            if e.response:
                try:
                    error_body = e.response.text[:500]
                    logger.error(f"Error response body: {error_body}")
                except:
                    pass
            # 429 Rate Limit: retry with longer delay (respect Retry-After if present)
            if status_code == 429:
                retry_after = None
                if e.response and "Retry-After" in e.response.headers:
                    try:
                        retry_after = int(e.response.headers["Retry-After"])
                    except (ValueError, TypeError):
                        pass
                wait = retry_after if retry_after else (10 + self.retry_delay * (2 ** retry_count))
                logger.warning(f"Rate limited (429). Retrying after {wait}s")
                time.sleep(wait)
                return self._handle_retry(endpoint, params, retry_count, "rate_limit")
            # Don't retry on other 4xx errors (client errors)
            if status_code and 400 <= status_code < 500:
                logger.error(
                    f"RecipeDB request failed with {status_code} at {url}. "
                    "Check COSYLAB_API_KEY, RECIPEDB_BASE_URL, and RECIPEDB_USE_BEARER_AUTH. Not retrying."
                )
                return None
            return self._handle_retry(endpoint, params, retry_count, "http_error")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {url}: {str(e)}")
            return self._handle_retry(endpoint, params, retry_count, "request_exception")
            
        except ValueError as e:
            logger.error(f"Failed to parse JSON response from {url}: {str(e)}")
            return None
    
    @staticmethod
    def _recipe_title_matches_query(query: str, title: str) -> Tuple[str, bool]:
        """
        Check how well query matches recipe title. Returns (match_kind, is_match).
        match_kind: "exact" (substring), "all_words", "partial", or "" (no match).
        is_match: True if we should consider this recipe a hit.
        """
        q = (query or "").strip().lower()
        t = (title or "").lower()
        if not q or not t:
            return "", False
        # 1. Exact substring (already supported)
        if q in t or t in q:
            return "exact", True
        # 2. Word-based: extract significant words from query (min 2 chars, not stopwords)
        words = [w for w in re.split(r"\W+", q) if len(w) >= 2 and w not in _RECIPE_NAME_STOPWORDS]
        if not words:
            return "", False
        in_title = sum(1 for w in words if w in t)
        if in_title == len(words):
            return "all_words", True
        if in_title >= 1:
            return "partial", True
        return "", False

    def _extract_payload_data(self, response: Optional[Dict]) -> Optional[Union[Dict, List]]:
        """
        Unwrap payload.data from API response. Handles both single object and list
        (e.g. Recipe By Id returns payload.data = object, Recipe By Title may return list).
        """
        if not response or not isinstance(response, dict):
            return None
        payload = response.get("payload")
        if isinstance(payload, dict):
            return payload.get("data")
        for key in ("data", "result", "recipe"):
            val = response.get(key)
            if val is not None:
                return val
        return None

    def _extract_recipe_list(self, response: Optional[Union[Dict, List]]) -> List[Dict]:
        """Extract list of recipes from org API response (handles multiple shapes)."""
        if not response:
            return []
        if isinstance(response, list):
            return response
        if not isinstance(response, dict):
            return []
        # payload.data (common org API shape)
        payload = response.get("payload")
        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return [data]  # single recipe object (e.g. Recipe By Id)
        # Top-level data or recipes
        for key in ("data", "recipes", "results", "items"):
            val = response.get(key)
            if isinstance(val, list):
                return val
            if isinstance(val, dict):
                return [val]
        return []

    def _recipesinfo_request(
        self,
        params: Optional[Dict] = None,
        retry_count: int = 0
    ) -> Optional[List[Dict]]:
        """
        Call org API list endpoint (recipesinfo or recipes). Returns list of recipe dicts or [].
        Tries configured endpoint first, then 'recipes' if that returns nothing.
        """
        p = dict(params) if params else {}
        p.setdefault("page", 1)
        p.setdefault("limit", 50)
        response = self._make_request(self.org_endpoint, p, retry_count)
        data = self._extract_recipe_list(response)
        if data:
            return data
        # Try alternate endpoint name (e.g. API uses "recipes" not "recipesinfo")
        if self.org_endpoint != "recipes":
            response = self._make_request("recipes", p, retry_count)
            data = self._extract_recipe_list(response)
            if data:
                logger.info(f"RecipeDB org API responded on endpoint 'recipes' (got {len(data)} items)")
                return data
        if response is not None and not data:
            logger.warning("RecipeDB response was not empty but no recipe list could be extracted. Keys: %s", list(response.keys()) if isinstance(response, dict) else "n/a")
        return []

    def _org_recipe_to_standard(self, r: Dict) -> Dict:
        """Convert org API recipe format to standard app format."""
        rid = r.get("Recipe_id") or r.get("_id") or r.get("id") or ""
        return {
            "id": str(rid),
            "name": r.get("Recipe_title") or r.get("name") or r.get("title") or "",
            "ingredients": r.get("ingredients") or [],
            "cuisine": r.get("cuisine") or r.get("Region") or r.get("region") or "",
            "diet_type": r.get("diet_type") or r.get("diet") or "",
            "instructions": r.get("instructions") or "",
            "prep_time": int(r.get("prep_time", 0) or 0),
            "cook_time": int(r.get("cook_time", 0) or 0),
            "servings": int(r.get("servings", 0) or 0),
            "Calories": r.get("Calories"),
            "_raw": r,
        }

    def _normalize_recipe(self, r: Dict) -> Dict:
        """Normalize any recipe dict to standard format (id, name, ingredients, etc.)."""
        if not r:
            return {}
        return self._org_recipe_to_standard(r)

    def _try_fallback(
        self,
        _original_url: str,
        endpoint: str,
        params: Optional[Dict],
        headers: Dict[str, str],
    ) -> Optional[Dict]:
        """If RECIPEDB_FALLBACK_BASE_URL is set, try one request with it. Return data or None."""
        if not self.fallback_base_url:
            return None
        url = f"{self.fallback_base_url}/{endpoint}"
        try:
            logger.info(f"Trying fallback URL: {url}")
            response = requests.get(url, params=params, timeout=self.timeout, headers=headers)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Fallback request succeeded (response size: {len(str(data))} bytes)")
            return data
        except Exception as e:
            logger.warning(f"Fallback request failed: {e}")
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
        q = (recipe_name or "").strip()
        if not q:
            logger.warning("Empty recipe name")
            return None

        # 1. Try dedicated endpoint: Recipe By Title (works with both Bearer and x-api-key)
        params = {"title": recipe_name.strip()}
        response = self._make_request("recipe_by_title", params)
        if response is not None:
            # Unwrap payload.data (single object or list)
            data = self._extract_payload_data(response) if isinstance(response, dict) else response
            if isinstance(data, list) and len(data) > 0:
                recipe = data[0]
            elif isinstance(data, dict) and (data.get("Recipe_id") or data.get("id") or data.get("_id")):
                recipe = data
            elif isinstance(response, list) and len(response) > 0:
                recipe = response[0]
            elif isinstance(response, dict) and not response.get("payload"):
                recipe = response
            else:
                recipe = None
            if recipe:
                out = self._org_recipe_to_standard(recipe) if self.use_bearer else self._normalize_recipe(recipe)
                logger.info(f"Found recipe via Recipe By Title: {out.get('name')} (ID: {out.get('id')})")
                return out

        # 2. Fallback: org API recipesinfo (paginated list + client-side search)
        if self.use_bearer:
            best_all_words: Optional[Dict] = None
            best_partial: Optional[Dict] = None
            for page in range(1, self._max_search_pages + 1):
                data = self._recipesinfo_request({"page": page, "limit": 200})
                if not data:
                    break
                for r in data:
                    title = r.get("Recipe_title") or r.get("name") or ""
                    kind, is_match = self._recipe_title_matches_query(q, title)
                    if not is_match:
                        continue
                    out = self._org_recipe_to_standard(r)
                    if kind == "exact":
                        logger.info(f"Found recipe (exact): {out.get('name')} (ID: {out.get('id')}) on page {page}")
                        return out
                    if kind == "all_words" and best_all_words is None:
                        best_all_words = out
                    if kind == "partial" and best_partial is None:
                        best_partial = out
            result = best_all_words or best_partial
            if result:
                logger.info(f"Found recipe (word match): {result.get('name')} (ID: {result.get('id')})")
                return result
            logger.warning(f"No recipe found for name: {recipe_name} (searched {self._max_search_pages} pages)")
            return None

        logger.warning(f"No recipe found for name: {recipe_name}")
        return None
    
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

        # 1. Try dedicated endpoint: Recipe Nutrition Info (same path for Bearer and x-api-key)
        params = {"id": recipe_id}
        response = self._make_request("recipe_nutrition_info", params)
        if response is not None:
            # Unwrap payload.data (single object) or use response as nutrition object
            raw = self._extract_payload_data(response) if isinstance(response, dict) else response
            if raw is None:
                raw = response
            if isinstance(raw, dict):
                nutrition_data = self._parse_nutrition_response(raw)
                # Ensure calories from Calories or energy (kcal) when present
                cal_val = raw.get("Calories") or raw.get("calories") or raw.get("Energy (kcal)")
                if cal_val is not None:
                    try:
                        nutrition_data["calories"] = float(str(cal_val).replace(",", ""))
                    except (TypeError, ValueError):
                        pass
                if nutrition_data.get("calories", 0) > 0 or nutrition_data.get("protein", 0) > 0 or nutrition_data.get("carbs", 0) > 0 or nutrition_data.get("fat", 0) > 0:
                    logger.info(f"Nutrition from Recipe Nutrition Info: {nutrition_data.get('calories', 0)} cal")
                    return nutrition_data

        # 2. Fallback: org API recipesinfo (scan pages for this recipe_id)
        if self.use_bearer:
            for page in range(1, self._max_search_pages + 1):
                data = self._recipesinfo_request({"page": page, "limit": 200})
                if not data:
                    continue
                for r in data:
                    rid = str(r.get("Recipe_id") or r.get("_id") or r.get("id") or "")
                    if rid != str(recipe_id):
                        continue
                    cal_str = r.get("Calories") or r.get("calories") or "0"
                    try:
                        cal = float(str(cal_str).replace(",", ""))
                    except (TypeError, ValueError):
                        cal = 0.0
                    nutrition_data = self._parse_nutrition_response(r)
                    nutrition_data["calories"] = cal
                    logger.info(f"Nutrition from recipesinfo fallback: {cal} cal")
                    return nutrition_data
            raise ValueError(f"Failed to fetch nutrition info for recipe ID: {recipe_id}")

        raise ValueError(f"Failed to fetch nutrition info for recipe ID: {recipe_id}")
    
    def _parse_nutrition_response(self, response: Dict) -> Dict:
        """
        Parse and standardize nutrition API response.

        Handles different possible response formats (including case variants)
        and RecipeDB org API field names (e.g. "Protein (g)", "Carbohydrate, by difference (g)",
        "Total lipid (fat) (g)", "Energy (kcal)"). Ensures consistent output for health scorer
        and swap pipeline.

        Args:
            response: Raw API response (e.g. recipe object from RecipeDB payload.data)

        Returns:
            Dict: Standardized nutrition data (calories, protein, carbs, fat, etc.)
        """
        def _get(d: Dict, *keys, default=0):
            """Get value by any of the keys (case-insensitive)."""
            d_lower = {str(k).lower(): v for k, v in d.items()} if isinstance(d, dict) else {}
            for key in keys:
                k = str(key).lower()
                if k in d_lower:
                    try:
                        v = d_lower[k]
                        if v is None:
                            continue
                        return float(str(v).replace(",", ""))
                    except (TypeError, ValueError):
                        pass
            return default

        # Handle nested response structure if present (e.g. response.nutrition vs flat recipe)
        data = response.get("nutrition", response)
        if not isinstance(data, dict):
            data = {}

        # RecipeDB org API uses: Calories, Protein (g), Carbohydrate, by difference (g),
        # Total lipid (fat) (g), Energy (kcal). Map all to standard keys for health_scorer.
        return {
            "calories": _get(data, "calories", "energy (kcal)", default=0),
            "protein": _get(data, "protein", "protein (g)", default=0),
            "carbs": _get(
                data,
                "carbohydrates",
                "carbs",
                "carbohydrate, by difference (g)",
                default=0,
            ),
            "fat": _get(data, "fat", "total_fat", "total lipid (fat) (g)", default=0),
            "saturated_fat": _get(data, "saturated_fat", default=0),
            "trans_fat": _get(data, "trans_fat", default=0),
            "sodium": _get(data, "sodium", default=0),
            "sugar": _get(data, "sugar", "sugars", default=0),
            "cholesterol": _get(data, "cholesterol", default=0),
            "fiber": _get(data, "fiber", "dietary_fiber", default=0),
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

        # Try dedicated endpoint: Recipe Micro Nutrition Info
        params = {"id": recipe_id}
        response = self._make_request("recipe_micro_nutrition_info", params)
        if response is not None:
            raw = self._extract_payload_data(response) if isinstance(response, dict) else response
            if raw is None:
                raw = response
            if isinstance(raw, dict):
                micro_data = self._parse_micro_nutrition_response(raw)
                logger.debug(f"Micronutrient data from API: {len(micro_data.get('vitamins', {}))} vitamins")
                return micro_data

        # Org API or no micro endpoint: return empty structure (health scorer accepts zeros)
        return self._parse_micro_nutrition_response({})
    
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
        
        if self.use_bearer:
            data = self._recipesinfo_request({"page": 1, "limit": limit * 2})
            if not data:
                return []
            out = []
            for r in data:
                try:
                    c = float(str(r.get("Calories") or 0).replace(",", ""))
                except (TypeError, ValueError):
                    c = 0
                if min_cal <= c <= max_cal:
                    out.append(self._org_recipe_to_standard(r))
                    if len(out) >= limit:
                        break
            logger.info(f"Found {len(out)} recipes in calorie range")
            return out

        params = {"min_calories": min_cal, "max_calories": max_cal, "limit": limit}
        response = self._make_request("recipe_by_calories", params)
        
        if not response:
            logger.warning(f"No recipes found in calorie range: {min_cal}-{max_cal}")
            return []
        
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
        
        if self.use_bearer:
            data = self._recipesinfo_request({"page": 1, "limit": 50})
            recipes = [self._org_recipe_to_standard(r) for r in (data or [])]
            logger.info(f"Found {len(recipes)} recipes (org API: no protein filter)")
            return recipes

        params = {"min_protein": min_protein, "max_protein": max_protein}
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
        
        if self.use_bearer:
            data = self._recipesinfo_request({"page": 1, "limit": 50})
            recipes = [self._org_recipe_to_standard(r) for r in (data or [])]
            logger.info(f"Found {len(recipes)} recipes (org API: no cuisine filter)")
            return recipes

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
        
        if self.use_bearer:
            data = self._recipesinfo_request({"page": 1, "limit": 50})
            recipes = [self._org_recipe_to_standard(r) for r in (data or [])]
            logger.info(f"Found {len(recipes)} recipes (org API: no diet filter)")
            return recipes

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

        # 1. Try dedicated endpoint: Recipe By Id
        params = {"id": recipe_id}
        response = self._make_request("recipe_by_id", params)
        if response is not None:
            data = self._extract_payload_data(response) if isinstance(response, dict) else response
            if data is None:
                data = response.get("recipe", response)
            if isinstance(data, dict) and (data.get("Recipe_id") or data.get("id") or data.get("_id")):
                out = self._org_recipe_to_standard(data)
                logger.info(f"Retrieved recipe via Recipe By Id: {out.get('name')} (ID: {out.get('id')})")
                return out
            if isinstance(data, list) and len(data) > 0:
                out = self._org_recipe_to_standard(data[0])
                logger.info(f"Retrieved recipe via Recipe By Id: {out.get('name')}")
                return out

        # 2. Fallback: org API recipesinfo scan
        if self.use_bearer:
            for page in range(1, self._max_search_pages + 1):
                data = self._recipesinfo_request({"page": page, "limit": 200})
                if not data:
                    continue
                for r in data:
                    rid = str(r.get("Recipe_id") or r.get("_id") or r.get("id") or "")
                    if rid == str(recipe_id):
                        out = self._org_recipe_to_standard(r)
                        logger.info(f"Retrieved recipe from recipesinfo: {out.get('name')}")
                        return out
            logger.warning(f"No recipe found for ID: {recipe_id}")
            return None

        logger.warning(f"No recipe found for ID: {recipe_id}")
        return None
    
    def check_availability(self) -> bool:
        """
        Check if RecipeDB API is available and responding.
        
        Used for health checks and monitoring. Makes a simple request
        to verify API connectivity.
        
        Returns:
            bool: True if API is available, False otherwise
        """
        try:
            if self.use_bearer:
                data = self._recipesinfo_request({"page": 1, "limit": 1})
                return data is not None
            response = self._make_request("recipe_by_id", {"id": "1"})
            return response is not None
        except Exception as e:
            logger.error(f"RecipeDB availability check failed: {str(e)}")
            return False
    
    def search_by_utensils(self, utensils: str) -> List[Dict]:
        """
        Find recipes by required utensils using "Recipe By Utensils" endpoint.
        
        Useful for filtering recipes based on available equipment.
        
        Args:
            utensils: Utensil/equipment name (e.g., "pan", "microwave", "no-cook")
            
        Returns:
            List[Dict]: List of recipe dictionaries requiring specified utensils.
                        Returns empty list if no recipes found.
                        
        Example:
            recipes = service.search_by_utensils("microwave")
        """
        logger.info(f"Searching recipes by utensils: {utensils}")
        
        if self.use_bearer:
            data = self._recipesinfo_request({"page": 1, "limit": 50})
            recipes = [self._org_recipe_to_standard(r) for r in (data or [])]
            logger.info(f"Found {len(recipes)} recipes (org API: no utensils filter)")
            return recipes

        params = {"utensils": utensils}
        response = self._make_request("recipe_by_utensils", params)
        
        if not response:
            logger.warning(f"No recipes found for utensils: {utensils}")
            return []
        
        recipes = response if isinstance(response, list) else [response]
        
        logger.info(f"Found {len(recipes)} recipes for utensils: {utensils}")
        return recipes
    
    def search_by_method(self, method: str) -> List[Dict]:
        """
        Find recipes by cooking method using "Recipe By Recipes Method" endpoint.
        
        Useful for filtering by preparation style (e.g., "no-cook", "microwave").
        
        Args:
            method: Cooking method (e.g., "no-cook", "bake", "fry", "microwave")
            
        Returns:
            List[Dict]: List of recipe dictionaries using specified method.
                        Returns empty list if no recipes found.
                        
        Example:
            recipes = service.search_by_method("no-cook")
        """
        logger.info(f"Searching recipes by method: {method}")
        
        if self.use_bearer:
            data = self._recipesinfo_request({"page": 1, "limit": 50})
            recipes = [self._org_recipe_to_standard(r) for r in (data or [])]
            logger.info(f"Found {len(recipes)} recipes (org API: no method filter)")
            return recipes

        params = {"method": method}
        response = self._make_request("recipe_by_recipes_method", params)
        
        if not response:
            logger.warning(f"No recipes found for method: {method}")
            return []
        
        recipes = response if isinstance(response, list) else [response]
        
        logger.info(f"Found {len(recipes)} recipes for method: {method}")
        return recipes
    
    def search_by_category(self, category: str) -> List[Dict]:
        """
        Find recipes by category using "Recipe By Category" endpoint.
        
        Useful for finding specific meal types.
        
        Args:
            category: Recipe category (e.g., "quick meals", "snacks")
            
        Returns:
            List[Dict]: List of recipe dictionaries in specified category.
                        Returns empty list if no recipes found.
                        
        Example:
            recipes = service.search_by_category("snacks")
        """
        logger.info(f"Searching recipes by category: {category}")
        
        if self.use_bearer:
            data = self._recipesinfo_request({"page": 1, "limit": 50})
            recipes = [self._org_recipe_to_standard(r) for r in (data or [])]
            logger.info(f"Found {len(recipes)} recipes (org API: no category filter)")
            return recipes

        params = {"category": category}
        response = self._make_request("recipe_by_category", params)
        
        if not response:
            logger.warning(f"No recipes found for category: {category}")
            return []
        
        recipes = response if isinstance(response, list) else [response]
        
        logger.info(f"Found {len(recipes)} recipes for category: {category}")
        return recipes
    
    def search_by_day_category(self, day_category: str) -> List[Dict]:
        """
        Find recipes by day category using "Recipe By Recipe Day Category" endpoint.
        
        Useful for finding meals for specific times of day.
        
        Args:
            day_category: Day category (e.g., "breakfast", "lunch", "dinner", "snack")
            
        Returns:
            List[Dict]: List of recipe dictionaries for specified day category.
                        Returns empty list if no recipes found.
                        
        Example:
            recipes = service.search_by_day_category("breakfast")
        """
        logger.info(f"Searching recipes by day category: {day_category}")
        
        params = {"day_category": day_category}
        response = self._make_request("recipe_by_recipe_day_category", params)
        
        if not response:
            logger.warning(f"No recipes found for day category: {day_category}")
            return []
        
        recipes = response if isinstance(response, list) else [response]
        
        logger.info(f"Found {len(recipes)} recipes for day category: {day_category}")
        return recipes
    
    def search_by_carbs(self, min_carbs: float, max_carbs: float) -> List[Dict]:
        """
        Find recipes within a specific carbohydrate range using "Recipe By Carbs" endpoint.
        
        Useful for finding recipes with specific carb content.
        
        Args:
            min_carbs: Minimum carbohydrates in grams (inclusive)
            max_carbs: Maximum carbohydrates in grams (inclusive)
            
        Returns:
            List[Dict]: List of recipe dictionaries matching carb criteria.
                        Returns empty list if no recipes found.
                        
        Example:
            recipes = service.search_by_carbs(20.0, 50.0)
        """
        logger.info(f"Searching recipes by carbs: {min_carbs}g-{max_carbs}g")
        
        params = {
            "min_carbs": min_carbs,
            "max_carbs": max_carbs
        }
        
        response = self._make_request("recipe_by_carbs", params)
        
        if not response:
            logger.warning(f"No recipes found in carbs range: {min_carbs}g-{max_carbs}g")
            return []
        
        recipes = response if isinstance(response, list) else [response]
        
        logger.info(f"Found {len(recipes)} recipes in carbs range")
        return recipes
    
    def clear_cache(self):
        """
        Clear the LRU cache for get_recipe_by_id method.
        
        Call this method if you need to force refresh of cached recipe data.
        """
        self.get_recipe_by_id.cache_clear()
        logger.info("RecipeDB cache cleared")