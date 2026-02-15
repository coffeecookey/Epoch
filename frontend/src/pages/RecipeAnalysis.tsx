import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { RecipeForm } from "@/components/RecipeForm";
import { HealthScoreDisplay } from "@/components/HealthScoreDisplay";
import { AnalysisResults } from "@/components/AnalysisResults";
import { SwapSuggestions } from "@/components/SwapSuggestions";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { recipeApi, ApiError } from "@/services/api";
import { addRecipe } from "@/store/recipeStore";
import type { FullAnalysisResponse, RecalculateResponse, AnalyzeRequest } from "@/types/api";
import { AlertCircle, ArrowLeft, BookmarkPlus } from "lucide-react";
import { toast } from "sonner";

const FALLBACK_TOAST_DISABLED_KEY = "nutritwin-disable-fallback-toast";

export default function RecipeAnalysis() {
  const navigate = useNavigate();
  const [step, setStep] = useState<"form" | "results" | "final">("form");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const [analysisData, setAnalysisData] = useState<FullAnalysisResponse | null>(null);
  const [finalData, setFinalData] = useState<RecalculateResponse | null>(null);
  const [requestData, setRequestData] = useState<AnalyzeRequest | null>(null);
  const [selectedImprovement, setSelectedImprovement] = useState<number>(0);
  const [selectedSwapsCount, setSelectedSwapsCount] = useState<number>(0);

  const handleAnalyze = async (data: AnalyzeRequest) => {
    setIsLoading(true);
    setError(null);
    setSaved(false);
    setRequestData(data);

    const { quantity: _q, ...apiPayload } = data;
    try {
      const response = await recipeApi.analyzeFull(apiPayload);
      setAnalysisData(response);
      setStep("results");

      // Show toast when CosyLab was unavailable and fallback LLM/rule-based was used
      if (response.used_llm_fallback) {
        const disabled = localStorage.getItem(FALLBACK_TOAST_DISABLED_KEY) === "true";
        if (!disabled) {
          const toastId = toast(
            "Fallback LLM is working",
            {
              description: (
                <button
                  type="button"
                  className="text-red-600 hover:underline cursor-pointer text-left"
                  onClick={() => {
                    localStorage.setItem(FALLBACK_TOAST_DISABLED_KEY, "true");
                    toast.dismiss(toastId);
                  }}
                >
                  Disable toaster
                </button>
              ),
            }
          );
        }
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Failed to analyze recipe. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleAcceptSwaps = async (selectedSwaps: Record<string, string>) => {
    if (!analysisData || !requestData) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await recipeApi.recalculate({
        recipe_name: analysisData.recipe_name,
        original_ingredients: analysisData.ingredients,
        accepted_swaps: selectedSwaps,
        allergens: requestData.allergens,
        avoid_ingredients: requestData.avoid_ingredients,
      });
      setFinalData(response);
      setStep("final");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Failed to recalculate recipe. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setStep("form");
    setAnalysisData(null);
    setFinalData(null);
    setRequestData(null);
    setError(null);
    setSaved(false);
    setSelectedImprovement(0);
    setSelectedSwapsCount(0);
  };

  const handleSwapSelectionChange = (improvement: number, swaps: Record<string, string>) => {
    setSelectedImprovement(improvement);
    setSelectedSwapsCount(Object.keys(swaps).length);
  };

  const handleSaveToRecipes = () => {
    if (!analysisData || !requestData) return;
    addRecipe({
      name: analysisData.recipe_name,
      quantity: requestData.quantity,
      analysisData,
      finalData: finalData ?? undefined,
    });
    setSaved(true);
  };

  return (
    <div className="min-h-screen bg-background">
      <div className="container mx-auto px-4 py-8 max-w-7xl">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="font-display text-4xl mb-2">Recipe Health Analyzer</h1>
          <p className="text-muted-foreground">
            Analyze your recipes, detect allergens, and get healthier ingredient suggestions
          </p>
        </div>

        {/* Error Alert */}
        {error && (
          <Alert variant="destructive" className="mb-6">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Form Step */}
        {step === "form" && (
          <RecipeForm onSubmit={handleAnalyze} isLoading={isLoading} />
        )}

        {/* Results Step */}
        {step === "results" && analysisData && (
          <div className="space-y-8">
            {/* Actions */}
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={handleReset} className="gap-2">
                <ArrowLeft className="h-4 w-4" />
                Analyze Another Recipe
              </Button>
              <Button
                variant={saved ? "secondary" : "default"}
                onClick={handleSaveToRecipes}
                className="gap-2"
                disabled={saved}
              >
                <BookmarkPlus className="h-4 w-4" />
                {saved ? "Saved to My Recipes" : "Save to My Recipes"}
              </Button>
              {saved && (
                <Button variant="outline" onClick={() => navigate("/recipes")}>
                  View Recipes
                </Button>
              )}
            </div>

            {/* Score Comparison */}
            <Card className="bg-gradient-to-r from-blue-50 to-purple-50">
              <CardContent className="pt-6">
                <h2 className="font-display text-2xl mb-6 text-center">Health Score Analysis</h2>
                <div className="grid md:grid-cols-2 gap-6">
                  <HealthScoreDisplay
                    healthScore={analysisData.original_health_score}
                    title="Original Score"
                    showBreakdown={true}
                  />
                  {selectedSwapsCount > 0 ? (
                    <HealthScoreDisplay
                      healthScore={{
                        score: Math.min(100, Math.max(0, analysisData.original_health_score.score + selectedImprovement)),
                        rating: analysisData.improved_health_score?.rating || "Good",
                        breakdown: analysisData.improved_health_score?.breakdown || {},
                      }}
                      title="Projected Score (Selected)"
                      showBreakdown={false}
                    />
                  ) : analysisData.improved_health_score ? (
                    <HealthScoreDisplay
                      healthScore={analysisData.improved_health_score}
                      title="Max Potential Score"
                      showBreakdown={true}
                    />
                  ) : (
                    <Card>
                      <CardContent className="pt-6 text-center text-muted-foreground">
                        No potential score available. No swaps suggested for this recipe.
                      </CardContent>
                    </Card>
                  )}
                </div>
                {selectedSwapsCount > 0 && (
                  <div className="text-center mt-4 p-4 bg-blue-100 rounded-lg">
                    <p className="text-blue-900 font-semibold">
                      Selected {selectedSwapsCount} swap{selectedSwapsCount > 1 ? 's' : ''}: +{selectedImprovement.toFixed(1)} points
                    </p>
                  </div>
                )}
                {selectedSwapsCount === 0 && analysisData.score_improvement > 0 && (
                  <div className="text-center mt-4 p-4 bg-green-100 rounded-lg">
                    <p className="text-green-800 font-semibold">
                      Max potential improvement: +{analysisData.score_improvement.toFixed(1)} points (all swaps)
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Recipe Details */}
            <AnalysisResults data={analysisData} type="initial" />

            <Separator className="my-8" />

            {/* Swap Suggestions */}
            <div>
              <h2 className="font-display text-2xl mb-6">Ingredient Improvements</h2>
              <SwapSuggestions
                swapSuggestions={analysisData.swap_suggestions}
                riskyIngredients={analysisData.risky_ingredients}
                scoreImprovement={analysisData.score_improvement}
                onAcceptSwaps={handleAcceptSwaps}
                onSelectionChange={handleSwapSelectionChange}
                isLoading={isLoading}
              />
            </div>
          </div>
        )}

        {/* Final Results Step */}
        {step === "final" && finalData && analysisData && (
          <div className="space-y-8">
            {/* Actions */}
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={handleReset} className="gap-2">
                <ArrowLeft className="h-4 w-4" />
                Analyze Another Recipe
              </Button>
              <Button
                variant={saved ? "secondary" : "default"}
                onClick={handleSaveToRecipes}
                className="gap-2"
                disabled={saved}
              >
                <BookmarkPlus className="h-4 w-4" />
                {saved ? "Saved to My Recipes" : "Save to My Recipes"}
              </Button>
              {saved && (
                <Button variant="outline" onClick={() => navigate("/recipes")}>
                  View Recipes
                </Button>
              )}
            </div>

            {/* Score Comparison */}
            <Card className="bg-gradient-to-r from-green-50 to-emerald-50">
              <CardContent className="pt-6">
                <h2 className="font-display text-2xl mb-6 text-center">Final Results</h2>
                <div className="grid md:grid-cols-2 gap-6">
                  <HealthScoreDisplay
                    healthScore={analysisData.original_health_score}
                    title="Before"
                    showBreakdown={false}
                  />
                  <HealthScoreDisplay
                    healthScore={finalData.final_health_score}
                    title="After"
                    showBreakdown={true}
                  />
                </div>
                {finalData.total_score_improvement > 0 && (
                  <div className="text-center mt-4 p-4 bg-green-100 rounded-lg">
                    <p className="text-green-800 font-semibold text-lg">
                      Total improvement: +{finalData.total_score_improvement.toFixed(1)} points! 🎉
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Final Recipe Details */}
            <AnalysisResults data={finalData} type="final" />
          </div>
        )}
      </div>
    </div>
  );
}
