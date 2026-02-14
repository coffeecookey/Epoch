"""
Gemini function-calling tool definitions for the LLM swap agent.

Defines 16 tools that the agent can call to query FlavorDB and RecipeDB APIs.
Each tool is a google.genai FunctionDeclaration.
"""

from google.genai import types


# ─── FlavorDB Molecule Tools (7) ───────────────────────────────────────────────

flavordb_get_entity_by_name = types.FunctionDeclaration(
    name="flavordb_get_entity_by_name",
    description=(
        "Get the full flavor profile of an ingredient from FlavorDB. "
        "Returns molecules, primary flavor descriptors, and food category. "
        "Use this FIRST when analyzing any ingredient."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "ingredient_name": types.Schema(
                type=types.Type.STRING,
                description="Ingredient name, e.g. 'butter', 'vanilla', 'garlic'",
            ),
        },
        required=["ingredient_name"],
    ),
)

flavordb_get_molecules_by_common_name = types.FunctionDeclaration(
    name="flavordb_get_molecules_by_common_name",
    description=(
        "Get detailed data for a specific flavor molecule by its common name. "
        "Returns chemical formula, molecular weight, odor/taste thresholds and descriptors."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "molecule_name": types.Schema(
                type=types.Type.STRING,
                description="Common name of the molecule, e.g. 'vanillin', 'limonene'",
            ),
        },
        required=["molecule_name"],
    ),
)

flavordb_get_molecules_by_flavor_profile = types.FunctionDeclaration(
    name="flavordb_get_molecules_by_flavor_profile",
    description=(
        "Find all molecules associated with a specific flavor descriptor. "
        "E.g. 'sweet', 'umami', 'floral', 'citrus', 'bitter'."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "flavor": types.Schema(
                type=types.Type.STRING,
                description="Flavor descriptor, e.g. 'sweet', 'umami', 'smoky'",
            ),
        },
        required=["flavor"],
    ),
)

flavordb_get_molecules_by_functional_group = types.FunctionDeclaration(
    name="flavordb_get_molecules_by_functional_group",
    description=(
        "Get molecules containing a specific chemical functional group. "
        "E.g. 'aldehyde', 'ester', 'ketone', 'alcohol', 'terpene'."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "group": types.Schema(
                type=types.Type.STRING,
                description="Functional group name, e.g. 'aldehyde', 'ester'",
            ),
        },
        required=["group"],
    ),
)

flavordb_get_molecules_by_weight_range = types.FunctionDeclaration(
    name="flavordb_get_molecules_by_weight_range",
    description=(
        "Get molecules within a molecular weight range (Daltons). "
        "Useful for finding structurally similar volatile compounds."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "min_weight": types.Schema(type=types.Type.NUMBER, description="Minimum MW in Daltons"),
            "max_weight": types.Schema(type=types.Type.NUMBER, description="Maximum MW in Daltons"),
        },
        required=["min_weight", "max_weight"],
    ),
)

flavordb_get_molecules_by_polar_surface_area = types.FunctionDeclaration(
    name="flavordb_get_molecules_by_polar_surface_area",
    description=(
        "Get molecules within a polar surface area (PSA) range. "
        "PSA correlates with volatility and membrane permeability."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "min_psa": types.Schema(type=types.Type.NUMBER, description="Minimum PSA in Angstrom^2"),
            "max_psa": types.Schema(type=types.Type.NUMBER, description="Maximum PSA in Angstrom^2"),
        },
        required=["min_psa", "max_psa"],
    ),
)

flavordb_get_molecules_by_hbd_hba = types.FunctionDeclaration(
    name="flavordb_get_molecules_by_hbd_hba",
    description=(
        "Get molecules by hydrogen bond donor (HBD) and acceptor (HBA) counts. "
        "Useful for finding molecules with similar interaction profiles."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "min_hbd": types.Schema(type=types.Type.INTEGER, description="Min H-bond donors"),
            "max_hbd": types.Schema(type=types.Type.INTEGER, description="Max H-bond donors"),
            "min_hba": types.Schema(type=types.Type.INTEGER, description="Min H-bond acceptors"),
            "max_hba": types.Schema(type=types.Type.INTEGER, description="Max H-bond acceptors"),
        },
        required=["min_hbd", "max_hbd", "min_hba", "max_hba"],
    ),
)

# ─── FlavorDB Property Tools (4) ──────────────────────────────────────────────

flavordb_get_aroma_threshold = types.FunctionDeclaration(
    name="flavordb_get_aroma_threshold",
    description=(
        "Get the aroma (odor) detection threshold for a molecule. "
        "Use this for perceptual filtering: only molecules detectable at "
        "food-relevant concentrations matter for flavor matching."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "molecule_name": types.Schema(
                type=types.Type.STRING,
                description="Molecule common name, e.g. 'vanillin'",
            ),
        },
        required=["molecule_name"],
    ),
)

