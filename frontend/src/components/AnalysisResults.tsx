import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { AlertTriangle, CheckCircle, Info } from "lucide-react";
import type { FullAnalysisResponse, RecalculateResponse } from "@/types/api";

interface AnalysisResultsProps {
  data: FullAnalysisResponse | RecalculateResponse;
  type: "initial" | "final";
}

export function AnalysisResults({ data, type }: AnalysisResultsProps) {
  const isFinal = type === "final";
  const ingredients = isFinal 
    ? (data as RecalculateResponse).final_ingredients 
    : (data as FullAnalysisResponse).ingredients;

  const allergens = data.detected_allergens || [];
  const userWarnings = data.user_allergen_warnings || [];
  const flaggedIngredients = data.flagged_avoid_ingredients || [];
  const explanation = data.explanation || "";

  return (
    <div className="space-y-6">
      {/* Recipe Info Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>{data.recipe_name}</span>
            {isFinal && (
              <Badge variant="outline" className="text-green-600 border-green-600">
                Final Results
              </Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Ingredients List */}
          <div>
            <h3 className="font-medium mb-2">Ingredients ({ingredients.length})</h3>
            <div className="flex flex-wrap gap-2">
              {ingredients.map((ingredient, index) => (
                <Badge key={index} variant="secondary">
                  {ingredient}
                </Badge>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Allergen Warnings */}
      {(allergens.length > 0 || userWarnings.length > 0) && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Allergen Warning</AlertTitle>
          <AlertDescription className="space-y-2 mt-2">
            {allergens.length > 0 && (
              <div>
                <span className="font-medium">Detected allergens: </span>
                {allergens
                  .map((a) => (typeof a === 'string' ? a : a?.allergen_category || a?.category || 'Unknown'))
                  .join(", ")}
              </div>
            )}
            {userWarnings.length > 0 && (
              <div>
                <span className="font-medium">Your allergen concerns: </span>
                {userWarnings
                  .map((w) => (typeof w === 'string' ? w : w?.allergen_category || w?.category || 'Unknown'))
                  .join(", ")}
              </div>
            )}
          </AlertDescription>
        </Alert>
      )}

      {/* Flagged Ingredients */}
      {flaggedIngredients.length > 0 && (
        <Alert>
          <Info className="h-4 w-4" />
          <AlertTitle>Avoided Ingredients Found</AlertTitle>
          <AlertDescription>
            The following ingredients you wanted to avoid were found: {flaggedIngredients.join(", ")}
          </AlertDescription>
        </Alert>
      )}

      {/* Explanation */}
      {explanation && (
        <Card>
          <CardHeader>
            <CardTitle className="font-display text-xl">Health Analysis</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">{explanation}</p>
          </CardContent>
        </Card>
      )}

      {/* Nutrition Details */}
      <Accordion type="single" collapsible className="w-full">
        <AccordionItem value="nutrition">
          <AccordionTrigger className="text-base font-semibold">
            Nutritional Information
          </AccordionTrigger>
          <AccordionContent>
            <div className="space-y-4">
              {/* Macronutrients */}
              {data.nutrition && Object.keys(data.nutrition).length > 0 && (
                <div>
                  <h4 className="font-medium mb-2">Macronutrients</h4>
                  <div className="grid grid-cols-2 gap-2">
                    {Object.entries(data.nutrition).map(([key, value]) => (
                      <div key={key} className="flex justify-between p-2 rounded bg-muted/50">
                        <span className="text-sm capitalize">{key.replace(/_/g, " ")}</span>
                        <span className="text-sm font-medium">
                          {typeof value === 'number' ? `${value.toFixed(2)}g` : value}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Micronutrients */}
              {data.micro_nutrition && (
                <div>
                  {/* Check if it's nested structure (vitamins/minerals) */}
                  {data.micro_nutrition.vitamins || data.micro_nutrition.minerals ? (
                    <>
                      {data.micro_nutrition.vitamins && Object.keys(data.micro_nutrition.vitamins).length > 0 && (
                        <div className="mb-4">
                          <h4 className="font-medium mb-2">Vitamins</h4>
                          <div className="grid grid-cols-2 gap-2">
                            {Object.entries(data.micro_nutrition.vitamins).map(([key, value]) => (
                              <div key={key} className="flex justify-between p-2 rounded bg-muted/50">
                                <span className="text-sm capitalize">{key.replace(/_/g, " ")}</span>
                                <span className="text-sm font-medium">
                                  {typeof value === 'number' ? `${value.toFixed(2)}mg` : String(value)}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      {data.micro_nutrition.minerals && Object.keys(data.micro_nutrition.minerals).length > 0 && (
                        <div>
                          <h4 className="font-medium mb-2">Minerals</h4>
                          <div className="grid grid-cols-2 gap-2">
                            {Object.entries(data.micro_nutrition.minerals).map(([key, value]) => (
                              <div key={key} className="flex justify-between p-2 rounded bg-muted/50">
                                <span className="text-sm capitalize">{key.replace(/_/g, " ")}</span>
                                <span className="text-sm font-medium">
                                  {typeof value === 'number' ? `${value.toFixed(2)}mg` : String(value)}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  ) : (
                    // Flat structure (fallback)
                    Object.keys(data.micro_nutrition).length > 0 && (
                      <div>
                        <h4 className="font-medium mb-2">Micronutrients</h4>
                        <div className="grid grid-cols-2 gap-2">
                          {Object.entries(data.micro_nutrition).map(([key, value]) => (
                            <div key={key} className="flex justify-between p-2 rounded bg-muted/50">
                              <span className="text-sm capitalize">{key.replace(/_/g, " ")}</span>
                              <span className="text-sm font-medium">
                                {typeof value === 'number' ? `${value.toFixed(2)}mg` : String(value)}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )
                  )}
                </div>
              )}
            </div>
          </AccordionContent>
        </AccordionItem>

        {/* Similar Recipe Recommendation (only for initial analysis) */}
        {!isFinal && (data as FullAnalysisResponse).similar_recipe && (
          <AccordionItem value="recommendation">
            <AccordionTrigger className="text-base font-semibold">
              Similar Healthier Recipe
            </AccordionTrigger>
            <AccordionContent>
              <Card>
                <CardContent className="pt-6 space-y-2">
                  <div className="flex items-center justify-between">
                    <h4 className="font-semibold">
                      {(data as FullAnalysisResponse).similar_recipe!.name}
                    </h4>
                    <Badge className="bg-green-500">
                      Score: {(data as FullAnalysisResponse).similar_recipe!.health_score.toFixed(1)}
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Similarity: {((data as FullAnalysisResponse).similar_recipe!.similarity_score * 100).toFixed(0)}%
                  </p>
                  <p className="text-sm">
                    {(data as FullAnalysisResponse).similar_recipe!.reason}
                  </p>
                </CardContent>
              </Card>
            </AccordionContent>
          </AccordionItem>
        )}
      </Accordion>

      {/* Success Message for Final Results */}
      {isFinal && (
        <Alert className="border-green-200 bg-green-50">
          <CheckCircle className="h-4 w-4 text-green-600" />
          <AlertTitle className="text-green-900">Recipe Optimized!</AlertTitle>
          <AlertDescription className="text-green-800">
            Your recipe has been successfully improved with the selected ingredient swaps.
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}
