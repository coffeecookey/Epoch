import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ArrowRight, TrendingUp, Star } from "lucide-react";

interface SwapSuggestionsProps {
  swapSuggestions: Array<Record<string, any>>;
  riskyIngredients: Array<Record<string, any>>;
  scoreImprovement: number | null;
  onAcceptSwaps: (selectedSwaps: Record<string, string>) => void;
  isLoading?: boolean;
}

export function SwapSuggestions({
  swapSuggestions,
  riskyIngredients,
  scoreImprovement,
  onAcceptSwaps,
  isLoading = false,
}: SwapSuggestionsProps) {
  const [selectedSwaps, setSelectedSwaps] = useState<Record<string, string>>({});

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
      <Card className="border-blue-200 bg-blue-50/50">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="font-display text-2xl">Ingredient Swap Suggestions</CardTitle>
              <CardDescription className="mt-1">
                Select healthier alternatives to improve your recipe
              </CardDescription>
            </div>
            {scoreImprovement > 0 && (
              <Badge variant="outline" className="text-green-600 border-green-600 flex items-center gap-1">
                <TrendingUp className="h-4 w-4" />
                +{scoreImprovement.toFixed(1)} points
              </Badge>
            )}
          </div>
        </CardHeader>
      </Card>

      {/* Swap Options */}
      <div className="space-y-4">
        {swapSuggestions.map((swap, index) => {
          const substitute = swap.substitute;
          if (!substitute) return null;

          return (
            <Card key={index} className="overflow-hidden">
              <CardHeader className="bg-muted/50">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <CardTitle className="text-base font-semibold">
                      {swap.original}
                    </CardTitle>
                    {getRiskyReason(swap.original) && (
                      <CardDescription className="mt-1">
                        {getRiskyReason(swap.original)}
                      </CardDescription>
                    )}
                  </div>
                  <Badge variant="destructive" className="shrink-0">
                    Risky
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="pt-6">
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
                  {/* Substitute Options */}
                  <div className="space-y-3">
                    <div
                      className="flex items-start space-x-3 p-3 rounded-lg border hover:bg-muted/50 transition-colors"
                    >
                      <RadioGroupItem
                        value={substitute.name}
                        id={`${swap.original}-0`}
                        className="mt-1"
                      />
                      <Label
                        htmlFor={`${swap.original}-0`}
                        className="flex-1 cursor-pointer space-y-2"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-medium">{substitute.name}</span>
                          <div className="flex items-center gap-2">
                            <Badge variant="outline" className="text-green-600">
                              +{(substitute.health_improvement || 0).toFixed(1)}
                            </Badge>
                            <div className="flex items-center gap-1 text-sm text-muted-foreground">
                              <Star className="h-3 w-3 fill-yellow-400 text-yellow-400" />
                              <span>{((substitute.flavor_match || 0) / 10).toFixed(1)}/10</span>
                            </div>
                          </div>
                        </div>
                        {substitute.reason && (
                          <p className="text-sm text-muted-foreground">
                            {substitute.reason}
                          </p>
                        )}
                      </Label>
                    </div>

                    {/* Keep Original Option */}
                    <div className="flex items-start space-x-3 p-3 rounded-lg border hover:bg-muted/50 transition-colors">
                      <RadioGroupItem
                        value="skip"
                        id={`${swap.original}-skip`}
                        className="mt-1"
                      />
                      <Label
                        htmlFor={`${swap.original}-skip`}
                        className="flex-1 cursor-pointer"
                      >
                        <span className="font-medium text-muted-foreground">
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
