"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import {
  ApiError,
  Budget,
  CatalogMeta,
  RecommendationRequest,
  fetchMeta,
  fetchRecommendations,
} from "../lib/api";
import ResultsPanel, { PanelState } from "./ResultsPanel";

const MAX_PREFERENCES = 500;
const BUDGETS: { value: Budget; label: string; hint: string }[] = [
  { value: "low", label: "Low", hint: "up to ₹400" },
  { value: "medium", label: "Medium", hint: "₹401–800" },
  { value: "high", label: "High", hint: "₹801+" },
];

export default function RecommendationApp() {
  const [meta, setMeta] = useState<CatalogMeta | null>(null);
  const [metaError, setMetaError] = useState<string | null>(null);

  const [location, setLocation] = useState("");
  const [budget, setBudget] = useState<Budget>("medium");
  const [cuisineSelect, setCuisineSelect] = useState("");
  const [cuisineText, setCuisineText] = useState("");
  const [minRating, setMinRating] = useState(0);
  const [preferences, setPreferences] = useState("");
  const [locationError, setLocationError] = useState<string | null>(null);

  const [panel, setPanel] = useState<PanelState>({ kind: "idle" });
  const lastRequest = useRef<RecommendationRequest | null>(null);
  const inFlight = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchMeta(controller.signal)
      .then(setMeta)
      .catch((err) => {
        if (controller.signal.aborted) return;
        setMetaError(err instanceof ApiError ? err.message : "Couldn't load locations and cuisines.");
      });
    return () => {
      controller.abort();
      inFlight.current?.abort();
    };
  }, []);

  async function search(payload: RecommendationRequest) {
    inFlight.current?.abort();
    const controller = new AbortController();
    inFlight.current = controller;
    lastRequest.current = payload;
    setPanel({ kind: "loading" });

    try {
      const data = await fetchRecommendations(payload, controller.signal);
      setPanel({ kind: "done", location: payload.location, data });
    } catch (err) {
      if (controller.signal.aborted) return;
      setPanel({
        kind: "error",
        message: err instanceof ApiError ? err.message : "Something went wrong. Please try again.",
      });
    }
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (panel.kind === "loading") return;

    const trimmedLocation = location.trim();
    if (!trimmedLocation) {
      setLocationError("Please choose or type a location.");
      return;
    }
    setLocationError(null);

    void search({
      location: trimmedLocation,
      budget,
      cuisine: cuisineText.trim() || cuisineSelect || undefined,
      min_rating: minRating,
      additional_preferences: preferences.trim(),
    });
  }

  const loading = panel.kind === "loading";

  return (
    <main>
      <h1>Restaurant recommendations</h1>
      <p className="lede">
        Tell us what you feel like and we&apos;ll pick from real Bangalore Zomato listings.
      </p>

      {metaError && (
        <p className="notice notice-error" role="alert">
          {metaError}
        </p>
      )}

      <form onSubmit={onSubmit} noValidate>
        <div className="field">
          <label htmlFor="location">Location</label>
          <input
            id="location"
            list="location-options"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="e.g. Banashankari"
            autoComplete="off"
            aria-invalid={locationError ? true : undefined}
            aria-describedby={locationError ? "location-error" : undefined}
            disabled={loading}
          />
          <datalist id="location-options">
            {meta?.neighborhoods.map((n) => (
              <option key={n} value={n} />
            ))}
          </datalist>
          {locationError && (
            <p id="location-error" className="field-error" role="alert">
              {locationError}
            </p>
          )}
        </div>

        <fieldset className="field" disabled={loading}>
          <legend>Budget (cost for two)</legend>
          <div className="segmented">
            {BUDGETS.map((b) => (
              <label key={b.value} className={budget === b.value ? "segment active" : "segment"}>
                <input
                  type="radio"
                  name="budget"
                  value={b.value}
                  checked={budget === b.value}
                  onChange={() => setBudget(b.value)}
                />
                <span>{b.label}</span>
                <small>{b.hint}</small>
              </label>
            ))}
          </div>
        </fieldset>

        <div className="field two-col">
          <div>
            <label htmlFor="cuisine">Cuisine</label>
            <select
              id="cuisine"
              value={cuisineSelect}
              onChange={(e) => setCuisineSelect(e.target.value)}
              disabled={loading}
            >
              <option value="">Any cuisine</option>
              {meta?.cuisines.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="cuisine-text">Or type a cuisine (optional)</label>
            <input
              id="cuisine-text"
              value={cuisineText}
              onChange={(e) => setCuisineText(e.target.value)}
              placeholder="e.g. Pizza"
              maxLength={100}
              disabled={loading}
            />
          </div>
        </div>

        <div className="field">
          <label htmlFor="min-rating">
            Minimum rating: <strong>{minRating === 0 ? "Any" : minRating.toFixed(1)}</strong>
          </label>
          <input
            id="min-rating"
            type="range"
            min={0}
            max={5}
            step={0.1}
            value={minRating}
            onChange={(e) => setMinRating(Number(e.target.value))}
            disabled={loading}
          />
        </div>

        <div className="field">
          <label htmlFor="preferences">Additional preferences (optional)</label>
          <textarea
            id="preferences"
            rows={3}
            value={preferences}
            onChange={(e) => setPreferences(e.target.value)}
            maxLength={MAX_PREFERENCES}
            placeholder="e.g. family-friendly, quick service, table booking"
            disabled={loading}
          />
          <small className="counter">
            {preferences.length}/{MAX_PREFERENCES}
          </small>
        </div>

        <button type="submit" disabled={loading}>
          {loading ? "Finding restaurants…" : "Get recommendations"}
        </button>
      </form>

      <ResultsPanel
        state={panel}
        onRetry={() => lastRequest.current && void search(lastRequest.current)}
      />
    </main>
  );
}
