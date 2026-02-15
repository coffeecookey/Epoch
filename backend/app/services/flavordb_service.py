"""
FlavorDB API service wrapper.

This module provides a clean interface for interacting with the FlavorDB API.
It handles all HTTP communication for flavor profile queries, molecule data,
and flavor pairing recommendations.

FlavorDB API Base URL: https://cosylab.iiitd.edu.in/flavordb

Available endpoints:
- Entities By Readable Name
- Flavor Pairings by Ingredient
- Molecules By Flavor Profile
- Molecules By Common Name
- Properties By Aroma Threshold Values
- Properties By Taste Threshold
"""

import requests
import logging
from typing import Dict, List, Optional, Set
from functools import lru_cache
import time

from app.config import settings
from app.utils.helpers import normalize_ingredient_name

# Configure logging
logger = logging.getLogger(__name__)


class FlavorDBService:
    """
    Service class for interacting with FlavorDB API.
    
    Provides methods for fetching flavor profiles, molecule data,
    flavor pairings, and calculating flavor similarity between ingredients.
    
    Attributes:
        base_url: Base URL for FlavorDB API
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts for failed requests
    """
    
    def __init__(self):
        """Initialize FlavorDB service with configuration."""
        self.base_url = settings.FLAVORDB_BASE_URL
        self.timeout = settings.API_TIMEOUT
        self.api_key = settings.COSYLAB_API_KEY
        self.max_retries = 3
        self.retry_delay = 1  # seconds

        logger.info(f"FlavorDB service initialized with base URL: {self.base_url}")
    
    def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        retry_count: int = 0
    ) -> Optional[Dict]:
        """
        Make HTTP GET request to FlavorDB API with retry logic.
        
        Handles connection errors, timeouts, and HTTP errors with automatic
        retry mechanism. Implements exponential backoff for retries.
        
        Args:
            endpoint: API endpoint path (e.g., "entities_by_readable_name")
            params: Query parameters as dictionary
            retry_count: Current retry attempt number (for internal use)
            
        Returns:
            Dict: Parsed JSON response from API, or None if request fails
            
        Raises:
            No exceptions raised - errors are logged and None is returned
        """
        url = f"{self.base_url}/{endpoint}"
        
        try:
            logger.debug(f"Making request to {url} with params: {params}")
            
            headers = {"Accept": "application/json"}
            if self.api_key:
                headers["x-api-key"] = self.api_key

            response = requests.get(
                url,
                params=params,
                timeout=self.timeout,
                headers=headers,
            )
            
            # Check for HTTP errors
            response.raise_for_status()
            
            # Parse JSON response
            data = response.json()
            logger.debug(f"Request successful. Response size: {len(str(data))} bytes")
            
            return data
            
        except requests.exceptions.Timeout:
            logger.warning(f"Request timeout for {url}")
            return self._handle_retry(endpoint, params, retry_count, "timeout")
            
        except requests.exceptions.ConnectionError:
            logger.warning(f"Connection error for {url}")
            return self._handle_retry(endpoint, params, retry_count, "connection_error")
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error for {url}: {e.response.status_code}")
            # Don't retry on 4xx errors (client errors)
            if 400 <= e.response.status_code < 500:
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
            logger.warning(f"[COSYLAB API FALLBACK] FlavorDB endpoint '{endpoint}' failed after {self.max_retries} retries ({error_type}). Returning empty result.")
            return None
    
    @lru_cache(maxsize=200)
    def get_flavor_profile_by_ingredient(self, ingredient_name: str) -> Dict:
        """
        Get flavor compounds and profile for an ingredient using "Entities By Readable Name".
        
        Retrieves the complete flavor profile including all flavor molecules,
        their concentrations, and associated flavor descriptors.
        
        Args:
            ingredient_name: Name of the ingredient (e.g., "butter", "vanilla", "garlic")
            
        Returns:
            Dict: Flavor profile data with structure:
                {
                    "ingredient": str,
                    "molecules": [
                        {
                            "name": str,
                            "common_name": str,
                            "concentration": float (optional),
                            "odor_descriptors": List[str]
                        }
                    ],
                    "primary_flavors": List[str],
                    "category": str (e.g., "dairy", "spice", "fruit")
                }
                Returns empty dict with ingredient name if not found.
                
        Example:
            profile = service.get_flavor_profile_by_ingredient("vanilla")
            # Returns molecules like vanillin, etc.
        """
        logger.info(f"Fetching flavor profile for ingredient: {ingredient_name}")
        
        # Extract core ingredient name (removes quantities, prep words, etc.)
        normalized_name = normalize_ingredient_name(ingredient_name)
        if not normalized_name:
            normalized_name = ingredient_name.strip().lower()
        logger.debug(f"FlavorDB query name: '{normalized_name}' (from '{ingredient_name}')")
        
        params = {"name": normalized_name}
        response = self._make_request("entities_by_readable_name", params)
        
        if not response:
            logger.warning(f"No flavor profile found for ingredient: {ingredient_name}")
            logger.warning(f"[COSYLAB API FALLBACK] FlavorDB returned no flavor profile for '{ingredient_name}'. Using empty profile fallback.")
            return {
                "ingredient": ingredient_name,
                "molecules": [],
                "primary_flavors": [],
                "category": "unknown"
            }
        
        # Parse flavor profile response
        flavor_profile = self._parse_flavor_profile_response(response, ingredient_name)
        
        logger.info(
            f"Found {len(flavor_profile.get('molecules', []))} molecules "
            f"for ingredient: {ingredient_name}"
        )
        return flavor_profile
    
    def _parse_flavor_profile_response(
        self,
        response: Dict,
        ingredient_name: str
    ) -> Dict:
        """
        Parse and standardize flavor profile API response.
        
        Handles different possible response formats from FlavorDB and
        extracts relevant flavor molecule information.
        
        Args:
            response: Raw API response
            ingredient_name: Original ingredient name for reference
            
        Returns:
            Dict: Standardized flavor profile data
        """
        # Handle nested response structure
        entity_data = response.get("entity", response)
        
        # Extract molecules
        molecules = []
        molecule_list = entity_data.get("molecules", entity_data.get("flavor_molecules", []))
        
        for molecule in molecule_list:
            molecules.append({
                "name": molecule.get("chemical_name", molecule.get("name", "")),
                "common_name": molecule.get("common_name", ""),
                "concentration": molecule.get("concentration", 0.0),
                "odor_descriptors": molecule.get("odor_descriptors", 
                                                molecule.get("flavor_descriptors", []))
            })
        
        # Extract primary flavor descriptors
        primary_flavors = entity_data.get("flavor_profile", [])
        if isinstance(primary_flavors, str):
            primary_flavors = [primary_flavors]
        
        # Extract category
        category = entity_data.get("category", entity_data.get("food_category", "unknown"))
        
        return {
            "ingredient": ingredient_name,
            "molecules": molecules,
            "primary_flavors": primary_flavors,
            "category": category
        }
    
    @lru_cache(maxsize=200)
    def get_flavor_pairings(self, ingredient_name: str) -> List[str]:
        """
        Find complementary ingredients using "Flavor Pairings by Ingredient" endpoint.
        
        Retrieves a list of ingredients that pair well with the given ingredient
        based on shared flavor compounds and culinary traditions.
        
        Args:
            ingredient_name: Name of the ingredient to find pairings for
            
        Returns:
            List[str]: List of ingredient names that pair well with the input.
                      Returns empty list if no pairings found.
                      
        Example:
            pairings = service.get_flavor_pairings("tomato")
            # Returns: ["basil", "garlic", "olive oil", ...]
        """
        logger.info(f"Fetching flavor pairings for ingredient: {ingredient_name}")
        
        # Extract core ingredient name
        normalized_name = normalize_ingredient_name(ingredient_name)
        if not normalized_name:
            normalized_name = ingredient_name.strip().lower()
        logger.debug(f"FlavorDB pairings query: '{normalized_name}' (from '{ingredient_name}')")
        
        params = {"ingredient": normalized_name}
        response = self._make_request("flavor_pairings", params)
        
        if not response:
            logger.warning(f"No flavor pairings found for ingredient: {ingredient_name}")
            logger.warning(f"[COSYLAB API FALLBACK] FlavorDB returned no pairings for '{ingredient_name}'. Returning empty pairings list.")
            return []
        
        # Parse pairings response
        pairings = self._parse_pairings_response(response)
        
        logger.info(f"Found {len(pairings)} flavor pairings for ingredient: {ingredient_name}")
        return pairings
    
    def _parse_pairings_response(self, response: Dict) -> List[str]:
        """
        Parse and extract ingredient names from pairings API response.
        
        Args:
            response: Raw API response
            
        Returns:
            List[str]: List of paired ingredient names
        """
        # Handle different possible response formats
        if isinstance(response, list):
            # Direct list of ingredient names
            pairings = [str(item) if isinstance(item, str) else item.get("name", "") 
                       for item in response]
        elif isinstance(response, dict):
            # Nested structure
            pairings = response.get("pairings", response.get("ingredients", []))
            if isinstance(pairings, list):
                pairings = [str(item) if isinstance(item, str) else item.get("name", "") 
                           for item in pairings]
        else:
            pairings = []
        
        # Filter out empty strings
        return [p for p in pairings if p]
    
    def get_molecules_by_flavor(self, flavor_profile: str) -> List[Dict]:
        """
        Find molecules associated with a specific flavor using "Molecules By Flavor Profile".
        
        Retrieves all molecules that contribute to a particular flavor descriptor
        (e.g., sweet, umami, floral, citrus).
        
        Args:
            flavor_profile: Flavor descriptor (e.g., "sweet", "umami", "floral", 
                           "citrus", "bitter", "savory")
            
        Returns:
            List[Dict]: List of molecule dictionaries with structure:
                [
                    {
                        "name": str,
                        "common_name": str,
                        "chemical_formula": str,
                        "flavor_contribution": str
                    }
                ]
                Returns empty list if no molecules found.
                
        Example:
            molecules = service.get_molecules_by_flavor("sweet")
        """
        logger.info(f"Fetching molecules for flavor profile: {flavor_profile}")
        
        params = {"flavor": flavor_profile.strip().lower()}
        response = self._make_request("molecules_by_flavor_profile", params)
        
        if not response:
            logger.warning(f"No molecules found for flavor profile: {flavor_profile}")
            return []
        
        # Parse molecules response
        molecules = self._parse_molecules_response(response)
        
        logger.info(f"Found {len(molecules)} molecules for flavor: {flavor_profile}")
        return molecules
    
    def _parse_molecules_response(self, response: Dict) -> List[Dict]:
        """
        Parse and standardize molecules API response.
        
        Args:
            response: Raw API response
            
        Returns:
            List[Dict]: Standardized list of molecule data
        """
        # Handle different response formats
        if isinstance(response, list):
            molecule_list = response
        elif isinstance(response, dict):
            molecule_list = response.get("molecules", [])
        else:
            molecule_list = []
        
        molecules = []
        for molecule in molecule_list:
            if isinstance(molecule, dict):
                molecules.append({
                    "name": molecule.get("chemical_name", molecule.get("name", "")),
                    "common_name": molecule.get("common_name", ""),
                    "chemical_formula": molecule.get("formula", molecule.get("chemical_formula", "")),
                    "flavor_contribution": molecule.get("flavor_descriptor", 
                                                       molecule.get("odor_descriptor", ""))
                })
        
        return molecules
    
    @lru_cache(maxsize=500)
    def get_molecules_by_name(self, common_name: str) -> Dict:
        """
        Get detailed molecule data using "Molecules By Common Name" endpoint.
        
        Retrieves comprehensive information about a specific flavor molecule
        including its chemical properties and flavor contributions.
        
        Args:
            common_name: Common name of the molecule (e.g., "vanillin", "limonene")
            
        Returns:
            Dict: Molecule properties with structure:
                {
                    "name": str,
                    "common_name": str,
                    "chemical_formula": str,
                    "molecular_weight": float,
                    "odor_threshold": float,
                    "taste_threshold": float,
                    "odor_descriptors": List[str],
                    "taste_descriptors": List[str]
                }
                Returns empty dict if molecule not found.
                
        Example:
            molecule = service.get_molecules_by_name("vanillin")
        """
        logger.info(f"Fetching molecule data for: {common_name}")
        
        params = {"name": common_name.strip().lower()}
        response = self._make_request("molecules_by_common_name", params)
        
        if not response:
            logger.warning(f"No molecule data found for: {common_name}")
            return {}
        
        # Parse molecule data
        molecule_data = self._parse_molecule_detail_response(response)
        
        logger.debug(f"Retrieved molecule data for: {common_name}")
        return molecule_data
    
    def _parse_molecule_detail_response(self, response: Dict) -> Dict:
        """
        Parse and standardize detailed molecule API response.
        
        Args:
            response: Raw API response
            
        Returns:
            Dict: Standardized molecule data
        """
        # Handle nested response
        molecule = response.get("molecule", response)
        
        return {
            "name": molecule.get("chemical_name", molecule.get("name", "")),
            "common_name": molecule.get("common_name", ""),
            "chemical_formula": molecule.get("formula", molecule.get("chemical_formula", "")),
            "molecular_weight": float(molecule.get("molecular_weight", 0.0)),
            "odor_threshold": float(molecule.get("odor_threshold", 0.0)),
            "taste_threshold": float(molecule.get("taste_threshold", 0.0)),
            "odor_descriptors": molecule.get("odor_descriptors", []),
            "taste_descriptors": molecule.get("taste_descriptors", [])
        }
    
    def calculate_flavor_similarity(
        self,
        ingredient1: str,
        ingredient2: str
    ) -> float:
        """
        Calculate flavor similarity score between two ingredients.
        
        Compares the flavor profiles of two ingredients based on shared
        flavor molecules, weighted by their concentrations and importance.
        
        Algorithm:
        1. Fetch flavor profiles for both ingredients
        2. Extract molecule sets for each ingredient
        3. Calculate Jaccard similarity of molecule sets
        4. Weight by molecule concentrations if available
        5. Normalize to 0-100 percentage score
        
        Args:
            ingredient1: First ingredient name
            ingredient2: Second ingredient name
            
        Returns:
            float: Similarity percentage (0-100)
                  0 = completely different flavors
                  100 = identical flavor profiles
                  
        Example:
            similarity = service.calculate_flavor_similarity("butter", "ghee")
            # Returns: ~85.5 (high similarity)
            
            similarity = service.calculate_flavor_similarity("butter", "garlic")
            # Returns: ~12.3 (low similarity)
        """
        # Normalize names for display
        norm1 = normalize_ingredient_name(ingredient1) or ingredient1
        norm2 = normalize_ingredient_name(ingredient2) or ingredient2
        logger.info(f"Calculating flavor similarity between: {norm1} and {norm2}")
        
        # Fetch flavor profiles (normalization happens inside)
        profile1 = self.get_flavor_profile_by_ingredient(ingredient1)
        profile2 = self.get_flavor_profile_by_ingredient(ingredient2)
        
        molecules1 = profile1.get("molecules", [])
        molecules2 = profile2.get("molecules", [])
        
        # Handle empty profiles
        if not molecules1 or not molecules2:
            logger.warning(
                f"Cannot calculate similarity - missing flavor data for "
                f"{ingredient1} or {ingredient2}"
            )
            return 0.0
        
        # Calculate similarity
        similarity = self._compute_molecule_similarity(molecules1, molecules2)
        
        logger.info(
            f"Flavor similarity between {ingredient1} and {ingredient2}: {similarity:.2f}%"
        )
        return similarity
    
    def _compute_molecule_similarity(
        self,
        molecules1: List[Dict],
        molecules2: List[Dict]
    ) -> float:
        """
        Compute similarity score between two molecule sets.
        
        Uses weighted Jaccard similarity considering molecule names and
        concentrations.
        
        Args:
            molecules1: List of molecule dicts for first ingredient
            molecules2: List of molecule dicts for second ingredient
            
        Returns:
            float: Similarity score (0-100)
        """
        # Extract molecule names (use common_name if available, else chemical name)
        def get_molecule_name(mol: Dict) -> str:
            return mol.get("common_name") or mol.get("name", "")
        
        # Create sets of molecule names
        set1 = {get_molecule_name(mol).lower() for mol in molecules1 if get_molecule_name(mol)}
        set2 = {get_molecule_name(mol).lower() for mol in molecules2 if get_molecule_name(mol)}
        
        # Handle empty sets
        if not set1 or not set2:
            return 0.0
        
        # Calculate Jaccard similarity (intersection / union)
        intersection = set1.intersection(set2)
        union = set1.union(set2)
        
        if not union:
            return 0.0
        
        base_similarity = len(intersection) / len(union)
        
        # Apply concentration weighting if available
        weighted_similarity = self._apply_concentration_weighting(
            intersection,
            molecules1,
            molecules2
        )
        
        # Combine base and weighted similarities (70% weighted, 30% base)
        final_similarity = (weighted_similarity * 0.7) + (base_similarity * 0.3)
        
        # Convert to percentage (0-100)
        return round(final_similarity * 100, 2)
    
    def _apply_concentration_weighting(
        self,
        shared_molecules: Set[str],
        molecules1: List[Dict],
        molecules2: List[Dict]
    ) -> float:
        """
        Apply concentration-based weighting to similarity calculation.
        
        Molecules with higher concentrations contribute more to the
        overall flavor similarity score.
        
        Args:
            shared_molecules: Set of molecule names present in both ingredients
            molecules1: Molecule list for first ingredient
            molecules2: Molecule list for second ingredient
            
        Returns:
            float: Weighted similarity (0-1)
        """
        if not shared_molecules:
            return 0.0
        
        # Create concentration maps
        def create_concentration_map(molecules: List[Dict]) -> Dict[str, float]:
            conc_map = {}
            for mol in molecules:
                name = (mol.get("common_name") or mol.get("name", "")).lower()
                # Use concentration if available, otherwise assume equal weight
                conc_map[name] = mol.get("concentration", 1.0)
            return conc_map
        
        conc_map1 = create_concentration_map(molecules1)
        conc_map2 = create_concentration_map(molecules2)
        
        # Calculate weighted similarity for shared molecules
        total_weight = 0.0
        matched_weight = 0.0
        
        for mol_name in shared_molecules:
            # Get concentrations (default to 1.0 if not available)
            c1 = conc_map1.get(mol_name, 1.0)
            c2 = conc_map2.get(mol_name, 1.0)
            
            # Weight is the minimum of the two concentrations
            weight = min(c1, c2)
            matched_weight += weight
        
        # Total weight is sum of all concentrations in both sets
        total_weight = sum(conc_map1.values()) + sum(conc_map2.values())
        
        if total_weight == 0:
            return 0.0
        
        return matched_weight / total_weight
    
    def check_availability(self) -> bool:
        """
        Check if FlavorDB API is available and responding.
        
        Used for health checks and monitoring. Makes a simple request
        to verify API connectivity.
        
        Returns:
            bool: True if API is available, False otherwise
        """
        try:
            # Try a simple request to check availability
            response = self._make_request(
                "entities_by_readable_name",
                {"name": "water"}
            )
            return response is not None
        except Exception as e:
            logger.error(f"FlavorDB availability check failed: {str(e)}")
            return False
    
    def clear_cache(self):
        """
        Clear all LRU caches for flavor profile and molecule methods.
        
        Call this method if you need to force refresh of cached data.
        """
        self.get_flavor_profile_by_ingredient.cache_clear()
        self.get_flavor_pairings.cache_clear()
        self.get_molecules_by_name.cache_clear()
        logger.info("FlavorDB cache cleared")
    
    def get_cache_info(self) -> Dict[str, Dict]:
        """
        Get cache statistics for all cached methods.
        
        Useful for monitoring cache performance and hit rates.
        
        Returns:
            Dict: Cache statistics for each cached method
        """
        return {
            "flavor_profiles": {
                "hits": self.get_flavor_profile_by_ingredient.cache_info().hits,
                "misses": self.get_flavor_profile_by_ingredient.cache_info().misses,
                "size": self.get_flavor_profile_by_ingredient.cache_info().currsize,
                "maxsize": self.get_flavor_profile_by_ingredient.cache_info().maxsize
            },
            "flavor_pairings": {
                "hits": self.get_flavor_pairings.cache_info().hits,
                "misses": self.get_flavor_pairings.cache_info().misses,
                "size": self.get_flavor_pairings.cache_info().currsize,
                "maxsize": self.get_flavor_pairings.cache_info().maxsize
            },
            "molecules": {
                "hits": self.get_molecules_by_name.cache_info().hits,
                "misses": self.get_molecules_by_name.cache_info().misses,
                "size": self.get_molecules_by_name.cache_info().currsize,
                "maxsize": self.get_molecules_by_name.cache_info().maxsize
            }
        }