import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Header from "@/components/Header";
import Landing from "./pages/Landing";
import Dashboard from "./pages/Dashboard";
import Recipes from "./pages/Recipes";
import RecipeAnalysis from "./pages/RecipeAnalysis";
import Profiles from "./pages/Profiles";
import Cravings from "./pages/Cravings";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <Header />
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/profiles" element={<Profiles />} />
          <Route path="/analysis" element={<RecipeAnalysis />} />
          <Route path="/cravings" element={<Cravings />} />
          <Route path="/recipes" element={<Recipes />} />
          <Route path="/dashboard" element={<Dashboard />} />
          {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
