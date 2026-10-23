export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export type Budget = "low" | "medium" | "high";

export interface RecommendationRequest {
  location: string;
  budget: Budget;
  cuisine?: string;
  min_rating: number;
  additional_preferences: string;
}

export interface Recommendation {
  rank: number;
  restaurant_id: string;
  name: string;
  cuisine: string | null;
  rating: number | null;
  estimated_cost: number | null;
  explanation: string | null;
  neighborhood: string | null;
  rest_type: string | null;
}

export type FallbackReason = "no_api_key" | "rate_limited" | "llm_error" | "invalid_output";

export interface RecommendationResponse {
  summary: string | null;
  recommendations: Recommendation[];
  meta: {
    candidates_considered: number;
    used_llm: boolean;
    fallback: boolean;
    budget_relaxed: boolean;
    fallback_reason?: FallbackReason | null;
    retry_after_seconds?: number | null;
    cached?: boolean;
  };
}

export interface CatalogMeta {
  neighborhoods: string[];
  cuisines: string[];
}

export class ApiError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new ApiError("Couldn't reach the recommendation service. Check that the API is running.");
  }
  if (!response.ok) {
    let detail = "";
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // non-JSON error body
    }
    if (response.status === 422) {
      throw new ApiError("Some of the preferences were not valid. Please check the form and try again.");
    }
    throw new ApiError(detail || `The service returned an error (${response.status}). Please try again.`);
  }
  return (await response.json()) as T;
}

export function fetchMeta(signal?: AbortSignal): Promise<CatalogMeta> {
  return request<CatalogMeta>("/meta", { signal });
}

export function fetchRecommendations(
  body: RecommendationRequest,
  signal?: AbortSignal,
): Promise<RecommendationResponse> {
  return request<RecommendationResponse>("/recommendations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
}
