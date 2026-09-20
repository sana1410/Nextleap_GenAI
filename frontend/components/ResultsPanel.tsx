"use client";

import { useEffect, useRef } from "react";
import type { RecommendationResponse } from "../lib/api";
import { cleanText } from "../lib/text";
import RecommendationCard from "./RecommendationCard";

/**
 * The panel always shows exactly one of these. Starting a new search clears the previous
 * outcome, so results, errors and empty states never linger next to a loading state.
 */
export type PanelState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "done"; location: string; data: RecommendationResponse };

export default function ResultsPanel({ state, onRetry }: { state: PanelState; onRetry: () => void }) {
  const panelRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (state.kind === "done" || state.kind === "error") {
      panelRef.current?.querySelector<HTMLElement>("#results-heading")?.focus({ preventScroll: true });
      const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      panelRef.current?.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
    }
  }, [state]);

  return (
    <section ref={panelRef} className="results" aria-labelledby="results-heading" aria-busy={state.kind === "loading"}>
      {state.kind === "loading" && <Loading />}

      {state.kind === "error" && (
        <div className="state state-error" role="alert">
          <h2 id="results-heading" tabIndex={-1}>
            Something went wrong
          </h2>
          <p>{state.message}</p>
          <button type="button" className="secondary" onClick={onRetry}>
            Try again
          </button>
        </div>
      )}

      {state.kind === "done" && <Done state={state} />}

      {(state.kind === "idle" || state.kind === "loading") && (
        <h2 id="results-heading" className="visually-hidden">
          Recommendations
        </h2>
      )}
    </section>
  );
}

function retryHint(seconds: number | null | undefined): string {
  if (!seconds || seconds <= 0) return "Try again shortly for AI-written explanations.";
  if (seconds <= 90) return `Try again in about ${seconds} second${seconds === 1 ? "" : "s"} for AI-written explanations.`;
  if (seconds <= 3600) return `Try again in about ${Math.ceil(seconds / 60)} minutes for AI-written explanations.`;
  return "The AI daily limit has been reached, so AI-written explanations are unavailable for now.";
}

function fallbackMessage(reason: string | null | undefined, retryAfter: number | null | undefined): string {
  if (reason === "rate_limited") {
    return `The AI ranking service is at capacity right now, so these are the top catalog matches with a standard description. ${retryHint(retryAfter)}`;
  }
  return "Ranked without AI because the model was unavailable. These are the top catalog matches with a standard description.";
}

function Loading() {
  return (
    <div role="status">
      <p className="state-loading">Asking the AI to rank the best matches. This can take a few seconds…</p>
      <ul className="cards" aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <li key={i} className="card skeleton">
            <div className="rank" />
            <div className="card-body">
              <div className="bar bar-title" />
              <div className="bar bar-sub" />
              <div className="bar bar-text" />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Done({ state }: { state: Extract<PanelState, { kind: "done" }> }) {
  const { recommendations, summary, meta } = state.data;
  const location = cleanText(state.location, 100);

  if (recommendations.length === 0) {
    return (
      <div className="state state-empty">
        <h2 id="results-heading" tabIndex={-1}>
          No restaurants match these filters
        </h2>
        <p>
          Try a different location, a wider budget, or a lower minimum rating. The catalog only covers Bangalore
          neighborhoods, so other cities won&apos;t have results.
        </p>
      </div>
    );
  }

  const summaryText = cleanText(summary);
  return (
    <>
      <div className="results-header">
        <h2 id="results-heading" tabIndex={-1}>
          Top {recommendations.length} for {location}
        </h2>
        <span className={meta.fallback ? "badge badge-fallback" : "badge badge-ai"}>
          {meta.fallback ? "Catalog ranking" : "AI ranked"}
        </span>
      </div>

      {summaryText && <p className="summary">{summaryText}</p>}

      {meta.fallback && (
        <p className="note note-fallback" role="note">
          {fallbackMessage(meta.fallback_reason, meta.retry_after_seconds)}
        </p>
      )}
      {meta.budget_relaxed && (
        <p className="note" role="note">
          Few restaurants matched your exact budget, so the range was widened slightly.
        </p>
      )}

      <ol className="cards">
        {recommendations.map((item) => (
          <RecommendationCard key={item.restaurant_id} item={item} />
        ))}
      </ol>
    </>
  );
}
