/**
 * Authentication store using localStorage.
 *
 * Stores user credentials (password is SHA-256 hashed before persisting).
 * When a real backend/DB is added later, swap localStorage calls for API calls.
 */

const USERS_KEY = "nutritwin-users";
const SESSION_KEY = "nutritwin-session";

// ───── Types ──────────────────────────────────────────────────────────────────

export interface StoredUser {
  username: string;       // unique primary key
  name: string;
  age: number;
  passwordHash: string;
  dietaryPresets: string[];       // e.g. ["diabetic", "gluten_free"]
  allergens: string[];            // e.g. ["milk", "peanuts"]
  avoidIngredients: string[];     // e.g. ["refined sugar"]
  createdAt: string;              // ISO timestamp
}

export type SignupPayload = Omit<StoredUser, "passwordHash" | "createdAt"> & {
  password: string;
};

// ───── Helpers ────────────────────────────────────────────────────────────────

async function hashPassword(plain: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(plain);
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(hashBuffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function loadUsers(): StoredUser[] {
  try {
    const raw = localStorage.getItem(USERS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveUsers(users: StoredUser[]): void {
  localStorage.setItem(USERS_KEY, JSON.stringify(users));
}

// ───── Public API ─────────────────────────────────────────────────────────────

export async function signup(payload: SignupPayload): Promise<{ ok: true } | { ok: false; error: string }> {
  const { username, name, age, password, dietaryPresets, allergens, avoidIngredients } = payload;

  if (!username.trim()) return { ok: false, error: "Username is required" };
  if (!name.trim()) return { ok: false, error: "Name is required" };
  if (!password || password.length < 6) return { ok: false, error: "Password must be at least 6 characters" };
  if (age < 1 || age > 150) return { ok: false, error: "Please enter a valid age" };

  const users = loadUsers();
  if (users.some((u) => u.username.toLowerCase() === username.trim().toLowerCase())) {
    return { ok: false, error: "Username already taken" };
  }

  const passwordHash = await hashPassword(password);

  const newUser: StoredUser = {
    username: username.trim(),
    name: name.trim(),
    age,
    passwordHash,
    dietaryPresets,
    allergens,
    avoidIngredients,
    createdAt: new Date().toISOString(),
  };

  users.push(newUser);
  saveUsers(users);

  // Auto-login after signup
  setSession(newUser);

  return { ok: true };
}

export async function login(username: string, password: string): Promise<{ ok: true; user: StoredUser } | { ok: false; error: string }> {
  if (!username.trim() || !password) return { ok: false, error: "Username and password are required" };

  const users = loadUsers();
  const user = users.find((u) => u.username.toLowerCase() === username.trim().toLowerCase());
  if (!user) return { ok: false, error: "Invalid username or password" };

  const hash = await hashPassword(password);
  if (hash !== user.passwordHash) return { ok: false, error: "Invalid username or password" };

  setSession(user);
  return { ok: true, user };
}

export function logout(): void {
  localStorage.removeItem(SESSION_KEY);
}

export function getSession(): StoredUser | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as StoredUser;
  } catch {
    return null;
  }
}

function setSession(user: StoredUser): void {
  // Store session without passwordHash for safety
  const { passwordHash: _, ...safe } = user;
  localStorage.setItem(SESSION_KEY, JSON.stringify({ ...safe, passwordHash: "" }));
}
