"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import PreferenceForm, { FormState } from "./PreferenceForm";
import ResultsPanel, { PanelState } from "./ResultsPanel";
import { ApiError, CatalogMeta, RecommendationRequest, fetchMeta, fetchRecommendations } from "../lib/api";

const INITIAL_FORM: FormState = {
  location: "",
  budget: "medium",
  cuisineSelect: "",
  cuisineText: "",
  minRating: 0,
  preferences: "",
};

export default function RecommendationApp() {
  const [meta, setMeta] = useState<CatalogMeta | null>(null);
  const [metaError, setMetaError] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const [locationError, setLocationError] = useState<string | null>(null);
  const [panel, setPanel] = useState<PanelState>({ kind: "idle" });

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

  async function search(request: RecommendationRequest) {
    inFlight.current?.abort();
    const controller = new AbortController();
    inFlight.current = controller;
    setPanel({ kind: "loading", request });

    try {
      const data = await fetchRecommendations(request, controller.signal);
      setPanel({ kind: "done", request, data });
    } catch (err) {
      if (controller.signal.aborted) return;
      setPanel({
        kind: "error",
        request,
        message: err instanceof ApiError ? err.message : "Something went wrong. Please try again.",
      });
    }
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (panel.kind === "loading") return;

    const trimmedLocation = form.location.trim();
    if (!trimmedLocation) {
      setLocationError("Please choose or type a Bangalore neighborhood.");
      return;
    }
    setLocationError(null);

    void search({
      location: trimmedLocation,
      budget: form.budget,
      cuisine: form.cuisineText.trim() || form.cuisineSelect || undefined,
      min_rating: form.minRating,
      additional_preferences: form.preferences.trim(),
    });
  }

  function onEdit() {
    document.getElementById("location-input")?.focus();
    document.querySelector(".form-card")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function onRetry() {
    if (panel.kind === "error") void search(panel.request);
  }

  const loading = panel.kind === "loading";

  return (
    <div className="page">
      <PreferenceForm
        meta={meta}
        metaError={metaError}
        state={form}
        setState={setForm}
        locationError={locationError}
        loading={loading}
        onSubmit={onSubmit}
      />
      <ResultsPanel state={panel} onRetry={onRetry} onEdit={onEdit} />
    </div>
  );
}
