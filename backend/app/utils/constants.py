"""
Centralized constants and configuration data.

This module contains all hardcoded databases, thresholds, and mappings
used throughout the application. Centralizing these values makes them
easy to modify and maintain.

Categories:
- Allergen keywords for detection
- Unhealthy ingredient keywords
- Health scoring thresholds and targets
- Micronutrient RDA values
- Healthy ingredient swap database
- API endpoints
"""

from typing import Dict, List, Tuple

# ==============================================================================
# ALLERGEN DATABASE
# ==============================================================================

ALLERGEN_KEYWORDS: Dict[str, List[str]] = {
    "milk": [
        "milk", "cream", "butter", "cheese", "yogurt", "whey", "casein",
        "lactose", "dairy", "ghee", "buttermilk", "sour cream", "ice cream",
        "custard", "pudding"
    ],
    "eggs": [
        "egg", "eggs", "albumin", "mayonnaise", "meringue", "eggnog"
    ],
    "peanuts": [
        "peanut", "peanuts", "groundnut", "peanut butter", "peanut oil"
    ],
    "tree_nuts": [
        "almond", "almonds", "walnut", "walnuts", "cashew", "cashews",
        "pecan", "pecans", "pistachio", "pistachios", "hazelnut", "hazelnuts",
        "macadamia", "brazil nut", "pine nut"
    ],
    "soy": [
        "soy", "soya", "tofu", "tempeh", "edamame", "miso", "soy sauce",
        "tamari", "soybean", "soy milk"
    ],
    "wheat": [
        "wheat", "flour", "bread", "pasta", "noodle", "couscous",
        "bulgur", "semolina", "durum", "farro", "spelt"
    ],
    "fish": [
        "fish", "salmon", "tuna", "cod", "halibut", "tilapia", "trout",
        "mackerel", "sardine", "anchovy", "bass", "haddock"
    ],
    "shellfish": [
        "shrimp", "prawn", "crab", "lobster", "clam", "oyster", "mussel",
        "scallop", "crayfish", "crawfish"
    ]
}


# Allergen severity mapping
ALLERGEN_SEVERITY_MAP: Dict[str, str] = {
    "peanuts": "high",      # High risk of severe reactions
    "tree_nuts": "high",    # High risk of severe reactions
    "shellfish": "high",    # High risk of severe reactions
    "fish": "medium",       # Moderate risk
    "eggs": "medium",       # Moderate risk, often outgrown
    "milk": "medium",       # Moderate risk, often outgrown
    "soy": "low",           # Generally milder reactions
    "wheat": "low"          # Generally milder reactions
}


# ==============================================================================
# RISKY INGREDIENT KEYWORDS
# ==============================================================================

UNHEALTHY_KEYWORDS: Dict[str, List[str]] = {
    "trans_fat": [
        "hydrogenated", "partially hydrogenated", "shortening"
    ],
    "refined": [
        "refined", "white flour", "white sugar", "white rice",
        "refined sugar", "refined oil"
    ],
    "artificial": [
        "artificial", "aspartame", "saccharin", "sucralose",
        "acesulfame", "artificial flavor", "artificial color",
        "yellow 5", "yellow 6", "red 40", "blue 1"
    ],
    "high_sodium": [
        "soy sauce", "salt", "sodium", "bouillon", "broth cube",
        "msg", "monosodium glutamate"
    ],
    "processed": [
        "processed", "packaged", "instant", "canned"
    ],
    "preservative": [
        "bha", "bht", "sodium benzoate", "sodium nitrite",
        "potassium sorbate", "tbhq"
    ]
}


# Category mapping for risky ingredients
RISKY_INGREDIENT_CATEGORIES: Dict[str, str] = {
    "trans_fat": "critical",
    "artificial": "high",
    "refined": "medium",
    "high_sodium": "medium",
    "processed": "low",
    "preservative": "low"
}


# ==============================================================================
# HEALTH SCORING THRESHOLDS
# ==============================================================================

# Rating thresholds (score ranges)
RATING_THRESHOLDS: Dict[str, float] = {
    "Excellent": 80.0,  # 80-100
    "Good": 60.0,       # 60-79
    "Decent": 40.0,     # 40-59
    "Bad": 20.0,        # 20-39
    "Poor": 0.0         # 0-19
}


# Macronutrient target ranges (percentage of total calories)
MACRO_TARGETS: Dict[str, Tuple[float, float]] = {
    "protein_percent": (10.0, 35.0),   # 10-35% of calories from protein
    "carbs_percent": (45.0, 65.0),     # 45-65% of calories from carbs
    "fat_percent": (20.0, 35.0)        # 20-35% of calories from fat
}


# Negative factor thresholds (per serving)
NEGATIVE_FACTOR_THRESHOLDS: Dict[str, float] = {
    "sodium": 400.0,         # mg (>400mg triggers penalty)
    "sugar": 25.0,           # g (>25g triggers penalty)
    "saturated_fat": 10.0,   # g (>10g triggers penalty)
    "trans_fat": 0.5,        # g (>0.5g triggers penalty)
    "cholesterol": 100.0     # mg (>100mg triggers penalty)
}


# ==============================================================================
# MICRONUTRIENT RDA VALUES
# ==============================================================================

