"""
Extended FlavorDB API service.

Inherits from FlavorDBService and adds additional endpoints needed by
the LLM swap agent: functional groups, weight ranges, PSA, HBD/HBA,
aroma/taste thresholds, regulatory info, and physicochemical properties.
"""

import logging
from typing import Dict, List, Optional

from app.services.flavordb_service import FlavorDBService

logger = logging.getLogger(__name__)


class FlavorDBExtendedService(FlavorDBService):
    """Extended FlavorDB service with additional molecule query endpoints."""

    def get_molecules_by_functional_group(self, group: str) -> List[Dict]:
        """Get molecules containing a specific functional group (e.g., 'aldehyde', 'ester')."""
        logger.info(f"Fetching molecules by functional group: {group}")
        params = {"group": group.strip().lower()}
        response = self._make_request("molecules_by_functional_group", params)
        if not response:
            return []
        molecules = response if isinstance(response, list) else response.get("molecules", [])
        return [self._normalize_molecule(m) for m in molecules if isinstance(m, dict)]

    def get_molecules_by_weight_range(self, min_weight: float, max_weight: float) -> List[Dict]:
        """Get molecules within a molecular weight range."""
        logger.info(f"Fetching molecules by weight range: {min_weight}-{max_weight}")
        params = {"min": min_weight, "max": max_weight}
        response = self._make_request("molecules_by_weight_range", params)
        if not response:
            return []
        molecules = response if isinstance(response, list) else response.get("molecules", [])
        return [self._normalize_molecule(m) for m in molecules if isinstance(m, dict)]

    def get_molecules_by_polar_surface_area(self, min_psa: float, max_psa: float) -> List[Dict]:
        """Get molecules within a polar surface area range."""
        logger.info(f"Fetching molecules by PSA range: {min_psa}-{max_psa}")
        params = {"min": min_psa, "max": max_psa}
        response = self._make_request("molecules_by_polar_surface_area", params)
        if not response:
            return []
        molecules = response if isinstance(response, list) else response.get("molecules", [])
        return [self._normalize_molecule(m) for m in molecules if isinstance(m, dict)]

    def get_molecules_by_hbd_hba(
        self, min_hbd: int, max_hbd: int, min_hba: int, max_hba: int
    ) -> List[Dict]:
        """Get molecules by hydrogen bond donor/acceptor counts."""
        logger.info(f"Fetching molecules by HBD({min_hbd}-{max_hbd}), HBA({min_hba}-{max_hba})")
        params = {"min_hbd": min_hbd, "max_hbd": max_hbd, "min_hba": min_hba, "max_hba": max_hba}
        response = self._make_request("molecules_by_hbd_hba", params)
        if not response:
            return []
        molecules = response if isinstance(response, list) else response.get("molecules", [])
        return [self._normalize_molecule(m) for m in molecules if isinstance(m, dict)]

    def get_aroma_threshold(self, molecule_name: str) -> Dict:
        """Get aroma threshold values for a molecule."""
        logger.info(f"Fetching aroma threshold for: {molecule_name}")
        params = {"name": molecule_name.strip().lower()}
        response = self._make_request("properties_by_aroma_threshold", params)
        if not response:
            return {"molecule": molecule_name, "aroma_threshold": None, "unit": "ppb"}
        data = response.get("molecule", response) if isinstance(response, dict) else {}
        return {
            "molecule": molecule_name,
            "aroma_threshold": data.get("aroma_threshold", data.get("odor_threshold")),
            "unit": data.get("unit", "ppb"),
            "descriptors": data.get("odor_descriptors", []),
        }

    def get_taste_threshold(self, molecule_name: str) -> Dict:
        """Get taste threshold values for a molecule."""
        logger.info(f"Fetching taste threshold for: {molecule_name}")
        params = {"name": molecule_name.strip().lower()}
        response = self._make_request("properties_by_taste_threshold", params)
        if not response:
            return {"molecule": molecule_name, "taste_threshold": None, "unit": "ppm"}
        data = response.get("molecule", response) if isinstance(response, dict) else {}
        return {
            "molecule": molecule_name,
            "taste_threshold": data.get("taste_threshold"),
            "unit": data.get("unit", "ppm"),
            "descriptors": data.get("taste_descriptors", []),
        }

    def get_natural_occurrence(self, molecule_name: str) -> Dict:
        """Get natural food sources where a molecule is found."""
        logger.info(f"Fetching natural occurrence for: {molecule_name}")
        params = {"name": molecule_name.strip().lower()}
        response = self._make_request("properties_natural_occurrence", params)
        if not response:
            return {"molecule": molecule_name, "food_sources": []}
        data = response.get("molecule", response) if isinstance(response, dict) else {}
        return {
            "molecule": molecule_name,
            "food_sources": data.get("natural_sources", data.get("food_sources", [])),
        }

    def get_physicochemical_properties(self, molecule_name: str) -> Dict:
        """Get physicochemical properties: ALogP, ring count, bond count, atom count."""
        logger.info(f"Fetching physicochemical properties for: {molecule_name}")
        params = {"name": molecule_name.strip().lower()}
        # Try combined endpoint first
        response = self._make_request("physicochemical_properties", params)
        if not response:
            return {
                "molecule": molecule_name,
                "alogp": None,
                "num_rings": None,
                "num_bonds": None,
                "num_atoms": None,
                "molecular_weight": None,
            }
        data = response.get("molecule", response) if isinstance(response, dict) else {}
        return {
            "molecule": molecule_name,
            "alogp": data.get("alogp", data.get("logp")),
            "num_rings": data.get("num_rings", data.get("ring_count")),
            "num_bonds": data.get("num_bonds", data.get("bond_count")),
            "num_atoms": data.get("num_atoms", data.get("atom_count")),
            "molecular_weight": data.get("molecular_weight"),
        }

    def get_regulatory_info(self, molecule_name: str) -> Dict:
        """Get regulatory status: FEMA, JECFA, COE numbers."""
        logger.info(f"Fetching regulatory info for: {molecule_name}")
        params = {"name": molecule_name.strip().lower()}
        response = self._make_request("regulatory_info", params)
        if not response:
            return {
                "molecule": molecule_name,
                "fema_number": None,
                "jecfa_number": None,
                "coe_number": None,
                "gras_status": None,
            }
        data = response.get("molecule", response) if isinstance(response, dict) else {}
        return {
            "molecule": molecule_name,
            "fema_number": data.get("fema_number", data.get("fema")),
            "jecfa_number": data.get("jecfa_number", data.get("jecfa")),
            "coe_number": data.get("coe_number", data.get("coe")),
            "gras_status": data.get("gras_status", data.get("gras")),
        }

    def _normalize_molecule(self, mol: Dict) -> Dict:
        """Normalize a molecule dict to a consistent schema."""
        return {
            "name": mol.get("chemical_name", mol.get("name", "")),
            "common_name": mol.get("common_name", ""),
            "molecular_weight": mol.get("molecular_weight"),
            "flavor_descriptors": mol.get("flavor_descriptors", mol.get("odor_descriptors", [])),
        }
