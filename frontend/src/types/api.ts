// API Types for Recipe Health Analysis

export interface HealthScore {
  score: number;
  rating: string;
  breakdown: {
    macronutrient_score?: number;
    micronutrient_score?: number;
    negative_factors_penalty?: number;
    raw_total?: number;
    normalized_score?: number;
    components?: Record<string, any>;
    // Legacy field names for backward compatibility
    macro_impact?: number;
    micro_impact?: number;
    penalties?: number;
  };
}

export interface RecipeRecommendation {
  name: string;
  health_score: number;
  similarity_score: number;
  reason: string;
}

export interface SubstituteOption {
  name: string;
  flavor_match: number;
  health_improvement: number;
  reason?: string;
}

export interface Swap {
  original: string;
  substitute: SubstituteOption;
  accepted?: boolean;
}

export interface RiskyIngredient {
  name: string;
  reason: string;
}

export interface FullAnalysisResponse {
  recipe_name: string;
  ingredients: string[];
  source: string;
  original_health_score: HealthScore;
  nutrition: Record<string, number>;
  micro_nutrition: Record<string, any>;
  detected_allergens: Array<Record<string, any>>;
  user_allergen_warnings: Array<Record<string, any>>;
  flagged_avoid_ingredients: string[];
  similar_recipe: RecipeRecommendation | null;
  risky_ingredients: Array<Record<string, any>>;
  swap_suggestions: Array<Record<string, any>>;
  improved_health_score: HealthScore | null;
  improved_ingredients: string[] | null;
  score_improvement: number | null;
  explanation: string | null;
  agent_metadata?: Record<string, any>;
  /** True when CosyLab API was not responsive and fallback was used */
  used_llm_fallback?: boolean;
}

export interface AnalyzeRequest {
  recipe_name?: string;
  ingredients?: string[];
  allergens?: string[];
  avoid_ingredients?: string[];
  quantity?: number; // Servings (stored for display, not sent to backend)
}

export interface RecalculateRequest {
  recipe_name: string;
  original_ingredients: string[];
  accepted_swaps: Record<string, string>;
  allergens?: string[];
  avoid_ingredients?: string[];
}

export interface RecalculateResponse {
  recipe_name: string;
  final_ingredients: string[];
  final_health_score: HealthScore;
  nutrition: Record<string, number>;
  micro_nutrition: Record<string, any>;
  detected_allergens: Array<Record<string, any>>;
  user_allergen_warnings: Array<Record<string, any>>;
  flagged_avoid_ingredients: string[];
  total_score_improvement: number;
  explanation?: string;
}

export const ALLERGEN_OPTIONS = [
  { value: "milk", label: "Milk" },
  { value: "eggs", label: "Eggs" },
  { value: "peanuts", label: "Peanuts" },
  { value: "tree_nuts", label: "Tree Nuts" },
  { value: "soy", label: "Soy" },
  { value: "wheat", label: "Wheat" },
  { value: "fish", label: "Fish" },
  { value: "shellfish", label: "Shellfish" },
];

/** Dietary presets for common health conditions. Maps to allergens and avoid_ingredients. */
export const DIETARY_PRESETS = [
  {
    id: "diabetic",
    label: "Diabetic",
    allergens: [] as string[],
    avoid_ingredients: ["refined sugar", "high fructose corn syrup", "white sugar"],
  },
  {
    id: "gluten_free",
    label: "Gluten-free",
    allergens: ["wheat"],
    avoid_ingredients: ["gluten", "barley", "rye"],
  },
  {
    id: "dairy_free",
    label: "Dairy-free",
    allergens: ["milk"],
    avoid_ingredients: ["dairy", "cream", "cheese", "butter"],
  },
  {
    id: "nut_allergy",
    label: "Nut allergy",
    allergens: ["peanuts", "tree_nuts"],
    avoid_ingredients: [],
  },
  {
    id: "soy_free",
    label: "Soy-free",
    allergens: ["soy"],
    avoid_ingredients: ["soy"],
  },
  {
    id: "low_sodium",
    label: "Low sodium",
    allergens: [],
    avoid_ingredients: ["excess salt", "added salt"],
  },
  {
    id: "heart_healthy",
    label: "Heart-healthy",
    allergens: [],
    avoid_ingredients: ["trans fats", "saturated fats"],
  },
] as const;

/** Generic terms that are NOT valid for avoid_ingredients. Use specific dietary/health instructions. */
export const INVALID_AVOID_TERMS = new Set([
  "light", "heavy", "quick", "easy", "healthy", "unhealthy", "tasty", "delicious",
  "meal", "meals", "food", "foods", "good", "bad", "yummy", "simple", "fancy",
  "fresh", "nice", "great", "love", "like", "prefer", "want", "need",
  "breakfast", "lunch", "dinner", "snack", "snacks", "diet", "dieting",
  "organic", "natural", "clean", "processed", "junk",
]);

// User-related types
export interface Recipe {
  id: string;
  name: string;
  quantity?: number; // Servings
  health_score: number;
  rating: string;
  ingredients: string[];
  improved_score?: number;
  detected_allergens: string[];
  swap_suggestions: Swap[];
  timestamp: string;
}

export interface DashboardStats {
  total_recipes: number;
  average_health_score: number;
  best_improved_score: number;
  total_profiles: number;
  app_status: string;
}

export interface UserProfile {
  id: string;
  name: string;
  age?: number;
  archetype: string;
  allergens: string[];
  avoid_ingredients: string[];
  created_at: string;
}

