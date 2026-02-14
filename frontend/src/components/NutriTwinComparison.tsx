import { motion } from "framer-motion";
import { ArrowRight, Sparkles, Atom, ThumbsUp, AlertCircle, ChevronRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface SwapItem {
  original: string;
  optimized: string;
  reason: string;
}

const swaps: SwapItem[] = [
  { original: "All-purpose flour", optimized: "Almond flour", reason: "Lower glycemic index, +6g protein" },
  { original: "White sugar", optimized: "Coconut sugar", reason: "Lower GI, retains minerals" },
  { original: "Heavy cream", optimized: "Coconut cream", reason: "Dairy-free, similar texture" },
  { original: "Butter", optimized: "Avocado oil", reason: "Heart-healthy fats, similar richness" },
];

const NutriTwinComparison = () => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2 }}
    >
      <div className="mb-4 flex items-center gap-2">
        <Sparkles className="h-5 w-5 text-accent" />
        <h2 className="font-display text-2xl">NutriTwin Comparison</h2>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Original */}
        <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="font-display text-lg">Original Recipe</h3>
            <Badge variant="outline" className="border-sunrise text-sunrise">
              <AlertCircle className="mr-1 h-3 w-3" />
              Poor
            </Badge>
          </div>

          <div className="mb-4">
            <div className="mb-2 flex justify-between text-sm">
              <span className="text-muted-foreground">Health Score</span>
              <span className="font-semibold text-sunrise">38/100</span>
            </div>
            <div className="h-3 overflow-hidden rounded-full bg-muted">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: "38%" }}
                transition={{ duration: 1, delay: 0.5 }}
                className="h-full rounded-full bg-sunrise"
              />
            </div>
          </div>

          <div className="space-y-2">
            <NutrientRow label="Calories" value="520 kcal" highlight="warning" />
            <NutrientRow label="Sugar" value="42g" highlight="warning" />
            <NutrientRow label="Saturated Fat" value="18g" highlight="warning" />
            <NutrientRow label="Fiber" value="1.2g" highlight="low" />
            <NutrientRow label="Protein" value="6g" highlight="low" />
          </div>
        </div>

        {/* Optimized */}
        <div className="rounded-2xl border border-primary/30 bg-card p-5 shadow-sm ring-1 ring-primary/10">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="font-display text-lg">Optimized Recipe</h3>
            <Badge className="border-0 bg-primary/20 text-primary-foreground">
              <ThumbsUp className="mr-1 h-3 w-3" />
              Good
            </Badge>
          </div>

          <div className="mb-4">
            <div className="mb-2 flex justify-between text-sm">
              <span className="text-muted-foreground">Health Score</span>
              <span className="font-semibold text-foreground">76/100</span>
            </div>
            <div className="h-3 overflow-hidden rounded-full bg-muted">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: "76%" }}
                transition={{ duration: 1, delay: 0.7 }}
                className="h-full rounded-full bg-primary"
              />
            </div>
          </div>

          <div className="space-y-2">
            <NutrientRow label="Calories" value="380 kcal" highlight="good" />
            <NutrientRow label="Sugar" value="18g" highlight="good" />
            <NutrientRow label="Saturated Fat" value="6g" highlight="good" />
            <NutrientRow label="Fiber" value="4.8g" highlight="good" />
            <NutrientRow label="Protein" value="12g" highlight="good" />
          </div>
        </div>
      </div>

      {/* Ingredient Swaps */}
      <div className="mt-4 rounded-2xl border border-border bg-card p-5 shadow-sm">
        <div className="mb-4 flex items-center gap-2">
          <Atom className="h-5 w-5 text-accent" />
          <h3 className="font-display text-lg">Molecular Mapping — Ingredient Swaps</h3>
        </div>
        <p className="mb-4 text-sm text-muted-foreground">
          Taste integrity preserved through molecular flavor profiling
        </p>

        <div className="space-y-3">
          {swaps.map((swap, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.3 + i * 0.1 }}
              className="flex items-center gap-3 rounded-xl border border-border bg-background p-3"
            >
              <div className="flex-1">
                <span className="text-sm font-medium text-muted-foreground line-through">
                  {swap.original}
                </span>
              </div>
              <ArrowRight className="h-4 w-4 shrink-0 text-primary" />
              <div className="flex-1">
                <span className="text-sm font-semibold">{swap.optimized}</span>
              </div>
              <div className="hidden text-xs text-muted-foreground sm:block">
                {swap.reason}
              </div>
              <Atom className="h-4 w-4 shrink-0 text-accent/60" />
            </motion.div>
          ))}
        </div>
      </div>
    </motion.div>
  );
};

const NutrientRow = ({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight: "warning" | "good" | "low";
}) => (
  <div className="flex items-center justify-between rounded-lg bg-background px-3 py-2">
    <span className="text-sm text-muted-foreground">{label}</span>
    <span
      className={`text-sm font-semibold ${
        highlight === "warning"
          ? "text-sunrise"
          : highlight === "good"
          ? "text-foreground"
          : "text-muted-foreground"
      }`}
    >
      {value}
    </span>
  </div>
);

export default NutriTwinComparison;
