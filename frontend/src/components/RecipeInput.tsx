import { useState } from "react";
import { motion } from "framer-motion";
import { Search, Plus, X, AlertTriangle, Leaf, Wheat, Milk, Egg, Fish } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";

const allergens = [
  { id: "gluten", label: "Gluten-Free", icon: Wheat },
  { id: "dairy", label: "Dairy-Free", icon: Milk },
  { id: "eggs", label: "Egg-Free", icon: Egg },
  { id: "seafood", label: "Seafood-Free", icon: Fish },
  { id: "vegan", label: "Vegan", icon: Leaf },
];

interface RecipeInputProps {
  onAnalyze: (recipe: string, ingredients: string[]) => void;
}

const RecipeInput = ({ onAnalyze }: RecipeInputProps) => {
  const [recipeName, setRecipeName] = useState("");
  const [ingredientInput, setIngredientInput] = useState("");
  const [ingredients, setIngredients] = useState<string[]>([
    "All-purpose flour (2 cups)",
    "Butter (1 cup)",
    "White sugar (1.5 cups)",
    "Heavy cream (1 cup)",
  ]);
  const [activeAllergens, setActiveAllergens] = useState<string[]>([]);

  const addIngredient = () => {
    if (ingredientInput.trim()) {
      setIngredients([...ingredients, ingredientInput.trim()]);
      setIngredientInput("");
    }
  };

  const removeIngredient = (idx: number) => {
    setIngredients(ingredients.filter((_, i) => i !== idx));
  };

  const toggleAllergen = (id: string) => {
    setActiveAllergens((prev) =>
      prev.includes(id) ? prev.filter((a) => a !== id) : [...prev, id]
    );
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 }}
      className="rounded-2xl border border-border bg-card p-6 shadow-sm"
    >
      <div className="mb-6">
        <h2 className="font-display text-2xl">Recipe Input</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Enter your recipe and we'll analyze its nutritional profile
        </p>
      </div>

      {/* Recipe Name */}
      <div className="mb-4">
        <label className="mb-1.5 block text-sm font-medium">Recipe Name</label>
        <Input
          placeholder="e.g., Classic Chocolate Cake"
          value={recipeName}
          onChange={(e) => setRecipeName(e.target.value)}
          className="bg-background"
        />
      </div>

      {/* Ingredients */}
      <div className="mb-4">
        <label className="mb-1.5 block text-sm font-medium">Ingredients</label>
        <div className="flex gap-2">
          <Input
            placeholder="Add an ingredient..."
            value={ingredientInput}
            onChange={(e) => setIngredientInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addIngredient()}
            className="bg-background"
          />
          <Button onClick={addIngredient} size="icon" className="shrink-0">
            <Plus className="h-4 w-4" />
          </Button>
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          {ingredients.map((ing, idx) => (
            <Badge
              key={idx}
              variant="secondary"
              className="gap-1 py-1.5 pl-3 pr-2 text-sm"
            >
              {ing}
              <button
                onClick={() => removeIngredient(idx)}
                className="ml-1 rounded-full p-0.5 transition-colors hover:bg-foreground/10"
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
        </div>
      </div>

      {/* Allergen Settings */}
      <div className="mb-6">
        <label className="mb-2 flex items-center gap-2 text-sm font-medium">
          <AlertTriangle className="h-4 w-4 text-sunrise" />
          Allergen & Dietary Settings
        </label>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
          {allergens.map((a) => {
            const active = activeAllergens.includes(a.id);
            return (
              <button
                key={a.id}
                onClick={() => toggleAllergen(a.id)}
                className={`flex items-center gap-2 rounded-xl border px-3 py-2.5 text-sm font-medium transition-all ${
                  active
                    ? "border-accent bg-accent/20 text-accent-foreground"
                    : "border-border bg-background text-muted-foreground hover:border-accent/50"
                }`}
              >
                <a.icon className="h-4 w-4" />
                <span className="truncate">{a.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Analyze Button */}
      <Button
        onClick={() => onAnalyze(recipeName, ingredients)}
        className="w-full gap-2 bg-primary text-primary-foreground hover:bg-primary/90"
        size="lg"
      >
        <Search className="h-4 w-4" />
        Analyze Recipe
      </Button>
    </motion.div>
  );
};

export default RecipeInput;
