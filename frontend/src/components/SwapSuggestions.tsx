import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ArrowRight, TrendingUp, Star, Beaker, ChevronDown, ChevronUp, ShieldAlert } from "lucide-react";

interface SubstituteOption {
  name: string;
  flavor_match: number;
  health_improvement: number;
  reason?: string;
  shared_molecules?: string[];
}

interface SwapSuggestionsProps {
  swapSuggestions: Array<Record<string, any>>;
  riskyIngredients: Array<Record<string, any>>;
  scoreImprovement: number | null;
  onAcceptSwaps: (selectedSwaps: Record<string, string>) => void;
  onSelectionChange?: (selectedImprovement: number, selectedSwaps: Record<string, string>) => void;
  isLoading?: boolean;
}

/** Visual flavor-match bar colored by the app theme. */
function FlavorBar({ value }: { value: number }) {
  const pct = Math.min(100, Math.max(0, value));
  // Use watermelon for high, sunrise for mid, destructive for low
  const barColor =
    pct >= 70
      ? "bg-[hsl(var(--success))]"
      : pct >= 40
        ? "bg-[hsl(var(--warning))]"
        : "bg-[hsl(var(--destructive))]";

  return (
    <div className="flex items-center gap-2 min-w-[120px]">
      <div className="h-2 flex-1 rounded-full bg-muted overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-300 ${barColor}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs font-medium tabular-nums w-9 text-right text-muted-foreground">
        {pct.toFixed(0)}%
      </span>
    </div>
  );
}

/** Molecule pills — small tags showing shared flavor compounds. */
function MoleculePills({ molecules }: { molecules: string[] }) {
  if (!molecules || molecules.length === 0) return null;
  const shown = molecules.slice(0, 3);
  const rest = molecules.length - shown.length;

  return (
    <TooltipProvider>
      <div className="flex flex-wrap gap-1 mt-1.5">
        {shown.map((mol) => (
          <Tooltip key={mol}>
            <TooltipTrigger asChild>
              <span className="inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-[10px] font-medium bg-[hsl(var(--accent)/0.15)] text-[hsl(var(--accent))] border border-[hsl(var(--accent)/0.25)] cursor-default">
                <Beaker className="h-2.5 w-2.5" />
                {mol}
              </span>
            </TooltipTrigger>
            <TooltipContent side="top" className="text-xs">
              Shared flavor molecule
            </TooltipContent>
          </Tooltip>
        ))}
        {rest > 0 && (
          <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium text-muted-foreground bg-muted">
            +{rest} more
          </span>
        )}
      </div>
    </TooltipProvider>
  );
}

