import { useCallback, useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Eye, EyeOff } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import {
  signup,
  login,
  type SignupPayload,
  type StoredUser,
} from "@/store/authStore";
import { ALLERGEN_OPTIONS, DIETARY_PRESETS } from "@/types/api";

type AuthView = "login" | "signup";

interface AuthModalProps {
  open: boolean;
  defaultView?: AuthView;
  onClose: () => void;
  onAuth: (user: StoredUser) => void;
}

export default function AuthModal({
  open,
  defaultView = "login",
  onClose,
  onAuth,
}: AuthModalProps) {
  const [view, setView] = useState<AuthView>(defaultView);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // ── Login state ─────────────────────────────────
  const [loginUsername, setLoginUsername] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [showLoginPw, setShowLoginPw] = useState(false);

  // ── Signup state ────────────────────────────────
  const [name, setName] = useState("");
  const [age, setAge] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showSignupPw, setShowSignupPw] = useState(false);
  const [selectedPresets, setSelectedPresets] = useState<string[]>([]);
  const [selectedAllergens, setSelectedAllergens] = useState<string[]>([]);
  const [avoidInput, setAvoidInput] = useState("");
  const [avoidList, setAvoidList] = useState<string[]>([]);

  // Sync defaultView prop
  useEffect(() => {
    setView(defaultView);
  }, [defaultView]);

  // Reset on open/close
  useEffect(() => {
    if (!open) {
      setError("");
      setLoading(false);
    }
  }, [open]);

  // ── Derived allergens from dietary presets ───────
  const derivedAllergens = useMemo(() => {
    const set = new Set<string>(selectedAllergens);
    for (const id of selectedPresets) {
      const preset = DIETARY_PRESETS.find((p) => p.id === id);
      if (preset) preset.allergens.forEach((a) => set.add(a));
    }
    return Array.from(set);
  }, [selectedAllergens, selectedPresets]);

  const derivedAvoid = useMemo(() => {
    const set = new Set<string>(avoidList);
    for (const id of selectedPresets) {
      const preset = DIETARY_PRESETS.find((p) => p.id === id);
      if (preset) preset.avoid_ingredients.forEach((a) => set.add(a));
    }
    return Array.from(set);
  }, [avoidList, selectedPresets]);

  // ── Handlers ────────────────────────────────────

  const togglePreset = (id: string) =>
    setSelectedPresets((prev) =>
      prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]
    );

  const toggleAllergen = (val: string) =>
    setSelectedAllergens((prev) =>
      prev.includes(val) ? prev.filter((a) => a !== val) : [...prev, val]
    );

  const addAvoidItem = () => {
    const trimmed = avoidInput.trim().toLowerCase();
    if (trimmed && !avoidList.includes(trimmed)) {
      setAvoidList((prev) => [...prev, trimmed]);
    }
    setAvoidInput("");
  };

  const handleLogin = useCallback(async () => {
    setError("");
    setLoading(true);
    const result = await login(loginUsername, loginPassword);
    setLoading(false);
    if (result.ok === true) {
      onAuth(result.user);
      onClose();
    } else {
      setError(result.error);
    }
  }, [loginUsername, loginPassword, onAuth, onClose]);

  const handleSignup = useCallback(async () => {
    setError("");
    setLoading(true);

    const payload: SignupPayload = {
      username,
      name,
      age: Number(age) || 0,
      password,
      dietaryPresets: selectedPresets,
      allergens: derivedAllergens,
      avoidIngredients: derivedAvoid,
    };

    const result = await signup(payload);
    setLoading(false);
    if (result.ok === true) {
      // Reconstruct user for callback
      onAuth({
        username: payload.username,
        name: payload.name,
        age: payload.age,
        passwordHash: "",
        dietaryPresets: payload.dietaryPresets,
        allergens: payload.allergens,
        avoidIngredients: payload.avoidIngredients,
        createdAt: new Date().toISOString(),
      });
      onClose();
    } else {
      setError(result.error);
    }
  }, [username, name, age, password, selectedPresets, derivedAllergens, derivedAvoid, onAuth, onClose]);

  if (!open) return null;

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            key="auth-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] bg-black/40 backdrop-blur-md"
            onClick={onClose}
          />
          {/* Centered modal */}
          <div
            className="fixed left-1/2 top-[55%] z-[101] w-full max-w-md -translate-x-1/2 -translate-y-1/2 px-4"
          >
            <motion.div
              key="auth-modal"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ type: "spring", duration: 0.35 }}
              className="relative rounded-xl border border-border bg-card p-6 shadow-xl max-h-[85vh] overflow-y-auto"
            >
            {/* Close button */}
            <button
              onClick={onClose}
              className="absolute right-4 top-4 rounded-sm p-1 text-muted-foreground transition-colors hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>

            {/* Tab switcher */}
            <div className="mb-6 flex gap-1 rounded-lg bg-muted p-1">
              <button
                onClick={() => { setView("login"); setError(""); }}
                className={`flex-1 rounded-md py-2 text-sm font-medium transition-colors ${
                  view === "login"
                    ? "bg-card text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                Log in
              </button>
              <button
                onClick={() => { setView("signup"); setError(""); }}
                className={`flex-1 rounded-md py-2 text-sm font-medium transition-colors ${
                  view === "signup"
                    ? "bg-card text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                Sign up
              </button>
            </div>

            {/* Error banner */}
            {error && (
              <div className="mb-4 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {error}
              </div>
            )}

            {/* ── LOGIN VIEW ──────────────────────────── */}
            {view === "login" && (
              <div className="space-y-4">
                <div>
                  <Label htmlFor="login-user" className="text-sm font-medium">Username</Label>
                  <Input
                    id="login-user"
                    placeholder="Enter your username"
                    value={loginUsername}
                    onChange={(e) => setLoginUsername(e.target.value)}
                    className="mt-1.5"
                    autoFocus
                  />
                </div>

                <div>
                  <Label htmlFor="login-pw" className="text-sm font-medium">Password</Label>
                  <div className="relative mt-1.5">
                    <Input
                      id="login-pw"
                      type={showLoginPw ? "text" : "password"}
                      placeholder="Enter your password"
                      value={loginPassword}
                      onChange={(e) => setLoginPassword(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && handleLogin()}
                    />
                    <button
                      type="button"
                      onClick={() => setShowLoginPw((v) => !v)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    >
                      {showLoginPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                </div>

                <Button
                  className="w-full"
                  disabled={loading}
                  onClick={handleLogin}
                >
                  {loading ? "Logging in…" : "Log in"}
                </Button>

                <p className="text-center text-xs text-muted-foreground">
                  Don't have an account?{" "}
                  <button
                    onClick={() => { setView("signup"); setError(""); }}
                    className="font-medium text-accent-foreground underline underline-offset-2 hover:text-foreground"
                  >
                    Sign up
                  </button>
                </p>
              </div>
            )}

            {/* ── SIGNUP VIEW ─────────────────────────── */}
            {view === "signup" && (
              <div className="space-y-4">
                {/* Basic info */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="col-span-2">
                    <Label htmlFor="signup-name" className="text-sm font-medium">Full name</Label>
                    <Input
                      id="signup-name"
                      placeholder="Jane Doe"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      className="mt-1.5"
                      autoFocus
                    />
                  </div>

                  <div>
                    <Label htmlFor="signup-age" className="text-sm font-medium">Age</Label>
                    <Input
                      id="signup-age"
                      type="number"
                      min={1}
                      max={150}
                      placeholder="25"
                      value={age}
                      onChange={(e) => setAge(e.target.value)}
                      className="mt-1.5"
                    />
                  </div>

                  <div>
                    <Label htmlFor="signup-user" className="text-sm font-medium">Username</Label>
                    <Input
                      id="signup-user"
                      placeholder="janedoe"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      className="mt-1.5"
                    />
                  </div>
                </div>

                <div>
                  <Label htmlFor="signup-pw" className="text-sm font-medium">Password</Label>
                  <div className="relative mt-1.5">
                    <Input
                      id="signup-pw"
                      type={showSignupPw ? "text" : "password"}
                      placeholder="Min. 6 characters"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                    />
                    <button
                      type="button"
                      onClick={() => setShowSignupPw((v) => !v)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    >
                      {showSignupPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                </div>

                {/* Dietary presets */}
                <div>
                  <Label className="text-sm font-medium">Dietary preferences</Label>
                  <p className="mb-2 text-xs text-muted-foreground">Select any that apply</p>
                  <div className="flex flex-wrap gap-2">
                    {DIETARY_PRESETS.map((preset) => (
                      <Badge
                        key={preset.id}
                        variant={selectedPresets.includes(preset.id) ? "default" : "outline"}
                        className="cursor-pointer select-none transition-colors"
                        onClick={() => togglePreset(preset.id)}
                      >
                        {preset.label}
                      </Badge>
                    ))}
                  </div>
                </div>

                {/* Allergens */}
                <div>
                  <Label className="text-sm font-medium">Allergens</Label>
                  <p className="mb-2 text-xs text-muted-foreground">We'll filter these from suggestions</p>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-2">
                    {ALLERGEN_OPTIONS.map((opt) => (
                      <label
                        key={opt.value}
                        className="flex cursor-pointer items-center gap-2 text-sm"
                      >
                        <Checkbox
                          checked={derivedAllergens.includes(opt.value)}
                          onCheckedChange={() => toggleAllergen(opt.value)}
                        />
                        {opt.label}
                      </label>
                    ))}
                  </div>
                </div>

                {/* Avoid ingredients */}
                <div>
                  <Label className="text-sm font-medium">Ingredients to avoid</Label>
                  <div className="mt-1.5 flex gap-2">
                    <Input
                      placeholder="e.g. refined sugar"
                      value={avoidInput}
                      onChange={(e) => setAvoidInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          addAvoidItem();
                        }
                      }}
                      className="flex-1"
                    />
                    <Button variant="outline" size="sm" onClick={addAvoidItem} className="shrink-0">
                      Add
                    </Button>
                  </div>
                  {avoidList.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {avoidList.map((item) => (
                        <Badge key={item} variant="secondary" className="gap-1 pr-1">
                          {item}
                          <button
                            onClick={() => setAvoidList((prev) => prev.filter((i) => i !== item))}
                            className="ml-0.5 rounded-full p-0.5 hover:bg-muted"
                          >
                            <X className="h-3 w-3" />
                          </button>
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>

                <Button
                  className="w-full"
                  disabled={loading}
                  onClick={handleSignup}
                >
                  {loading ? "Creating account…" : "Create account"}
                </Button>

                <p className="text-center text-xs text-muted-foreground">
                  Already have an account?{" "}
                  <button
                    onClick={() => { setView("login"); setError(""); }}
                    className="font-medium text-accent-foreground underline underline-offset-2 hover:text-foreground"
                  >
                    Log in
                  </button>
                </p>
              </div>
            )}
          </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
}
