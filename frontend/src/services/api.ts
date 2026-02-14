import type {
  AnalyzeRequest,
  FullAnalysisResponse,
  RecalculateRequest,
  RecalculateResponse,
  Recipe,
  DashboardStats,
  UserProfile,
  CravingRequest,
  CravingReplacement,
  CravingHistoryEntry,
  CravingPatternAnalysis,
} from "@/types/api";

const API_BASE_URL = "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function fetchWithError<T>(
  url: string,
  options?: RequestInit
): Promise<T> {
  try {
    const response = await fetch(url, options);

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new ApiError(
        response.status,
        errorData.message || `Request failed with status ${response.status}`
      );
    }

    return await response.json();
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError(0, error instanceof Error ? error.message : "Network error occurred");
  }
}

export const recipeApi = {
  async analyzeFull(request: AnalyzeRequest): Promise<FullAnalysisResponse> {
    return fetchWithError<FullAnalysisResponse>(`${API_BASE_URL}/analyze-full`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    });
  },

  async recalculate(request: RecalculateRequest): Promise<RecalculateResponse> {
    return fetchWithError<RecalculateResponse>(`${API_BASE_URL}/recalculate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    });
  },

  async healthCheck(): Promise<{ status: string }> {
    return fetchWithError<{ status: string }>(`${API_BASE_URL}/health`);
  },

  async saveRecipe(recipeData: FullAnalysisResponse): Promise<Recipe> {
    return fetchWithError<Recipe>(`${API_BASE_URL}/recipes`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(recipeData),
    });
  },

  async getRecipes(): Promise<Recipe[]> {
    return fetchWithError<Recipe[]>(`${API_BASE_URL}/recipes`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });
  },

  async getDashboardStats(): Promise<DashboardStats> {
    return fetchWithError<DashboardStats>(`${API_BASE_URL}/dashboard/stats`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });
  },

  async createProfile(profileData: Omit<UserProfile, "id" | "created_at">): Promise<UserProfile> {
    return fetchWithError<UserProfile>(`${API_BASE_URL}/profiles`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(profileData),
    });
  },

  async getProfiles(): Promise<UserProfile[]> {
    return fetchWithError<UserProfile[]>(`${API_BASE_URL}/profiles`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });
  },

  async getProfile(profileId: string): Promise<UserProfile> {
    return fetchWithError<UserProfile>(`${API_BASE_URL}/profiles/${profileId}`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });
  },

  async updateProfile(
    profileId: string,
    profileData: Partial<Omit<UserProfile, "id" | "created_at">>
  ): Promise<UserProfile> {
    return fetchWithError<UserProfile>(`${API_BASE_URL}/profiles/${profileId}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(profileData),
    });
  },

  async deleteProfile(profileId: string): Promise<{ message: string; id: string }> {
    return fetchWithError<{ message: string; id: string }>(
      `${API_BASE_URL}/profiles/${profileId}`,
      {
        method: "DELETE",
      }
    );
  },

  // ===================== Craving Replacement =====================

  async getCravingReplacement(request: CravingRequest): Promise<CravingReplacement> {
    return fetchWithError<CravingReplacement>(`${API_BASE_URL}/cravings/replace`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
  },

  async analyzeCravingPatterns(
    history: CravingHistoryEntry[]
  ): Promise<CravingPatternAnalysis> {
    return fetchWithError<CravingPatternAnalysis>(`${API_BASE_URL}/cravings/patterns`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(history),
    });
  },
};