# Recommended Daily Allowance values (adult average)
RDA_VALUES: Dict[str, float] = {
    # Vitamins
    "vitamin_a": 900.0,      # mcg
    "vitamin_c": 90.0,       # mg
    "vitamin_d": 20.0,       # mcg
    "vitamin_e": 15.0,       # mg
    "vitamin_k": 120.0,      # mcg
    "thiamin": 1.2,          # mg (B1)
    "riboflavin": 1.3,       # mg (B2)
    "niacin": 16.0,          # mg (B3)
    "vitamin_b6": 1.7,       # mg
    "folate": 400.0,         # mcg (B9)
    "vitamin_b12": 2.4,      # mcg
    
    # Minerals
    "calcium": 1000.0,       # mg
    "iron": 18.0,            # mg
    "magnesium": 400.0,      # mg
    "phosphorus": 700.0,     # mg
    "potassium": 4700.0,     # mg
    "zinc": 11.0,            # mg
    "selenium": 55.0,        # mcg
    "copper": 0.9,           # mg
    "manganese": 2.3         # mg
}


# ==============================================================================
# HEALTHY INGREDIENT ALTERNATIVES DATABASE
# ==============================================================================

HEALTHY_SWAPS: Dict[str, Dict[str, List[str]]] = {
    "oil": {
        "vegetable oil": ["olive oil", "avocado oil", "coconut oil"],
        "butter": ["ghee", "olive oil", "avocado", "coconut oil"],
        "margarine": ["olive oil", "avocado oil"],
        "shortening": ["coconut oil", "applesauce"],
        "lard": ["olive oil", "avocado oil"]
    },
    
    "sweetener": {
        "sugar": ["honey", "maple syrup", "stevia", "monk fruit"],
        "white sugar": ["coconut sugar", "date sugar", "honey"],
        "brown sugar": ["coconut sugar", "maple syrup", "date sugar"],
        "corn syrup": ["honey", "maple syrup", "agave nectar"],
        "high fructose corn syrup": ["honey", "maple syrup"]
    },
    
    "dairy": {
        "cream": ["coconut cream", "cashew cream"],
        "heavy cream": ["coconut cream", "cashew cream"],
        "milk": ["almond milk", "oat milk", "soy milk", "coconut milk"],
        "whole milk": ["almond milk", "oat milk", "low-fat milk"],
        "sour cream": ["greek yogurt", "coconut cream"],
        "cheese": ["nutritional yeast", "cashew cheese"]
    },
    
    "grain": {
        "white rice": ["brown rice", "quinoa", "cauliflower rice"],
        "white flour": ["whole wheat flour", "almond flour", "oat flour"],
        "all-purpose flour": ["whole wheat flour", "spelt flour"],
        "pasta": ["whole wheat pasta", "zucchini noodles", "soba noodles"],
        "white bread": ["whole wheat bread", "sourdough bread"]
    },
    
    "protein": {
        "ground beef": ["ground turkey", "ground chicken", "lentils"],
        "bacon": ["turkey bacon", "tempeh bacon"],
        "sausage": ["chicken sausage", "turkey sausage"]
    },
    
    "condiment": {
        "mayonnaise": ["greek yogurt", "avocado", "hummus"],
        "ketchup": ["tomato paste", "salsa"],
        "soy sauce": ["coconut aminos", "tamari"]
    },
    
    "spice": {
        "salt": ["herbs", "lemon juice", "garlic powder"],
        "seasoning salt": ["herb blend", "garlic powder"]
    }
}


# ==============================================================================
# INGREDIENT CATEGORIZATION
# ==============================================================================

# Ingredient category keywords for automatic categorization
INGREDIENT_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "oil": [
        "oil", "butter", "ghee", "margarine", "shortening", "lard", "fat"
    ],
    "sweetener": [
        "sugar", "honey", "syrup", "stevia", "sweetener", "molasses",
        "agave", "fructose", "glucose"
    ],
    "dairy": [
        "milk", "cream", "cheese", "yogurt", "butter", "dairy"
    ],
    "grain": [
        "rice", "flour", "bread", "pasta", "wheat", "oat", "quinoa",
        "barley", "grain"
    ],
    "protein": [
        "chicken", "beef", "pork", "fish", "turkey", "lamb", "tofu",
        "tempeh", "egg", "bean", "lentil"
    ],
    "vegetable": [
        "carrot", "broccoli", "spinach", "tomato", "onion", "garlic",
        "pepper", "lettuce", "cabbage", "kale", "vegetable"
    ],
    "fruit": [
        "apple", "banana", "orange", "berry", "grape", "melon", "fruit"
    ],
    "spice": [
        "salt", "pepper", "cumin", "paprika", "oregano", "basil",
        "thyme", "cinnamon", "spice", "herb"
    ],
    "condiment": [
        "sauce", "ketchup", "mustard", "mayo", "mayonnaise", "dressing"
    ]
}


# ==============================================================================
# API CONFIGURATION
# ==============================================================================

# External API base URLs
RECIPEDB_BASE_URL: str = "https://cosylab.iiitd.edu.in/recipedb/search_recipedb"
FLAVORDB_BASE_URL: str = "https://cosylab.iiitd.edu.in/flavordb"


# API endpoint paths (relative to base URL)
RECIPEDB_ENDPOINTS: Dict[str, str] = {
    "recipe_by_title": "recipe_by_title",
    "recipe_by_id": "recipe_by_id",
    "recipe_nutrition": "recipe_nutrition_info",
    "recipe_micro_nutrition": "recipe_micro_nutrition_info",
    "recipe_by_calories": "recipe_by_calories",
    "recipe_by_protein": "recipe_by_protein_range",
    "recipe_by_cuisine": "recipe_by_cuisine",
    "recipe_by_diet": "recipe_by_diet"
}


FLAVORDB_ENDPOINTS: Dict[str, str] = {
    "entities_by_name": "entities_by_readable_name",
    "flavor_pairings": "flavor_pairings",
    "molecules_by_flavor": "molecules_by_flavor_profile",
    "molecules_by_name": "molecules_by_common_name"
}