"use client";

import { useEffect, useRef } from "react";
import Icon from "./Icon";
import RecommendationCard from "./RecommendationCard";
import { BUDGETS } from "./PreferenceForm";
import type { RecommendationRequest, RecommendationResponse } from "../lib/api";
import { cleanText } from "../lib/text";

/** The panel always shows exactly one of these, so results/errors/empty never linger next to a loading state. */
export type PanelState =
  | { kind: "idle" }
  | { kind: "loading"; request: RecommendationRequest }
  | { kind: "error"; message: string; request: RecommendationRequest }
  | { kind: "done"; request: RecommendationRequest; data: RecommendationResponse };

function retryHint(seconds: number | null | undefined): string {
  if (!seconds || seconds <= 0) return "Try again shortly for AI-written explanations.";
  if (seconds <= 90) return `Try again in about ${seconds} second${seconds === 1 ? "" : "s"} for AI-written explanations.`;
  if (seconds <= 3600) return `Try again in about ${Math.ceil(seconds / 60)} minutes for AI-written explanations.`;
  return "The AI daily limit has been reached, so AI-written explanations are unavailable for now.";
}

function fallbackMessage(reason: string | null | undefined, retryAfter: number | null | undefined): string {
  if (reason === "rate_limited") {
    return `The AI ranking engine is at capacity right now, so these are the top catalog matches with a standard description. ${retryHint(retryAfter)}`;
  }
  return "Ranked without AI because the model was unavailable. These are the top catalog matches with a standard description.";
}

function FilterSummary({ request, onEdit }: { request: RecommendationRequest; onEdit: () => void }) {
  const budget = BUDGETS.find((b) => b.value === request.budget);
  const cuisine = cleanText(request.cuisine, 60);
  return (
    <div className="filter-summary">
      <div className="filter-summary-text text-body-sm">
        <Icon name="sliders" size={16} className="icon-slot" />
        <span className="text-label-md accent">{cleanText(request.location, 60)}</span>
        {budget && (
          <>
            <span className="filter-summary-sep">&bull;</span>
            <span>{budget.hint}</span>
          </>
        )}
        {request.min_rating > 0 && (
          <>
            <span className="filter-summary-sep">&bull;</span>
            <span className="accent text-label-md">&#9733; {request.min_rating.toFixed(1)}+</span>
          </>
        )}
        {cuisine && (
          <>
            <span className="filter-summary-sep">&bull;</span>
            <span className="muted">{cuisine}</span>
          </>
        )}
      </div>
      <button type="button" className="filter-summary-edit text-label-md" onClick={onEdit}>
        <span>Edit</span>
        <Icon name="edit" size={14} />
      </button>
    </div>
  );
}