flavordb_get_taste_threshold = types.FunctionDeclaration(
    name="flavordb_get_taste_threshold",
    description=(
        "Get the taste detection threshold for a molecule. "
        "Use for perceptual filtering of non-volatile taste compounds."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "molecule_name": types.Schema(
                type=types.Type.STRING,
                description="Molecule common name",
            ),
        },
        required=["molecule_name"],
    ),
)

flavordb_get_natural_occurrence = types.FunctionDeclaration(
    name="flavordb_get_natural_occurrence",
    description=(
        "Get the natural food sources where a molecule is found. "
        "Useful for identifying which foods share key flavor compounds."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "molecule_name": types.Schema(
                type=types.Type.STRING,
                description="Molecule common name",
            ),
        },
        required=["molecule_name"],
    ),
)

flavordb_get_physicochemical_properties = types.FunctionDeclaration(
    name="flavordb_get_physicochemical_properties",
    description=(
        "Get physicochemical properties: ALogP (hydrophobicity), ring count, "
        "bond count, atom count, molecular weight. Useful for chemical similarity reasoning."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "molecule_name": types.Schema(
                type=types.Type.STRING,
                description="Molecule common name",
            ),
        },
        required=["molecule_name"],
    ),
)

# ─── FlavorDB Regulatory (1) ──────────────────────────────────────────────────

flavordb_get_regulatory_info = types.FunctionDeclaration(
    name="flavordb_get_regulatory_info",
    description=(
        "Get regulatory status of a molecule: FEMA number, JECFA number, COE number, "
        "GRAS status. Use to verify safety of shared molecules in substitute ingredients."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "molecule_name": types.Schema(
                type=types.Type.STRING,
                description="Molecule common name",
            ),
        },
        required=["molecule_name"],
    ),
)

# ─── FlavorDB Pairing (1) ─────────────────────────────────────────────────────

flavordb_get_flavor_pairings = types.FunctionDeclaration(
    name="flavordb_get_flavor_pairings",
    description=(
        "Get ingredients that pair well with a given ingredient based on shared "
        "flavor compounds. Use this to validate that a substitute pairs well "
        "with the other ingredients in the recipe."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "ingredient_name": types.Schema(
                type=types.Type.STRING,
                description="Ingredient name, e.g. 'tomato', 'basil'",
            ),
        },
        required=["ingredient_name"],
    ),
)

# ─── RecipeDB Tools (3) ───────────────────────────────────────────────────────

recipedb_search_by_ingredient = types.FunctionDeclaration(
    name="recipedb_search_by_ingredient",
    description=(
        "Search RecipeDB for recipes that use a specific ingredient. "
        "Use this to verify that a substitute ingredient is actually used "
        "in real recipes (functional role verification)."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "ingredient_name": types.Schema(
                type=types.Type.STRING,
                description="Ingredient to search for in recipes",
            ),
        },
        required=["ingredient_name"],
    ),
)

recipedb_get_nutrition_info = types.FunctionDeclaration(
    name="recipedb_get_nutrition_info",
    description=(
        "Get macronutrient data (calories, protein, carbs, fat, sodium, etc.) "
        "for a recipe by its RecipeDB ID."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "recipe_id": types.Schema(
                type=types.Type.STRING,
                description="RecipeDB recipe ID",
            ),
        },
        required=["recipe_id"],
    ),
)

recipedb_search_by_cuisine = types.FunctionDeclaration(
    name="recipedb_search_by_cuisine",
    description=(
        "Search RecipeDB for recipes from a specific cuisine. "
        "Useful to find traditional uses of substitute ingredients."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "cuisine": types.Schema(
                type=types.Type.STRING,
                description="Cuisine type, e.g. 'Indian', 'Italian', 'Mexican'",
            ),
        },
        required=["cuisine"],
    ),
)

# ─── All tools list ───────────────────────────────────────────────────────────

ALL_TOOLS = [
    flavordb_get_entity_by_name,
    flavordb_get_molecules_by_common_name,
    flavordb_get_molecules_by_flavor_profile,
    flavordb_get_molecules_by_functional_group,
    flavordb_get_molecules_by_weight_range,
    flavordb_get_molecules_by_polar_surface_area,
    flavordb_get_molecules_by_hbd_hba,
    flavordb_get_aroma_threshold,
    flavordb_get_taste_threshold,
    flavordb_get_natural_occurrence,
    flavordb_get_physicochemical_properties,
    flavordb_get_regulatory_info,
    flavordb_get_flavor_pairings,
    recipedb_search_by_ingredient,
    recipedb_get_nutrition_info,
    recipedb_search_by_cuisine,
]
