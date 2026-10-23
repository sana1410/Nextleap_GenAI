"use client";

import { FormEvent } from "react";
import Icon from "./Icon";
import LocationField from "./LocationField";
import { Budget, CatalogMeta } from "../lib/api";

export const MAX_PREFERENCES = 500;

export const BUDGETS: { value: Budget; label: string; hint: string }[] = [
  { value: "low", label: "Low", hint: "Up to ₹400" },
  { value: "medium", label: "Medium", hint: "₹401–800" },
  { value: "high", label: "High", hint: "₹801+" },
];

export interface FormState {
  location: string;
  budget: Budget;
  cuisineSelect: string;
  cuisineText: string;
  minRating: number;
  preferences: string;
}

export default function PreferenceForm({
  meta,
  metaError,
  state,
  setState,
  locationError,
  loading,
  onSubmit,
}: {
  meta: CatalogMeta | null;
  metaError: string | null;
  state: FormState;
  setState: (updater: (prev: FormState) => FormState) => void;
  locationError: string | null;
  loading: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  const ratingLabel = state.minRating === 0 ? "Any" : `${state.minRating.toFixed(1)} / 5.0`;
  const counterNearLimit = state.preferences.length > MAX_PREFERENCES - 40;

  return (
    <div className="hero-wrap">
      <div className="hero">
        <div className="hero-glow" aria-hidden="true" />
        <div className="eyebrow">
          <span className="eyebrow-dot" />
          <span className="text-label-caps accent">AI Dining Explorer &bull; Bangalore</span>
        </div>
        <h1 className="text-headline-lg">Restaurant recommendations</h1>
        <p>
          Tell us your location, budget and craving &mdash; the AI ranks real Bangalore restaurants and explains
          why each one fits.
        </p>
      </div>

      {metaError && (
        <p className="hint-banner is-error text-body-sm" role="alert" style={{ marginBottom: "1rem" }}>
          <Icon name="info" size={16} className="icon-slot" />
          {metaError}
        </p>
      )}

      <section className="form-card">
        <form onSubmit={onSubmit} noValidate>
          <LocationField
            value={state.location}
            onChange={(location) => setState((s) => ({ ...s, location }))}
            options={meta?.neighborhoods ?? []}
            disabled={loading}
            error={locationError}
          />

          <div className="field">
            <div className="field-label-row">
              <span className="field-label text-label-md">
                <Icon name="wallet" size={18} className="icon-slot" />
                Budget for two
              </span>
              <span className="text-body-sm muted">Estimated cost</span>
            </div>
            <div className="segmented" role="radiogroup" aria-label="Budget for two">
              {BUDGETS.map((b) => (
                <button
                  key={b.value}
                  type="button"
                  role="radio"
                  aria-checked={state.budget === b.value}
                  disabled={loading}
                  className={state.budget === b.value ? "segment active" : "segment"}
                  onClick={() => setState((s) => ({ ...s, budget: b.value }))}
                >
                  <span className="text-label-lg">{b.label}</span>
                  <small className="text-body-sm">{b.hint}</small>
                </button>
              ))}
            </div>
          </div>

          <div className="field">
            <div className="field-label-row">
              <span className="field-label text-label-md">
                <Icon name="fork" size={18} className="icon-slot" />
                Cuisine &amp; specialties
              </span>
              <span className="text-body-sm muted">Broad genre or a specific dish</span>
            </div>
            <div className="dual-combo">
              <div className="dual-combo-half select-half">
                <Icon name="dish" size={18} className="icon-slot" />
                <select
                  aria-label="Cuisine"
                  value={state.cuisineSelect}
                  disabled={loading}
                  onChange={(e) => setState((s) => ({ ...s, cuisineSelect: e.target.value }))}
                >
                  <option value="">Any cuisine</option>
                  {meta?.cuisines.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
              <div className="dual-combo-half text-half">
                <Icon name="edit" size={18} className="icon-slot" />
                <input
                  aria-label="Or type a cuisine"
                  type="text"
                  maxLength={100}
                  placeholder="e.g. woodfired pizza, filter coffee"
                  value={state.cuisineText}
                  disabled={loading}
                  onChange={(e) => setState((s) => ({ ...s, cuisineText: e.target.value }))}
                />
              </div>
            </div>
          </div>

          <div className="rating-field">
            <div className="rating-field-top">
              <label className="field-label text-label-md" htmlFor="min-rating">
                <Icon name="star" size={18} className="icon-slot" />
                Minimum rating
              </label>
              <span className="rating-readout text-label-md">
                <Icon name="star" size={14} filled className="icon-slot" />
                {ratingLabel}
              </span>
            </div>
            <input
              id="min-rating"
              className="slider-track"
              type="range"
              min={0}
              max={5}
              step={0.1}
              value={state.minRating}
              disabled={loading}
              onChange={(e) => setState((s) => ({ ...s, minRating: Number(e.target.value) }))}
            />
            <div className="rating-scale text-body-sm">
              <span>Any</span>
              <span>3.5 Decent</span>
              <span className="top">4.5+ Elite</span>
            </div>
          </div>

          <div className="field">
            <div className="field-label-row">
              <label className="field-label text-label-md" htmlFor="preferences">
                <Icon name="sparkles" size={18} className="icon-slot" />
                Specific vibe &amp; preferences
              </label>
              <span className="text-body-sm muted">Optional</span>
            </div>
            <div className="textarea-shell">
              <textarea
                id="preferences"
                rows={3}
                maxLength={MAX_PREFERENCES}
                placeholder="e.g. family-friendly, quick service, table booking, outdoor seating"
                value={state.preferences}
                disabled={loading}
                onChange={(e) => setState((s) => ({ ...s, preferences: e.target.value }))}
              />
              <div className="textarea-footer text-body-sm">
                <span className="ai-hint">
                  <Icon name="sparkles" size={14} className="icon-slot" />
                  AI matches vibe, dietary and seating notes
                </span>
                <span className={counterNearLimit ? "textarea-counter is-near-limit" : "textarea-counter"}>
                  {state.preferences.length}/{MAX_PREFERENCES}
                </span>
              </div>
            </div>
          </div>

          <button className="btn-primary text-label-lg" type="submit" disabled={loading}>
            {loading ? (
              <>
                <Icon name="refresh" size={18} className="spinner" />
                <span>Finding tables&hellip;</span>
              </>
            ) : (
              <>
                <span>Get recommendations</span>
                <Icon name="arrow" size={18} />
              </>
            )}
          </button>
        </form>
      </section>

      <div className="metric-bar">
        <div className="metric-bar-left">
          <div className="metric-icon">
            <Icon name="layers" size={18} />
          </div>
          <div>
            <div className="text-label-md on-surface">Real Bangalore catalog</div>
            <div className="text-body-sm muted">
              {meta ? `${meta.neighborhoods.length} neighborhoods • ${meta.cuisines.length} cuisines` : "Loading catalog…"}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
