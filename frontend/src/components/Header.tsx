import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Beaker, User, Menu, X, LogIn, UserPlus, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { NavLink } from "@/components/NavLink";
import AuthModal from "@/components/AuthModal";
import { getSession, logout, type StoredUser } from "@/store/authStore";

const navItems = [
  { label: "Home", path: "/" },
  { label: "Profiles", path: "/profiles" },
  { label: "Analysis", path: "/analysis" },
  { label: "Cravings", path: "/cravings" },
  { label: "Recipes", path: "/recipes" },
  { label: "Dashboard", path: "/dashboard" },
];

const Header = () => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [authOpen, setAuthOpen] = useState(false);
  const [authView, setAuthView] = useState<"login" | "signup">("login");
  const [user, setUser] = useState<StoredUser | null>(null);
  const [dropdownOpen, setDropdownOpen] = useState(false);

  // Restore session on mount
  useEffect(() => {
    setUser(getSession());
  }, []);

  const openLogin = () => { setAuthView("login"); setAuthOpen(true); setDropdownOpen(false); };
  const openSignup = () => { setAuthView("signup"); setAuthOpen(true); setDropdownOpen(false); };
  const handleAuth = (u: StoredUser) => setUser(u);
  const handleLogout = () => { logout(); setUser(null); setDropdownOpen(false); };

  return (
    <>
    <motion.header
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className="sticky top-0 z-50 border-b border-border bg-card/80 backdrop-blur-md"
    >
      <div className="container mx-auto flex h-16 items-center justify-between px-4">
        <NavLink to="/" className="flex items-center gap-2 no-underline">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary">
            <Beaker className="h-5 w-5 text-primary-foreground" />
          </div>
          <span className="font-display text-xl tracking-tight text-foreground">NutriTwin</span>
        </NavLink>

        {/* Desktop nav */}
        <nav className="hidden items-center gap-1 md:flex">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className="rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              activeClassName="bg-muted text-foreground"
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="hidden items-center gap-3 md:flex">
          <div
            className="relative"
            onMouseEnter={() => setDropdownOpen(true)}
            onMouseLeave={() => setDropdownOpen(false)}
          >
            {user ? (
              /* Logged-in avatar */
              <Button variant="ghost" size="icon" className="rounded-full">
                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
                  {user.name.charAt(0).toUpperCase()}
                </div>
              </Button>
            ) : (
              /* Guest icon */
              <Button variant="ghost" size="icon" className="rounded-full">
                <User className="h-4 w-4" />
              </Button>
            )}

            {/* Hover dropdown */}
            {dropdownOpen && (
              <motion.div
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                className="absolute right-0 top-full mt-1 min-w-[160px] rounded-lg border border-border bg-card p-1 shadow-lg"
              >
                {user ? (
                  <>
                    <div className="px-3 py-2 border-b border-border mb-1">
                      <p className="text-sm font-medium text-foreground">{user.name}</p>
                      <p className="text-xs text-muted-foreground">@{user.username}</p>
                    </div>
                    <button
                      onClick={handleLogout}
                      className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                    >
                      <LogOut className="h-3.5 w-3.5" />
                      Log out
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      onClick={openLogin}
                      className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                    >
                      <LogIn className="h-3.5 w-3.5" />
                      Log in
                    </button>
                    <button
                      onClick={openSignup}
                      className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                    >
                      <UserPlus className="h-3.5 w-3.5" />
                      Sign up
                    </button>
                  </>
                )}
              </motion.div>
            )}
          </div>
        </div>

        {/* Mobile toggle */}
        <button
          className="md:hidden"
          onClick={() => setMobileOpen(!mobileOpen)}
        >
          {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          className="border-t border-border bg-card px-4 pb-4 md:hidden"
        >
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className="block w-full rounded-md px-3 py-2 text-left text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              activeClassName="bg-muted text-foreground"
              onClick={() => setMobileOpen(false)}
            >
              {item.label}
            </NavLink>
          ))}
          {/* Mobile auth buttons */}
          <div className="mt-2 border-t border-border pt-2 flex gap-2">
            {user ? (
              <Button variant="ghost" size="sm" className="w-full justify-start gap-2" onClick={handleLogout}>
                <LogOut className="h-3.5 w-3.5" /> Log out ({user.name})
              </Button>
            ) : (
              <>
                <Button variant="ghost" size="sm" className="flex-1 gap-1" onClick={openLogin}>
                  <LogIn className="h-3.5 w-3.5" /> Log in
                </Button>
                <Button variant="ghost" size="sm" className="flex-1 gap-1" onClick={openSignup}>
                  <UserPlus className="h-3.5 w-3.5" /> Sign up
                </Button>
              </>
            )}
          </div>
        </motion.div>
      )}
    </motion.header>

      {/* Auth modal — rendered outside header to avoid stacking context issues */}
      <AuthModal
        open={authOpen}
        defaultView={authView}
        onClose={() => setAuthOpen(false)}
        onAuth={handleAuth}
      />
    </>
  );
};

export default Header;
