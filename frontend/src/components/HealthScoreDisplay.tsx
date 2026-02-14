import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import type { HealthScore } from "@/types/api";

interface HealthScoreDisplayProps {
  healthScore: HealthScore;
  title?: string;
  showBreakdown?: boolean;
}

export function HealthScoreDisplay({
  healthScore,
  title = "Health Score",
  showBreakdown = true,
}: HealthScoreDisplayProps) {
  // Guard against null/undefined healthScore
  if (!healthScore || healthScore.score === null || healthScore.score === undefined) {
    return (
      <Card>
        <CardContent className="pt-6 text-center text-muted-foreground">
          No health score data available
        </CardContent>
      </Card>
    );
  }

  const getScoreColor = (score: number) => {
    if (score >= 80) return "bg-green-500";
    if (score >= 60) return "bg-blue-500";
    if (score >= 40) return "bg-yellow-500";
    if (score >= 20) return "bg-orange-500";
    return "bg-red-500";
  };

  const getRatingColor = (rating: string) => {
    const lowerRating = rating.toLowerCase();
    if (lowerRating === "excellent") return "bg-green-500";
    if (lowerRating === "good") return "bg-blue-500";
    if (lowerRating === "decent") return "bg-yellow-500";
    if (lowerRating === "bad") return "bg-orange-500";
    return "bg-red-500";
  };

  const scoreColor = getScoreColor(healthScore.score);
  const breakdown = healthScore.breakdown as any || {};

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">{title}</CardTitle>
          <Badge className={getRatingColor(healthScore.rating)}>
            {healthScore.rating}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Main Score Display */}
        <div className="text-center">
          <div className={`text-5xl font-bold ${scoreColor.replace('bg-', 'text-')}`}>
            {(healthScore.score || 0).toFixed(1)}
          </div>
          <p className="text-sm text-muted-foreground mt-1">out of 100</p>
        </div>

        {/* Visual Progress Bar */}
        <div className="space-y-2">
          <Progress value={healthScore.score || 0} className="h-3" />
        </div>

        {/* Score Breakdown */}
        {showBreakdown && breakdown && (
          <div className="space-y-2 pt-2 border-t">
            <p className="text-sm font-medium">Score Breakdown</p>
            <div className="space-y-1.5">
              {(breakdown.macronutrient_score !== undefined || breakdown.macro_impact !== undefined) && (
                <div className="flex justify-between items-center text-sm">
                  <span className="text-muted-foreground">Macronutrients</span>
                  <span className="font-medium">
                    {(breakdown.macronutrient_score ?? breakdown.macro_impact ?? 0).toFixed(1)}/40
                  </span>
                </div>
              )}
              {(breakdown.micronutrient_score !== undefined || breakdown.micro_impact !== undefined) && (
                <div className="flex justify-between items-center text-sm">
                  <span className="text-muted-foreground">Micronutrients</span>
                  <span className="font-medium">
                    {(breakdown.micronutrient_score ?? breakdown.micro_impact ?? 0).toFixed(1)}/30
                  </span>
                </div>
              )}
              {(breakdown.negative_factors_penalty !== undefined || breakdown.penalties !== undefined) && (
                <div className="flex justify-between items-center text-sm">
                  <span className="text-muted-foreground">Penalties</span>
                  <span className="font-medium text-red-500">
                    {(breakdown.negative_factors_penalty ?? breakdown.penalties ?? 0).toFixed(1)}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
