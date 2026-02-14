import { useMemo, useState } from "react";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DIETARY_PRESETS,
  ALLERGEN_OPTIONS,
  INVALID_AVOID_TERMS,
} from "@/types/api";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";

function isValidAvoidTerm(term: string): { valid: boolean; error?: string } {
  const t = term.trim().toLowerCase();
  if (t.length < 2) return { valid: false, error: "Enter at least 2 characters" };
  const words = t.split(/\s+/);
  for (const w of words) {
    if (INVALID_AVOID_TERMS.has(w)) {
      return {
        valid: false,
        error: `"${term}" is too generic. Use specific items like: no dairy, gluten-free, allergic to peanuts, avoid sugar`,
      };
    }
  }
  return { valid: true };
}

interface DietaryCustomizationProps {
  allergens: string[];
  avoidIngredients: string[];
  onChange: (allergens: string[], avoidIngredients: string[]) => void;
  disabled?: boolean;
  compact?: boolean;
}

export function DietaryCustomization({
  allergens,
  avoidIngredients,
  onChange,
  disabled = false,
  compact = false,
}: DietaryCustomizationProps) {
  const [customAvoidInput, setCustomAvoidInput] = useState("");
  const [customAvoidError, setCustomAvoidError] = useState<string | null>(null);

  const selectedPresets = useMemo(() => {
    return DIETARY_PRESETS.filter((p) => {
      const hasAllAllergens = p.allergens.every((a) => allergens.includes(a));
      const hasAllAvoid = p.avoid_ingredients.every((a) =>
        avoidIngredients.some(
          (ai) => ai.toLowerCase() === a.toLowerCase()
        )
      );
      return hasAllAllergens && hasAllAvoid && (p.allergens.length > 0 || p.avoid_ingredients.length > 0);
    }).map((p) => p.id);
  }, [allergens, avoidIngredients]);

  const togglePreset = (presetId: string) => {
    const preset = DIETARY_PRESETS.find((p) => p.id === presetId);
    if (!preset) return;
    const isSelected = selectedPresets.includes(presetId);
    if (isSelected) {
      const newAllergens = allergens.filter((a) => !preset.allergens.includes(a));
      const newAvoid = avoidIngredients.filter(
        (a) => !preset.avoid_ingredients.some((pa) => pa.toLowerCase() === a.toLowerCase())
      );
      onChange(newAllergens, newAvoid);
    } else {
      const newAllergens = [...new Set([...allergens, ...preset.allergens])];
      const newAvoid = [...new Set([...avoidIngredients, ...preset.avoid_ingredients])];
      onChange(newAllergens, newAvoid);
    }
  };

  const toggleAllergen = (value: string) => {
    if (allergens.includes(value)) {
      onChange(
        allergens.filter((a) => a !== value),
        avoidIngredients
      );
    } else {
      onChange([...allergens, value], avoidIngredients);
    }
  };

  const addAvoidIngredient = () => {
    setCustomAvoidError(null);
    const trimmed = customAvoidInput.trim();
    if (!trimmed) return;
    const { valid, error } = isValidAvoidTerm(trimmed);
    if (!valid) {
      setCustomAvoidError(error ?? "Invalid");
      return;
    }
    const normalized = trimmed.toLowerCase();
    if (avoidIngredients.some((a) => a.toLowerCase() === normalized)) {
      setCustomAvoidInput("");
      return;
    }
    onChange(allergens, [...avoidIngredients, trimmed]);
    setCustomAvoidInput("");
  };

  const removeAvoidIngredient = (item: string) => {
    onChange(
      allergens,
      avoidIngredients.filter((a) => a !== item)
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addAvoidIngredient();
    }
  };

  const presetSection = (
    <div className="space-y-2">
      <Label>Dietary & health presets</Label>
      <p className="text-sm text-muted-foreground">
        Common conditions that add specific allergens and ingredients to avoid
      </p>
      <div className="flex flex-wrap gap-2">
        {DIETARY_PRESETS.map((preset) => (
          <Badge
            key={preset.id}
            variant={selectedPresets.includes(preset.id) ? "default" : "outline"}
            className={`cursor-pointer transition-colors ${
              selectedPresets.includes(preset.id)
                ? "bg-pink-500 hover:bg-pink-600"
                : "hover:bg-muted"
            } ${compact ? "text-xs py-1" : ""}`}
            onClick={() => !disabled && togglePreset(preset.id)}
          >
            {preset.label}
          </Badge>
        ))}
      </div>
    </div>
  );

  const allergenSection = (
    <div className="space-y-2">
      <Label>Allergens</Label>
      <p className="text-sm text-muted-foreground">
        Foods you are allergic or sensitive to
      </p>
      <div className={compact ? "grid grid-cols-2 gap-2" : "grid grid-cols-2 md:grid-cols-4 gap-3"}>
        {ALLERGEN_OPTIONS.map((opt) => (
          <div key={opt.value} className="flex items-center space-x-2">
            <Checkbox
              id={`allergen-${opt.value}`}
              checked={allergens.includes(opt.value)}
              onCheckedChange={() => toggleAllergen(opt.value)}
              disabled={disabled}
            />
            <label
              htmlFor={`allergen-${opt.value}`}
              className="text-sm font-medium leading-none cursor-pointer"
            >
              {opt.label}
            </label>
          </div>
        ))}
      </div>
    </div>
  );

  const customAvoidSection = (
    <div className="space-y-2">
      <Label>Additional ingredients to avoid</Label>
      <p className="text-sm text-muted-foreground">
        Specific items only — e.g. no dairy, gluten-free, allergic to peanuts, avoid sugar. Not generic terms like &quot;light meal&quot;.
      </p>
      <div className="flex gap-2">
        <Input
          placeholder="e.g. no dairy, gluten, peanuts, refined sugar"
          value={customAvoidInput}
          onChange={(e) => {
            setCustomAvoidInput(e.target.value);
            setCustomAvoidError(null);
          }}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          className={customAvoidError ? "border-destructive" : ""}
        />
        <Button
          type="button"
          variant="secondary"
          onClick={addAvoidIngredient}
          disabled={disabled || !customAvoidInput.trim()}
        >
          Add
        </Button>
      </div>
      {customAvoidError && (
        <p className="text-sm text-destructive">{customAvoidError}</p>
      )}
      {avoidIngredients.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-2">
          {avoidIngredients.map((item) => (
            <Badge
              key={item}
              variant="secondary"
              className="gap-1 pr-1"
            >
              {item}
              {!disabled && (
                <button
                  type="button"
                  onClick={() => removeAvoidIngredient(item)}
                  className="rounded-full hover:bg-muted p-0.5"
                  aria-label={`Remove ${item}`}
                >
                  <X className="h-3 w-3" />
                </button>
              )}
            </Badge>
          ))}
        </div>
      )}
    </div>
  );

  return (
    <div className={compact ? "space-y-4" : "space-y-6"}>
      {presetSection}
      {allergenSection}
      {customAvoidSection}
    </div>
  );
}
