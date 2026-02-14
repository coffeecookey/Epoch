import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  AlertCircle,
  Clock,
  Flame,
  Lightbulb,
  Search,
  TrendingUp,
  Check,
  Loader2,
} from "lucide-react";
import { recipeApi, ApiError } from "@/services/api";
import {
  logCraving,
  markReplacementChosen,
  getCravingHistory,
  getCravingStats,
  subscribeToCravingStore,
} from "@/store/cravingStore";
import { getSession } from "@/store/authStore";
import type {
  FlavorType,
  MoodType,
  TimeOfDay,
  CravingReplacement,
  CravingHistoryEntry,
  CravingPatternAnalysis,
  CravingStats,
} from "@/types/api";
import {
  FLAVOR_OPTIONS,
  MOOD_OPTIONS,
  TIME_OPTIONS,
} from "@/types/api";

// --------------- helpers ---------------

function detectTimeOfDay(): TimeOfDay {
  const h = new Date().getHours();
  if (h < 12) return "morning";
  if (h < 17) return "afternoon";
  if (h < 21) return "evening";
  return "late-night";
}

// --------------- page ---------------

export default function Cravings() {
  // form state
  const [cravingText, setCravingText] = useState("");
  const [flavor, setFlavor] = useState<FlavorType | null>(null);
  const [mood, setMood] = useState<MoodType | null>(null);
  const [time, setTime] = useState<TimeOfDay>(detectTimeOfDay());
  const [context, setContext] = useState("");

  // results
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CravingReplacement | null>(null);
  const [activeCravingId, setActiveCravingId] = useState<string | null>(null);
  const [chosenMap, setChosenMap] = useState<Record<string, string>>({});

  // history / patterns
  const [stats, setStats] = useState<CravingStats>(getCravingStats);
  const [history, setHistory] = useState<CravingHistoryEntry[]>([]);
  const [patterns, setPatterns] = useState<CravingPatternAnalysis | null>(null);
  const [patternsLoading, setPatternsLoading] = useState(false);

  // keep stats in sync
  useEffect(() => {
    const unsub = subscribeToCravingStore(() => {
      setStats(getCravingStats());
      setHistory(getCravingHistory());
    });
    setHistory(getCravingHistory());
    return unsub;
  }, []);

  // load patterns on mount if there is history
  useEffect(() => {
    const h = getCravingHistory();
    if (h.length >= 2) loadPatterns(h);
  }, []);

  async function loadPatterns(h: CravingHistoryEntry[]) {
    try {
      setPatternsLoading(true);
      const res = await recipeApi.analyzeCravingPatterns(h);
      setPatterns(res);
    } catch {
      // silent — patterns are optional
    } finally {
      setPatternsLoading(false);
    }
  }

  const canSubmit = cravingText.trim().length > 0 && flavor !== null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setError(null);
    setLoading(true);
    setResult(null);

    const session = getSession();

    try {
      const entry = logCraving({
        craving_text: cravingText,
        flavor_type: flavor!,
        mood: mood ?? undefined,
        time_of_day: time,
        context: context || undefined,
      });
      setActiveCravingId(entry.id);

      const res = await recipeApi.getCravingReplacement({
        craving_text: cravingText,
        flavor_type: flavor!,
        mood: mood ?? undefined,
        time_of_day: time,
        context: context || undefined,
        user_allergens: session?.allergens,
        user_avoid_ingredients: session?.avoidIngredients,
      });
      setResult(res);
      // refresh patterns
      loadPatterns(getCravingHistory());
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Failed to fetch replacements. Is the backend running?"
      );
    } finally {
      setLoading(false);
    }
  }

  function handleChoose(name: string) {
    if (!activeCravingId) return;
    markReplacementChosen(activeCravingId, name);
    setChosenMap((prev) => ({ ...prev, [activeCravingId!]: name }));
  }

  // ---- render ----

  return (
    <div className="min-h-screen bg-background">
      <main className="container mx-auto max-w-4xl px-4 py-8">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <h1 className="font-display text-4xl tracking-tight md:text-5xl mb-2">
            Cravings
          </h1>
          <p className="text-muted-foreground text-lg">
            Log what you're craving and get personalised healthier alternatives
          </p>
        </motion.div>

        {/* Stats strip */}
        {stats.totalLogged > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8"
          >
            <Card>
              <CardContent className="pt-4 pb-3 text-center">
                <p className="text-2xl font-bold">{stats.totalLogged}</p>
                <p className="text-xs text-muted-foreground">Logged</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4 pb-3 text-center">
                <p className="text-2xl font-bold">{stats.replacementsChosen}</p>
                <p className="text-xs text-muted-foreground">Replaced</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4 pb-3 text-center">
                <p className="text-2xl font-bold">{stats.replacementRate}%</p>
                <p className="text-xs text-muted-foreground">Replace Rate</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4 pb-3 text-center">
                <p className="text-2xl font-bold capitalize">
                  {stats.topFlavor ?? "-"}
                </p>
                <p className="text-xs text-muted-foreground">Top Craving</p>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* ================ FORM ================ */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
        >
          <Card className="mb-8">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <Search className="h-4 w-4" />
                What are you craving?
              </CardTitle>
              <CardDescription>
                Describe your craving and we'll find healthier alternatives
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-5">
                {/* Text */}
                <div>
                  <Label htmlFor="craving-text">Craving</Label>
                  <Input
                    id="craving-text"
                    placeholder='e.g. "chocolate", "something crunchy and salty"'
                    value={cravingText}
                    onChange={(e) => setCravingText(e.target.value)}
                    className="mt-1"
                  />
                </div>

                {/* Flavor */}
                <div>
                  <Label>Flavor type</Label>
                  <div className="flex flex-wrap gap-2 mt-1">
                    {FLAVOR_OPTIONS.map((f) => (
                      <Button
                        key={f.value}
                        type="button"
                        size="sm"
                        variant={flavor === f.value ? "default" : "outline"}
                        onClick={() =>
                          setFlavor(flavor === f.value ? null : f.value)
                        }
                      >
                        {f.label}
                      </Button>
                    ))}
                  </div>
                </div>

                {/* Mood (optional) */}
                <div>
                  <Label>
                    Mood{" "}
                    <span className="text-muted-foreground font-normal">
                      (optional)
                    </span>
                  </Label>
                  <div className="flex flex-wrap gap-2 mt-1">
                    {MOOD_OPTIONS.map((m) => (
                      <Button
                        key={m.value}
                        type="button"
                        size="sm"
                        variant={mood === m.value ? "default" : "outline"}
                        onClick={() =>
                          setMood(mood === m.value ? null : m.value)
                        }
                      >
                        {m.label}
                      </Button>
                    ))}
                  </div>
                </div>

                {/* Time of day */}
                <div>
                  <Label>Time of day</Label>
                  <div className="flex flex-wrap gap-2 mt-1">
                    {TIME_OPTIONS.map((t) => (
                      <Button
                        key={t.value}
                        type="button"
                        size="sm"
                        variant={time === t.value ? "default" : "outline"}
                        onClick={() => setTime(t.value)}
                      >
                        {t.label}
                      </Button>
                    ))}
                  </div>
                </div>

                {/* Context (optional) */}
                <div>
                  <Label htmlFor="context">
                    Context{" "}
                    <span className="text-muted-foreground font-normal">
                      (optional)
                    </span>
                  </Label>
                  <Input
                    id="context"
                    placeholder='e.g. "after studying for hours"'
                    value={context}
                    onChange={(e) => setContext(e.target.value)}
                    className="mt-1"
                  />
                </div>

                <Button
                  type="submit"
                  className="w-full gap-2"
                  disabled={!canSubmit || loading}
                >
                  {loading ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Finding replacements...
                    </>
                  ) : (
                    <>
                      <Flame className="h-4 w-4" />
                      Find My Replacement
                    </>
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>
        </motion.div>

        {/* Error */}
        {error && (
          <Alert variant="destructive" className="mb-6">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* ================ RESULTS ================ */}
        {result && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-6 mb-8"
          >
            {/* Psychological insight */}
            <Alert>
              <Lightbulb className="h-4 w-4" />
              <AlertDescription>
                {result.psychological_insight}
              </AlertDescription>
            </Alert>

            {/* Quick combos */}
            {result.quick_combos.length > 0 && (
              <div>
                <h2 className="font-display text-lg mb-3">Quick Combos</h2>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {result.quick_combos.map((combo, i) => {
                    const isChosen =
                      activeCravingId &&
                      chosenMap[activeCravingId] === combo.name;
                    return (
                      <Card key={i}>
                        <CardHeader className="pb-2">
                          <CardTitle className="text-base">
                            {combo.name}
                          </CardTitle>
                          <CardDescription className="flex items-center gap-2 text-xs">
                            <Clock className="h-3 w-3" />
                            {combo.prep_time_minutes} min
                            {combo.calories_estimate && (
                              <>
                                {" "}
                                &middot; ~{combo.calories_estimate} cal
                              </>
                            )}
                          </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-2">
                          <div className="flex flex-wrap gap-1">
                            {combo.ingredients.map((ing) => (
                              <Badge key={ing} variant="secondary">
                                {ing}
                              </Badge>
                            ))}
                          </div>
                          <p className="text-xs text-muted-foreground">
                            {combo.why_it_works}
                          </p>
                          <Button
                            size="sm"
                            variant={isChosen ? "default" : "outline"}
                            className="w-full gap-1"
                            onClick={() => handleChoose(combo.name)}
                            disabled={!!isChosen}
                          >
                            {isChosen ? (
                              <>
                                <Check className="h-3 w-3" /> Chosen
                              </>
                            ) : (
                              "I'll try this"
                            )}
                          </Button>
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Full recipes */}
            {result.full_recipes.length > 0 && (
              <div>
                <h2 className="font-display text-lg mb-3">
                  Recipe Suggestions
                </h2>
                <div className="space-y-3">
                  {result.full_recipes.map((r, i) => {
                    const isChosen =
                      activeCravingId &&
                      chosenMap[activeCravingId] === r.name;
                    return (
                      <Card key={i}>
                        <CardContent className="flex items-center justify-between py-4">
                          <div className="space-y-1 min-w-0 flex-1">
                            <p className="font-medium truncate">{r.name}</p>
                            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                              {r.cuisine && (
                                <span>{r.cuisine}</span>
                              )}
                              {r.prep_time != null && (
                                <span className="flex items-center gap-1">
                                  <Clock className="h-3 w-3" />
                                  {r.prep_time} min
                                </span>
                              )}
                              {r.health_score != null && (
                                <Badge
                                  variant={
                                    r.health_score >= 60
                                      ? "default"
                                      : "secondary"
                                  }
                                  className="text-[10px] px-1.5"
                                >
                                  Score {Math.round(r.health_score)}
                                </Badge>
                              )}
                            </div>
                          </div>
                          <Button
                            size="sm"
                            variant={isChosen ? "default" : "outline"}
                            className="ml-3 shrink-0 gap-1"
                            onClick={() => handleChoose(r.name)}
                            disabled={!!isChosen}
                          >
                            {isChosen ? (
                              <>
                                <Check className="h-3 w-3" /> Chosen
                              </>
                            ) : (
                              "I'll try this"
                            )}
                          </Button>
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Science explanation */}
            <Accordion type="single" collapsible>
              <AccordionItem value="science">
                <AccordionTrigger className="text-sm">
                  Why these replacements work
                </AccordionTrigger>
                <AccordionContent className="text-sm text-muted-foreground">
                  {result.science_explanation}
                </AccordionContent>
              </AccordionItem>
            </Accordion>

            {/* Encouragement */}
            {result.encouragement && (
              <p className="text-sm text-muted-foreground italic">
                {result.encouragement}
              </p>
            )}
          </motion.div>
        )}

        {/* ================ PATTERNS ================ */}
        {patterns && patterns.patterns.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-8"
          >
            <h2 className="font-display text-xl mb-3 flex items-center gap-2">
              <TrendingUp className="h-5 w-5" />
              Your Patterns
            </h2>
            <div className="grid gap-4 sm:grid-cols-2">
              {patterns.patterns.map((p, i) => (
                <Card key={i}>
                  <CardContent className="py-4">
                    <p className="text-sm">{p.pattern_description}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
            {patterns.encouragement_messages.length > 0 && (
              <div className="mt-4 space-y-2">
                {patterns.encouragement_messages.map((msg, i) => (
                  <Alert key={i}>
                    <AlertDescription className="text-sm">
                      {msg}
                    </AlertDescription>
                  </Alert>
                ))}
              </div>
            )}
          </motion.div>
        )}

        {patternsLoading && (
          <p className="text-sm text-muted-foreground mb-6">
            Analysing your craving patterns...
          </p>
        )}

        {/* ================ HISTORY ================ */}
        {history.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Recent Cravings</CardTitle>
                <CardDescription>Your logged craving history</CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {history.slice(0, 10).map((entry) => (
                    <li
                      key={entry.id}
                      className="flex items-center justify-between border-b border-border py-2 last:border-0 text-sm"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="font-medium truncate">
                          {entry.craving_text}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {entry.flavor_type}
                          {entry.mood ? ` / ${entry.mood}` : ""} &middot;{" "}
                          {entry.time_of_day.replace("-", " ")} &middot;{" "}
                          {entry.timestamp}
                        </p>
                      </div>
                      {entry.replacement_chosen && (
                        <Badge variant="outline" className="ml-2 shrink-0 text-xs">
                          {entry.replacement_chosen}
                        </Badge>
                      )}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </main>
    </div>
  );
}