function Loading({ request, onEdit }: { request: RecommendationRequest; onEdit: () => void }) {
  return (
    <div role="status">
      <FilterSummary request={request} onEdit={onEdit} />
      <div style={{ marginTop: "1.5rem" }}>
        <div className="skeleton-loading-line text-body-sm">
          <Icon name="refresh" size={16} className="icon-slot" />
          <span>Asking the AI to rank the best matches. This can take a few seconds&hellip;</span>
        </div>
        <ul className="cards" aria-hidden="true">
          {[0, 1, 2].map((i) => (
            <li key={i} className="skeleton-card">
              <div className="skeleton-row">
                <div className="skeleton-circle" />
                <div className="skeleton-bar" style={{ width: "45%" }} />
              </div>
              <div className="skeleton-bar" style={{ width: "65%" }} />
              <div className="skeleton-bar" style={{ width: "90%", height: "2.5rem" }} />
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function Empty({ request, onEdit }: { request: RecommendationRequest; onEdit: () => void }) {
  return (
    <>
      <FilterSummary request={request} onEdit={onEdit} />
      <div className="state-card" style={{ marginTop: "1.5rem" }}>
        <div className="state-icon-ring">
          <Icon name="search-off" size={26} />
        </div>
        <h2 id="results-heading" className="text-headline-sm" tabIndex={-1}>
          No restaurants match these filters
        </h2>
        <p className="text-body-sm">
          Try a different location, a wider budget, or a lower minimum rating. The catalog only covers Bangalore
          neighborhoods, so other cities won&apos;t have results.
        </p>
        <div className="state-card-actions">
          <button type="button" className="btn-secondary text-label-md" onClick={onEdit}>
            <Icon name="sliders" size={16} />
            Edit filters
          </button>
        </div>
      </div>
    </>
  );
}

function ErrorCard({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="error-card" role="alert">
      <div className="error-card-top">
        <div className="error-icon">
          <Icon name="alert" size={22} />
        </div>
        <div>
          <h2 id="results-heading" className="text-title-md" tabIndex={-1}>
            Something went wrong
          </h2>
          <p className="text-body-sm">{message}</p>
        </div>
      </div>
      <div className="error-card-actions">
        <button type="button" className="btn-secondary btn-danger text-label-md" onClick={onRetry}>
          <Icon name="refresh" size={16} />
          Try again
        </button>
      </div>
    </div>
  );
}

function Done({
  request,
  data,
  onEdit,
}: {
  request: RecommendationRequest;
  data: RecommendationResponse;
  onEdit: () => void;
}) {
  const { recommendations, summary, meta } = data;
  const location = cleanText(request.location, 100);

  if (recommendations.length === 0) {
    return <Empty request={request} onEdit={onEdit} />;
  }

  const summaryText = cleanText(summary);
  return (
    <>
      <FilterSummary request={request} onEdit={onEdit} />

      <div className="results-header" style={{ marginTop: "1.5rem" }}>
        <div className="results-heading-group">
          <h2 id="results-heading" className="text-headline-md" tabIndex={-1}>
            Top {recommendations.length} for {location}
          </h2>
        </div>
        <span className={meta.fallback ? "rank-badge-pill is-catalog text-label-caps" : "rank-badge-pill is-ai text-label-caps"}>
          <Icon name={meta.fallback ? "layers" : "sparkles"} size={13} filled={!meta.fallback} />
          {meta.fallback ? "Catalog ranking" : "AI ranked"}
        </span>
      </div>

      {summaryText && (
        <div className="summary-quote">
          <p>
            <Icon name="info" size={18} className="icon-slot" />
            <span>&ldquo;{summaryText}&rdquo;</span>
          </p>
        </div>
      )}

      {meta.fallback && (
        <div className="notice-banner">
          <div className="notice-icon">
            <Icon name="info" size={17} />
          </div>
          <p className="text-body-sm">{fallbackMessage(meta.fallback_reason, meta.retry_after_seconds)}</p>
        </div>
      )}
      {meta.budget_relaxed && (
        <div className="notice-banner is-muted">
          <div className="notice-icon">
            <Icon name="sliders" size={16} />
          </div>
          <p className="text-body-sm">Few restaurants matched your exact budget, so the range was widened slightly.</p>
        </div>
      )}

      <ol className="cards">
        {recommendations.map((item) => (
          <RecommendationCard key={item.restaurant_id} item={item} />
        ))}
      </ol>
    </>
  );
}

export default function ResultsPanel({
  state,
  onRetry,
  onEdit,
}: {
  state: PanelState;
  onRetry: () => void;
  onEdit: () => void;
}) {
  const panelRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (state.kind === "done" || state.kind === "error") {
      panelRef.current?.querySelector<HTMLElement>("#results-heading")?.focus({ preventScroll: true });
      const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      panelRef.current?.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
    }
  }, [state]);

  if (state.kind === "idle") return null;

  return (
    <section ref={panelRef} className="results" aria-labelledby="results-heading" aria-busy={state.kind === "loading"}>
      {state.kind === "loading" && <Loading request={state.request} onEdit={onEdit} />}
      {state.kind === "error" && (
        <>
          <FilterSummary request={state.request} onEdit={onEdit} />
          <ErrorCard message={state.message} onRetry={onRetry} />
        </>
      )}
      {state.kind === "done" && <Done request={state.request} data={state.data} onEdit={onEdit} />}
    </section>
  );
}
