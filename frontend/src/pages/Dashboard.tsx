import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { NavLink } from "@/components/NavLink";
import { TrendingUp, ChefHat, Users, Activity, AlertCircle, Flame } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { useLocation } from "react-router-dom";
import { recipeApi, ApiError } from "@/services/api";
import { getRecipes, subscribeToRecipeStore } from "@/store/recipeStore";
import { getCravingStats, subscribeToCravingStore } from "@/store/cravingStore";
import type { CravingStats } from "@/types/api";

function computeRecipeStats() {
  const recipes = getRecipes();
  const total = recipes.length;
  if (total === 0) {
    return { total_recipes: 0, average_health_score: 0, best_improved_score: 0 };
  }
  const scores = recipes.map((r) => r.health_score).filter((s) => typeof s === "number");
  const avg = scores.length > 0 ? scores.reduce((a, b) => a + b, 0) / scores.length : 0;
  const improvements = recipes
    .filter((r) => r.improved_score != null)
    .map((r) => (r.improved_score ?? 0) - r.health_score);
  const bestImprovement = improvements.length > 0 ? Math.max(...improvements) : 0;
  return {
    total_recipes: total,
    average_health_score: avg,
    best_improved_score: bestImprovement,
  };
}

export default function Dashboard() {
  const [recipeStats, setRecipeStats] = useState(computeRecipeStats);
  const [profileCount, setProfileCount] = useState<number | null>(null);
  const [profilesLoading, setProfilesLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cravingStats, setCravingStats] = useState<CravingStats>(getCravingStats);

  const refreshStats = () => {
    setRecipeStats(computeRecipeStats());
    setProfilesLoading(true);
    recipeApi
      .getProfiles()
      .then((profiles) => setProfileCount(profiles.length))
      .catch(() => setProfileCount(0))
      .finally(() => setProfilesLoading(false));
  };

  const location = useLocation();

  // Refresh recipe stats when navigating to Dashboard
  useEffect(() => {
    if (location.pathname === "/dashboard") {
      setRecipeStats(computeRecipeStats());
    }
  }, [location.pathname, location.key]);

  useEffect(() => {
    const unsubscribe = subscribeToRecipeStore(() => setRecipeStats(computeRecipeStats()));
    return unsubscribe;
  }, []);

  useEffect(() => {
    const unsub = subscribeToCravingStore(() => setCravingStats(getCravingStats()));
    return unsub;
  }, []);

  useEffect(() => {
    let cancelled = false;
    const loadProfiles = async () => {
      try {
        setError(null);
        const profilesPromise = recipeApi.getProfiles();
        const timeoutPromise = new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error("Request timed out")), 8000)
        );
        const profiles = await Promise.race([profilesPromise, timeoutPromise]);
        if (!cancelled) setProfileCount(profiles.length);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Could not load profiles");
          setProfileCount(0);
        }
      } finally {
        if (!cancelled) setProfilesLoading(false);
      }
    };
    loadProfiles();
    return () => {
      cancelled = true;
    };
  }, []);

  // Refresh when returning to this page (e.g. after saving a recipe or creating a profile)
  useEffect(() => {
    const onFocus = () => refreshStats();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, []);

  const displayStats = [
    {
      title: "Recipes Analyzed",
      value: recipeStats.total_recipes.toString(),
      icon: ChefHat,
      trend: "Total recipes saved to My Recipes",
    },
    {
      title: "Avg Health Score",
      value: recipeStats.average_health_score.toFixed(1),
      icon: Activity,
      trend: `Best improvement: +${recipeStats.best_improved_score.toFixed(1)} pts`,
    },
    {
      title: "Active Profiles",
      value: profilesLoading ? "…" : (profileCount ?? 0).toString(),
      icon: Users,
      trend: "User profiles created",
    },
  ];

  return (
    <div className="min-h-screen bg-background">
      <main className="container mx-auto px-4 py-8">
        {/* Hero Section */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <h1 className="font-display text-4xl tracking-tight md:text-5xl mb-3">
            Welcome Back
          </h1>
          <p className="text-muted-foreground text-lg">
            Track your nutrition journey and discover healthier recipe alternatives
          </p>
        </motion.div>

        {/* Error Alert */}
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-6"
          >
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          </motion.div>
        )}

        {/* Stats Grid */}
        <div className="grid gap-6 md:grid-cols-3 mb-8">
          {displayStats.map((stat, index) => (
              <motion.div
                key={stat.title}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
              >
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">
                      {stat.title}
                    </CardTitle>
                    <stat.icon className="h-4 w-4 text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{stat.value}</div>
                    <p className="text-xs text-muted-foreground mt-1">
                      {stat.trend}
                    </p>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
        </div>

        {/* Quick Actions */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <Card className="bg-gradient-to-br from-blue-50 to-purple-50 border-none">
            <CardHeader>
              <CardTitle className="font-display text-2xl">Quick Actions</CardTitle>
              <CardDescription>
                Start analyzing recipes or manage your profiles
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-4">
              <NavLink to="/analysis">
                <Button size="lg" className="gap-2">
                  <TrendingUp className="h-4 w-4" />
                  Analyze New Recipe
                </Button>
              </NavLink>
              <NavLink to="/cravings">
                <Button variant="outline" size="lg" className="gap-2">
                  <Flame className="h-4 w-4" />
                  Log a Craving
                </Button>
              </NavLink>
              <NavLink to="/recipes">
                <Button variant="outline" size="lg" className="gap-2">
                  <ChefHat className="h-4 w-4" />
                  View My Recipes
                </Button>
              </NavLink>
              <NavLink to="/profiles">
                <Button variant="outline" size="lg" className="gap-2">
                  <Users className="h-4 w-4" />
                  Your Profiles
                </Button>
              </NavLink>
            </CardContent>
          </Card>
        </motion.div>

        {/* Craving Insights */}
        {cravingStats.totalLogged > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.35 }}
            className="mt-8"
          >
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <div>
                  <CardTitle className="font-display text-xl">Craving Insights</CardTitle>
                  <CardDescription>Your craving management progress</CardDescription>
                </div>
                <Flame className="h-5 w-5 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div className="text-center">
                    <p className="text-2xl font-bold">{cravingStats.totalLogged}</p>
                    <p className="text-xs text-muted-foreground">Total logged</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold">{cravingStats.replacementsChosen}</p>
                    <p className="text-xs text-muted-foreground">Replaced</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold">{cravingStats.replacementRate}%</p>
                    <p className="text-xs text-muted-foreground">Replace rate</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold capitalize">{cravingStats.topFlavor ?? "-"}</p>
                    <p className="text-xs text-muted-foreground">Top craving</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Recent Activity */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="mt-8"
        >
          <Card>
            <CardHeader>
              <CardTitle className="font-display text-xl">Recent Activity</CardTitle>
              <CardDescription>Your latest recipe analyses and improvements</CardDescription>
            </CardHeader>
            <CardContent>
              {(() => {
                const recentRecipes = getRecipes().slice(0, 5);
                if (recentRecipes.length === 0) {
                  return (
                    <div className="flex items-center justify-center h-40 text-muted-foreground">
                      No recent activity. Start by analyzing a recipe!
                    </div>
                  );
                }
                return (
                  <ul className="space-y-3">
                    {recentRecipes.map((recipe) => (
                      <li
                        key={recipe.id}
                        className="flex items-center justify-between py-2 border-b border-border last:border-0"
                      >
                        <div>
                          <p className="font-medium">{recipe.name}</p>
                          <p className="text-sm text-muted-foreground">
                            {recipe.quantity && recipe.quantity > 0 && `${recipe.quantity} servings · `}
                            Health score: {Math.round(recipe.health_score)} · {recipe.timestamp}
                          </p>
                        </div>
                        <NavLink to="/recipes">
                          <Button variant="ghost" size="sm">
                            View
                          </Button>
                        </NavLink>
                      </li>
                    ))}
                  </ul>
                );
              })()}
            </CardContent>
          </Card>
        </motion.div>
      </main>
    </div>
  );
}
