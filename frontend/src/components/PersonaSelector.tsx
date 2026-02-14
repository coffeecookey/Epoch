import { useState } from "react";
import { motion } from "framer-motion";
import { Dumbbell, ShieldAlert, ChevronRight } from "lucide-react";

interface Persona {
  id: string;
  label: string;
  description: string;
  icon: React.ElementType;
  focus: string[];
  color: string;
}

const personas: Persona[] = [
  {
    id: "fitness",
    label: "Fitness Seeker",
    description: "Avoids added sugars; focuses on protein and recovery ingredients.",
    icon: Dumbbell,
    focus: ["Avoiding refined sugar", "Avoiding added sugar", "Avoiding white sugar", "Avoiding high fructose corn syrup"],
    color: "bg-primary/20 text-primary-foreground",
  },
  {
    id: "dietary",
    label: "Dietary-Restricted",
    description: "Common allergen ingredients to avoid; customize as needed.",
    icon: ShieldAlert,
    focus: ["Avoiding gluten", "Avoiding dairy", "Avoiding peanuts", "Avoiding shellfish", "Avoiding eggs"],
    color: "bg-accent/20 text-accent-foreground",
  },
];

const PersonaSelector = () => {
  const [active, setActive] = useState("fitness");

  const activePerson = personas.find((p) => p.id === active)!;

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.4 }}
      className="rounded-2xl border border-border bg-card p-5 shadow-sm"
    >
      <h2 className="mb-1 font-display text-2xl">Your Profile</h2>
      <p className="mb-4 text-sm text-muted-foreground">
        Choose your archetype to personalize analysis
      </p>

      <div className="mb-4 grid grid-cols-2 gap-2">
        {personas.map((p) => {
          const isActive = active === p.id;
          return (
            <button
              key={p.id}
              onClick={() => setActive(p.id)}
              className={`flex flex-col items-center gap-2 rounded-xl border p-4 text-center transition-all ${
                isActive
                  ? "border-accent bg-accent/10 shadow-sm"
                  : "border-border bg-background hover:border-accent/40"
              }`}
            >
              <div
                className={`flex h-10 w-10 items-center justify-center rounded-full ${
                  isActive ? "bg-accent text-card" : "bg-muted text-muted-foreground"
                }`}
              >
                <p.icon className="h-5 w-5" />
              </div>
              <span className="text-xs font-semibold">{p.label}</span>
            </button>
          );
        })}
      </div>

      <motion.div
        key={active}
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-xl bg-background p-4"
      >
        <p className="mb-3 text-sm text-muted-foreground">{activePerson.description}</p>
        <div className="flex flex-wrap gap-2">
          {activePerson.focus.map((f, i) => (
            <span
              key={i}
              className="inline-flex items-center gap-1 rounded-full bg-muted px-3 py-1 text-xs font-medium text-muted-foreground"
            >
              <ChevronRight className="h-3 w-3" />
              {f}
            </span>
          ))}
        </div>
      </motion.div>
    </motion.div>
  );
};

export default PersonaSelector;