export function SwapSuggestions({
  swapSuggestions,
  riskyIngredients,
  scoreImprovement,
  onAcceptSwaps,
  onSelectionChange,
  isLoading = false,
}: SwapSuggestionsProps) {
  const [selectedSwaps, setSelectedSwaps] = useState<Record<string, string>>({});
  const [expandedCards, setExpandedCards] = useState<Record<string, boolean>>({});

  // Calculate cumulative health improvement for selected swaps
  const calculateSelectedImprovement = () => {
    let total = 0;
    Object.entries(selectedSwaps).forEach(([original, substituteName]) => {
      const swap = swapSuggestions.find(s => s.original === original);
      if (swap) {
        const alternatives: SubstituteOption[] = swap.alternatives || [swap.substitute];
        const selected = alternatives.find(alt => alt.name === substituteName);
        if (selected) {
          total += selected.health_improvement || 0;
        }
      }
    });
    return total;
  };

  const selectedImprovement = calculateSelectedImprovement();
  const hasSelections = Object.keys(selectedSwaps).length > 0;

  // Notify parent component when selections change
  useEffect(() => {
    if (onSelectionChange) {
      onSelectionChange(selectedImprovement, selectedSwaps);
    }
  }, [selectedSwaps, selectedImprovement, onSelectionChange]);

  const handleSwapSelection = (original: string, substitute: string) => {
    setSelectedSwaps((prev) => ({
      ...prev,
      [original]: substitute,
    }));
  };

  const handleSkipIngredient = (original: string) => {
    setSelectedSwaps((prev) => {
      const newSwaps = { ...prev };
      delete newSwaps[original];
      return newSwaps;
    });
  };

  const toggleExpanded = (original: string) => {
    setExpandedCards((prev) => ({ ...prev, [original]: !prev[original] }));
  };

  const handleSubmit = () => {
    onAcceptSwaps(selectedSwaps);
  };

  const getRiskyReason = (ingredientName: string) => {
    const risky = riskyIngredients.find(
      (r) => r.name.toLowerCase() === ingredientName.toLowerCase()
    );
    return risky?.reason || "";
  };

  if (swapSuggestions.length === 0) {
    return (
      <Alert>
        <AlertDescription>
          No ingredient swaps suggested. Your recipe looks good!
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header Card */}
      <Card className="border-[hsl(var(--secondary))] bg-[hsl(var(--secondary)/0.12)]">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex-1">
              <CardTitle className="font-display text-2xl">Ingredient Swap Suggestions</CardTitle>
              <CardDescription className="mt-1">
                Select healthier alternatives to improve your recipe — ranked by taste preservation
              </CardDescription>
            </div>
            <div className="flex flex-col items-end gap-2">
              {scoreImprovement != null && scoreImprovement > 0 && (
                <Badge variant="outline" className="text-muted-foreground border-muted-foreground flex items-center gap-1 text-xs px-2 py-1">
                  <TrendingUp className="h-3 w-3" />
                  Max: +{scoreImprovement.toFixed(1)} pts
                </Badge>
              )}
              {hasSelections && (
                <Badge className="bg-[hsl(var(--success))] text-white flex items-center gap-1 text-sm px-3 py-1.5 shadow-sm">
                  <TrendingUp className="h-4 w-4" />
                  Selected: +{selectedImprovement.toFixed(1)} pts
                </Badge>
              )}
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* Swap Cards */}
      <div className="space-y-4">
        {swapSuggestions.map((swap, index) => {
          // Get all alternatives, or fall back to just the top substitute
          const alternatives: SubstituteOption[] =
            swap.alternatives && swap.alternatives.length > 0
              ? swap.alternatives
              : swap.substitute
                ? [swap.substitute]
                : [];

          if (alternatives.length === 0) return null;

          const topSub = alternatives[0];
          const hasMore = alternatives.length > 1;
          const isExpanded = expandedCards[swap.original] ?? false;
          const visibleAlternatives = isExpanded ? alternatives : [topSub];

          return (
            <Card key={index} className="overflow-hidden border-border/60 shadow-sm">
              {/* Risky ingredient header */}
              <CardHeader className="bg-muted/40 pb-3 pt-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 space-y-1">
                    <CardTitle className="text-base font-semibold flex items-center gap-2">
                      <ShieldAlert className="h-4 w-4 text-[hsl(var(--destructive))]" />
                      {swap.original}
                    </CardTitle>
                    {getRiskyReason(swap.original) && (
                      <CardDescription className="text-xs leading-relaxed">
                        {getRiskyReason(swap.original)}
                      </CardDescription>
                    )}
                  </div>
                  <Badge variant="destructive" className="shrink-0 text-[10px] uppercase tracking-wide">
                    Risky
                  </Badge>
                </div>
              </CardHeader>

              <CardContent className="pt-4 pb-4">
                <RadioGroup
                  value={selectedSwaps[swap.original] || "skip"}
                  onValueChange={(value) => {
                    if (value === "skip") {
                      handleSkipIngredient(swap.original);
                    } else {
                      handleSwapSelection(swap.original, value);
                    }
                  }}
                >
                  <div className="space-y-2">
                    {visibleAlternatives.map((alt, altIdx) => {
                      const isSelected = selectedSwaps[swap.original] === alt.name;
                      return (
                        <div
                          key={altIdx}
                          className={`flex items-start space-x-3 p-3 rounded-lg border transition-colors ${
                            isSelected
                              ? "border-[hsl(var(--primary))] bg-[hsl(var(--primary)/0.08)]"
                              : "border-border/50 hover:bg-muted/40"
                          }`}
                        >
                          <RadioGroupItem
                            value={alt.name}
                            id={`${swap.original}-${altIdx}`}
                            className="mt-1"
                          />
                          <Label
                            htmlFor={`${swap.original}-${altIdx}`}
                            className="flex-1 cursor-pointer space-y-1.5"
                          >
                            <div className="flex items-center justify-between gap-2 flex-wrap">
                              <span className="font-medium text-sm">{alt.name}</span>
                              <div className="flex items-center gap-3">
                                {/* Health improvement badge */}
                                <Badge
                                  variant="outline"
                                  className="text-[hsl(var(--success))] border-[hsl(var(--success)/0.4)] text-xs px-2"
                                >
                                  +{(alt.health_improvement || 0).toFixed(1)}
                                </Badge>
                                {/* Flavor match bar */}
                                <div className="hidden sm:flex items-center gap-1.5">
                                  <Star className="h-3 w-3 fill-[hsl(var(--warning))] text-[hsl(var(--warning))]" />
                                  <FlavorBar value={alt.flavor_match || 0} />
                                </div>
                              </div>
                            </div>

                            {/* Shared molecules */}
                            <MoleculePills molecules={alt.shared_molecules || []} />

                            {/* Explanation */}
                            {alt.reason && (
                              <p className="text-xs text-muted-foreground leading-relaxed">
                                {alt.reason}
                              </p>
                            )}
                          </Label>
                        </div>
                      );
                    })}

                    {/* Show more / less toggle */}
                    {hasMore && (
                      <button
                        type="button"
                        onClick={() => toggleExpanded(swap.original)}
                        className="flex items-center gap-1 text-xs font-medium text-[hsl(var(--accent))] hover:text-[hsl(var(--accent)/0.8)] transition-colors pl-9 py-1"
                      >
                        {isExpanded ? (
                          <>
                            <ChevronUp className="h-3 w-3" />
                            Show fewer alternatives
                          </>
                        ) : (
                          <>
                            <ChevronDown className="h-3 w-3" />
                            Show {alternatives.length - 1} more alternative{alternatives.length - 1 > 1 ? "s" : ""}
                          </>
                        )}
                      </button>
                    )}

                    {/* Keep original option */}
                    <div className="flex items-start space-x-3 p-3 rounded-lg border border-dashed border-border/50 hover:bg-muted/30 transition-colors">
                      <RadioGroupItem
                        value="skip"
                        id={`${swap.original}-skip`}
                        className="mt-1"
                      />
                      <Label
                        htmlFor={`${swap.original}-skip`}
                        className="flex-1 cursor-pointer"
                      >
                        <span className="font-medium text-sm text-muted-foreground">
                          Keep original ingredient
                        </span>
                      </Label>
                    </div>
                  </div>
                </RadioGroup>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Action Button */}
      <div className="flex justify-end">
        <Button
          onClick={handleSubmit}
          disabled={isLoading || Object.keys(selectedSwaps).length === 0}
          size="lg"
          className="gap-2"
        >
          {isLoading ? (
            "Recalculating..."
          ) : (
            <>
              Apply Selected Swaps ({Object.keys(selectedSwaps).length})
              <ArrowRight className="h-4 w-4" />
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
