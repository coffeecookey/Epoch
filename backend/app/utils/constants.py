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


# ==============================================================================
# CRAVING REPLACEMENT SYSTEM
# ==============================================================================

# Map flavor types to RecipeDB search parameters
FLAVOR_TO_SEARCH_PARAMS: Dict[str, Dict] = {
    "sweet": {
        "categories": ["desserts", "snacks", "beverages"],
        "max_carbs": 30.0,
        "max_calories": 300,
    },
    "salty": {
        "categories": ["snacks", "appetizers"],
        "max_calories": 250,
    },
    "crunchy": {
        "categories": ["snacks", "salads", "appetizers"],
        "max_calories": 250,
    },
    "spicy": {
        "categories": ["snacks", "appetizers", "soups"],
        "cuisines": ["Indian", "Mexican", "Thai"],
        "max_calories": 350,
    },
    "umami": {
        "categories": ["soups", "appetizers", "main course"],
        "max_calories": 400,
    },
    "creamy": {
        "categories": ["desserts", "beverages", "soups"],
        "max_calories": 300,
    },
}

# Map time-of-day to RecipeDB day_category values
TIME_TO_DAY_CATEGORY: Dict[str, List[str]] = {
    "morning": ["breakfast"],
    "afternoon": ["lunch", "snack"],
    "evening": ["dinner", "snack"],
    "late-night": ["snack"],
}

# Map moods to commonly craved flavors (for pattern analysis)
MOOD_FLAVOR_ASSOCIATIONS: Dict[str, List[str]] = {
    "stressed": ["sweet", "creamy", "crunchy"],
    "bored": ["crunchy", "salty", "spicy"],
    "tired": ["sweet", "creamy", "umami"],
    "happy": ["sweet", "spicy"],
    "anxious": ["crunchy", "salty", "creamy"],
    "sad": ["sweet", "creamy"],
}

# Template-based psychological insights (flavor_type -> mood -> insight)
CRAVING_INSIGHT_TEMPLATES: Dict[str, Dict[str, str]] = {
    "sweet": {
        "stressed": "Sweet cravings during stress often reflect your body seeking quick energy via glucose. Cortisol, the stress hormone, drives the desire for fast-acting carbohydrates.",
        "tired": "When fatigued, your body craves sugar for a rapid energy boost. This is linked to depleted glycogen and serotonin levels seeking a quick replenishment.",
        "sad": "Emotional lows trigger sugar cravings because sugar briefly raises serotonin and dopamine levels, providing a temporary mood lift.",
        "bored": "Boredom-driven sweet cravings are often about seeking stimulation rather than hunger. Your brain associates sugar with a dopamine reward.",
        "anxious": "Anxiety can cause sweet cravings as your brain looks for calming neurotransmitters. Sugar temporarily increases serotonin, providing brief relief.",
        "happy": "Craving something sweet when happy is often about celebrating. Your brain links sweet flavors with reward and positive memories.",
        "_default": "Sweet cravings are your brain seeking a dopamine reward. The key is to find alternatives that satisfy the same neural pathway without the sugar spike.",
    },
    "salty": {
        "stressed": "Salt cravings under stress may indicate mineral depletion. Stress hormones can affect your electrolyte balance, making salty foods feel extra satisfying.",
        "bored": "Wanting salty snacks when bored is a common texture-seeking behavior. The crunch and salt together provide sensory stimulation your brain is looking for.",
        "_default": "Salty cravings can signal dehydration or electrolyte imbalance. They can also be purely habitual, tied to snacking patterns.",
    },
    "crunchy": {
        "stressed": "Craving crunchy foods when stressed is linked to jaw-tension release. The act of crunching serves as a physical outlet for built-up tension.",
        "bored": "Crunchy cravings during boredom are about sensory stimulation. The auditory and tactile feedback of crunching engages multiple senses.",
        "anxious": "Crunching foods can serve as a stress-relief mechanism. The repetitive jaw motion has a calming effect similar to other rhythmic behaviors.",
        "_default": "Crunchy cravings are often about texture and sensory engagement rather than nutrition. Healthier crunchy options can satisfy this need effectively.",
    },
    "spicy": {
        "bored": "Craving spice when bored is your body seeking excitement. Capsaicin triggers endorphin release, creating a mild natural high.",
        "_default": "Spicy food cravings are tied to endorphin release. Capsaicin activates pain receptors that trigger a pleasurable endorphin rush.",
    },
    "umami": {
        "tired": "Umami cravings when tired suggest your body wants protein and amino acids for recovery. Glutamate-rich foods signal nourishment to your brain.",
        "_default": "Umami cravings indicate a desire for deep, savory satisfaction. These are often protein and amino-acid related signals from your body.",
    },
    "creamy": {
        "stressed": "Creamy food cravings during stress are connected to comfort-seeking behavior. Fat-rich foods activate reward centers and promote a sense of safety.",
        "sad": "Wanting creamy foods when sad is classic comfort eating. The smooth texture and fat content trigger calming neurotransmitter release.",
        "_default": "Creamy cravings are about texture comfort and satiety. Healthy fats can provide the same satisfaction as less nutritious options.",
    },
}

# Science explanations for why replacements work (by flavor_type)
CRAVING_SCIENCE_TEMPLATES: Dict[str, str] = {
    "sweet": "These alternatives provide natural sugars and complex carbohydrates that give sustained energy without the insulin spike of refined sugar. They still activate dopamine pathways but avoid the crash-and-crave cycle.",
    "salty": "These options deliver satisfying saltiness with added nutritional value like fiber, protein, or healthy fats. They address the electrolyte need without excess sodium.",
    "crunchy": "These crunchy alternatives provide the same tactile and auditory satisfaction. The physical act of crunching activates the same stress-relief pathways while delivering better nutrition.",
    "spicy": "Spicy alternatives still trigger endorphin release through capsaicin while adding nutritional benefits. The heat satisfaction is maintained without excess calories or sodium.",
    "umami": "Umami-rich alternatives provide glutamate and amino acids that satisfy deep savory cravings. They deliver protein and minerals that your body is actually signaling for.",
    "creamy": "These alternatives provide healthy fats and smooth textures that activate the same comfort-seeking reward centers. They deliver sustained satiety instead of a brief sugar-fat spike.",
}