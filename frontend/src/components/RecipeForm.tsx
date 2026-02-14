import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ALLERGEN_OPTIONS, INVALID_AVOID_TERMS } from "@/types/api";
import { recipeApi } from "@/services/api";
import type { UserProfile } from "@/types/api";

function isValidAvoidTerm(term: string): boolean {
  const t = term.trim().toLowerCase();
  if (t.length < 2) return false;
  const words = t.split(/\s+/);
  return !words.some((w) => INVALID_AVOID_TERMS.has(w));
}

interface RecipeFormProps {
  onSubmit: (data: {
    recipe_name?: string;
    ingredients?: string[];
    allergens?: string[];
    avoid_ingredients?: string[];
    quantity?: number;
  }) => void;
  isLoading?: boolean;
}

export function RecipeForm({ onSubmit, isLoading = false }: RecipeFormProps) {
  const [profiles, setProfiles] = useState<UserProfile[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<string>("__none__");
  const [inputMode, setInputMode] = useState<"recipe" | "custom">("recipe");
  const [recipeName, setRecipeName] = useState("");
  const [customRecipeName, setCustomRecipeName] = useState("");
  const [quantity, setQuantity] = useState<number>(4);
  const [customIngredients, setCustomIngredients] = useState("");
  const [selectedAllergens, setSelectedAllergens] = useState<string[]>([]);
  const [avoidIngredients, setAvoidIngredients] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    recipeApi.getProfiles().then(setProfiles).catch(() => setProfiles([]));
  }, []);

  useEffect(() => {
    if (!selectedProfileId || selectedProfileId === "__none__") return;
    const profile = profiles.find((p) => p.id === selectedProfileId);
    if (profile) {
      setSelectedAllergens(profile.allergens ?? []);
      setAvoidIngredients((profile.avoid_ingredients ?? []).join(", "));
    }
  }, [selectedProfileId, profiles]);

  const handleAllergenToggle = (allergen: string) => {
    setSelectedAllergens((prev) =>
      prev.includes(allergen)
        ? prev.filter((a) => a !== allergen)
        : [...prev, allergen]
    );
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (inputMode === "recipe" && !recipeName.trim()) {
      setError("Please enter a recipe name");
      return;
    }

    if (inputMode === "custom" && !customIngredients.trim()) {
      setError("Please enter at least one ingredient");
      return;
    }

    const rawAvoid = avoidIngredients
      .split(/[,;]/)
      .map((i) => i.trim())
      .filter((i) => i.length > 0);
    const invalidTerms = rawAvoid.filter((t) => !isValidAvoidTerm(t));
    if (invalidTerms.length > 0) {
      setError(
        `"${invalidTerms[0]}" is too generic. Use specific items like: no dairy, gluten-free, allergic to peanuts, avoid sugar`
      );
      return;
    }

    const data: any = {
      allergens: selectedAllergens.length > 0 ? selectedAllergens : undefined,
      avoid_ingredients: rawAvoid.length > 0 ? rawAvoid : undefined,
      quantity: quantity > 0 ? quantity : 4,
    };

    if (inputMode === "recipe") {
      data.recipe_name = recipeName.trim();
    } else {
      data.recipe_name = customRecipeName.trim() || "Custom Recipe";
      data.ingredients = customIngredients
        .split("\n")
        .map((i) => i.trim())
        .filter((i) => i.length > 0);
    }

    onSubmit(data);
  };

  return (
    <Card className="w-full max-w-2xl mx-auto">
      <CardHeader>
        <CardTitle className="font-display text-2xl">Analyze Your Recipe</CardTitle>
        <CardDescription>
          Enter a recipe name or list your ingredients to get health insights and swap suggestions
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Input Mode Selection */}
          <Tabs value={inputMode} onValueChange={(v) => setInputMode(v as "recipe" | "custom")}>
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="recipe">Recipe Name</TabsTrigger>
              <TabsTrigger value="custom">Custom Ingredients</TabsTrigger>
            </TabsList>

            <TabsContent value="recipe" className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="recipe-name">Recipe Name</Label>
                <Input
                  id="recipe-name"
                  placeholder="e.g., Spaghetti Carbonara"
                  value={recipeName}
                  onChange={(e) => setRecipeName(e.target.value)}
                  disabled={isLoading}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="quantity-recipe">Servings</Label>
                <Input
                  id="quantity-recipe"
                  type="number"
                  min={1}
                  max={100}
                  placeholder="4"
                  value={quantity}
                  onChange={(e) => setQuantity(Math.max(1, parseInt(e.target.value) || 1))}
                  disabled={isLoading}
                />
                <p className="text-sm text-muted-foreground">Number of servings</p>
              </div>
            </TabsContent>

            <TabsContent value="custom" className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="custom-recipe-name">Recipe Name</Label>
                <Input
                  id="custom-recipe-name"
                  placeholder="e.g., My Chocolate Cake"
                  value={customRecipeName}
                  onChange={(e) => setCustomRecipeName(e.target.value)}
                  disabled={isLoading}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="quantity-custom">Servings</Label>
                <Input
                  id="quantity-custom"
                  type="number"
                  min={1}
                  max={100}
                  placeholder="4"
                  value={quantity}
                  onChange={(e) => setQuantity(Math.max(1, parseInt(e.target.value) || 1))}
                  disabled={isLoading}
                />
                <p className="text-sm text-muted-foreground">Number of servings</p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="custom-ingredients">Ingredients (one per line)</Label>
                <Textarea
                  id="custom-ingredients"
                  rows={6}
                  value={customIngredients}
                  onChange={(e) => setCustomIngredients(e.target.value)}
                  disabled={isLoading}
                />
              </div>
            </TabsContent>
          </Tabs>

          {/* Profile Selection */}
          {profiles.length > 0 && (
            <div className="space-y-2">
              <Label>Use profile preferences</Label>
              <Select value={selectedProfileId} onValueChange={setSelectedProfileId}>
                <SelectTrigger>
                  <SelectValue placeholder="None (enter manually)" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">None (enter manually)</SelectItem>
                  {profiles.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name}
                      {(p.allergens?.length ?? 0) + (p.avoid_ingredients?.length ?? 0) > 0 &&
                        ` (${(p.allergens?.length ?? 0) + (p.avoid_ingredients?.length ?? 0)} preferences)`}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-sm text-muted-foreground">
                Pre-fill allergens and ingredients to avoid from a profile
              </p>
            </div>
          )}

          {/* Allergen Selection */}
          <div className="space-y-3">
            <Label>Allergens to Avoid</Label>
            <div className="grid grid-cols-2 gap-3">
              {ALLERGEN_OPTIONS.map((allergen) => (
                <div key={allergen.value} className="flex items-center space-x-2">
                  <Checkbox
                    id={allergen.value}
                    checked={selectedAllergens.includes(allergen.value)}
                    onCheckedChange={() => handleAllergenToggle(allergen.value)}
                    disabled={isLoading}
                  />
                  <label
                    htmlFor={allergen.value}
                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                  >
                    {allergen.label}
                  </label>
                </div>
              ))}
            </div>
          </div>

          {/* Avoid Ingredients */}
          <div className="space-y-2">
            <Label htmlFor="avoid-ingredients">
              Ingredients to Avoid (optional)
            </Label>
            <Input
              id="avoid-ingredients"
              placeholder="e.g. no dairy, gluten-free, allergic to peanuts, refined sugar"
              value={avoidIngredients}
              onChange={(e) => setAvoidIngredients(e.target.value)}
              disabled={isLoading}
            />
            <p className="text-sm text-muted-foreground">
              Specific items only — separate with commas. Not generic terms like &quot;light meal&quot;.
            </p>
          </div>

          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading ? "Analyzing..." : "Analyze Recipe"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
