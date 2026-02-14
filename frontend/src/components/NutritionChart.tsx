import { motion } from "framer-motion";
import { AlertTriangle, CheckCircle, Info } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";

const macroData = [
  { name: "Protein", original: 6, optimized: 12 },
  { name: "Carbs", original: 68, optimized: 42 },
  { name: "Fat", original: 24, optimized: 18 },
  { name: "Fiber", original: 1.2, optimized: 4.8 },
  { name: "Sugar", original: 42, optimized: 18 },
];

const microData = [
  { name: "Vitamin A", value: 15 },
  { name: "Vitamin C", value: 8 },
  { name: "Iron", value: 22 },
  { name: "Calcium", value: 35 },
  { name: "Potassium", value: 20 },
];

const PIE_COLORS = [
  "hsl(349, 30%, 73%)",   // berry
  "hsl(209, 30%, 80%)",   // sky
  "hsl(62, 65%, 70%)",    // watermelon
  "hsl(16, 78%, 72%)",    // sunrise
  "hsl(30, 28%, 80%)",    // linen dark
];

const warnings = [
  {
    type: "warning" as const,
    text: "High sodium content detected (820mg). Consider reducing salt by 40%.",
  },
  {
    type: "warning" as const,
    text: "Trans fats present from hydrogenated oils. Swap with cold-pressed alternatives.",
  },
  {
    type: "success" as const,
    text: "Good source of dietary fiber after optimization (+300% increase).",
  },
  {
    type: "info" as const,
    text: "Adding chia seeds would boost Omega-3 content significantly.",
  },
];

const NutritionChart = () => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.3 }}
    >
      <h2 className="mb-4 font-display text-2xl">Nutrition Analysis</h2>

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Macro Bar Chart */}
        <div className="rounded-2xl border border-border bg-card p-5 shadow-sm lg:col-span-2">
          <h3 className="mb-1 font-display text-lg">Macronutrient Comparison</h3>
          <p className="mb-4 text-xs text-muted-foreground">Original vs Optimized (grams per serving)</p>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={macroData} barGap={4}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(30, 15%, 88%)" />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} stroke="hsl(220, 10%, 45%)" />
              <YAxis tick={{ fontSize: 12 }} stroke="hsl(220, 10%, 45%)" />
              <Tooltip
                contentStyle={{
                  borderRadius: "12px",
                  border: "1px solid hsl(30, 15%, 88%)",
                  fontSize: "13px",
                }}
              />
              <Bar dataKey="original" fill="hsl(16, 78%, 72%)" radius={[4, 4, 0, 0]} name="Original" />
              <Bar dataKey="optimized" fill="hsl(62, 65%, 70%)" radius={[4, 4, 0, 0]} name="Optimized" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Micro Pie Chart */}
        <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
          <h3 className="mb-1 font-display text-lg">Micronutrients</h3>
          <p className="mb-4 text-xs text-muted-foreground">% Daily Value</p>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={microData}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={80}
                paddingAngle={3}
                dataKey="value"
              >
                {microData.map((_, i) => (
                  <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  borderRadius: "12px",
                  border: "1px solid hsl(30, 15%, 88%)",
                  fontSize: "13px",
                }}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="mt-2 flex flex-wrap justify-center gap-x-3 gap-y-1">
            {microData.map((item, i) => (
              <div key={i} className="flex items-center gap-1 text-xs text-muted-foreground">
                <span
                  className="inline-block h-2.5 w-2.5 rounded-full"
                  style={{ background: PIE_COLORS[i] }}
                />
                {item.name}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Warnings & Suggestions */}
      <div className="mt-4 rounded-2xl border border-border bg-card p-5 shadow-sm">
        <h3 className="mb-3 font-display text-lg">Warnings & Suggestions</h3>
        <div className="space-y-2">
          {warnings.map((w, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.5 + i * 0.1 }}
              className={`flex items-start gap-3 rounded-xl p-3 ${
                w.type === "warning"
                  ? "bg-sunrise/10 text-foreground"
                  : w.type === "success"
                  ? "bg-primary/10 text-foreground"
                  : "bg-secondary/50 text-foreground"
              }`}
            >
              {w.type === "warning" && <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-sunrise" />}
              {w.type === "success" && <CheckCircle className="mt-0.5 h-4 w-4 shrink-0 text-primary" />}
              {w.type === "info" && <Info className="mt-0.5 h-4 w-4 shrink-0 text-accent" />}
              <span className="text-sm">{w.text}</span>
            </motion.div>
          ))}
        </div>
      </div>
    </motion.div>
  );
};

export default NutritionChart;
