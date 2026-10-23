"""Bangalore Culinary Pulse — all-in-one Streamlit app.

Embeds the FastAPI backend logic directly so the entire system
deploys as a single Streamlit Cloud app.
"""
import os
import sys
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------------------
# Bootstrap: add backend/ to sys.path so `from app.*` imports work
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent
_BACKEND_DIR = _PROJECT_ROOT / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# Bridge Streamlit secrets → env vars (before Settings is instantiated)
_SECRET_KEYS = [
    "LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "LLM_REASONING_EFFORT",
    "LLM_TEMPERATURE", "LLM_TIMEOUT_SECONDS", "DATABASE_PATH",
    "LLM_USAGE_DB", "LLM_RPM_LIMIT", "LLM_RPD_LIMIT", "LLM_TPM_LIMIT",
    "LLM_TPD_LIMIT",
]
try:
    for _k in _SECRET_KEYS:
        if _k in st.secrets:
            os.environ[_k] = str(st.secrets[_k])
except FileNotFoundError:
    pass  # no secrets file locally — .env will be used instead

from app.config import Settings  # noqa: E402
from app.models.schemas import RecommendationRequest  # noqa: E402
from app.services.catalog import Catalog, CatalogUnavailableError  # noqa: E402
from app.services.llm import LLMClient  # noqa: E402
from app.services.llm_budget import LLMBudget  # noqa: E402
from app.services.recommend import recommend  # noqa: E402
from app.services.response_cache import ResponseCache  # noqa: E402
from app.services.retrieve import normalize_preferences, retrieve_candidates  # noqa: E402

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Bangalore Culinary Pulse",
    page_icon="\U0001F525",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Singletons (persist across Streamlit reruns)
# ---------------------------------------------------------------------------

@st.cache_resource
def _load_settings() -> Settings:
    return Settings()


@st.cache_resource
def _load_catalog(db_path: str) -> Catalog:
    return Catalog(db_path)


@st.cache_resource
def _load_llm(api_key: str, _settings_id: int) -> LLMClient | None:
    settings = _load_settings()
    return LLMClient(settings) if api_key else None


@st.cache_resource
def _load_budget(_settings_id: int) -> LLMBudget:
    return LLMBudget(_load_settings())


@st.cache_resource
def _load_cache(ttl: int, max_entries: int) -> ResponseCache:
    return ResponseCache(ttl, max_entries)


def _get_services():
    settings = _load_settings()
    catalog = _load_catalog(settings.database_path)
    llm = _load_llm(settings.llm_api_key, id(settings))
    budget = _load_budget(id(settings))
    cache = _load_cache(settings.cache_ttl_seconds, settings.cache_max_entries)
    return settings, catalog, llm, budget, cache


# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    /* Overall */
    .block-container { max-width: 900px; }

    /* Card styling */
    .rec-card {
        border: 1px solid #333;
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        background: #1a1a2e;
    }
    .rec-card-top { border-color: #f97316; border-width: 2px; }
    .rec-rank {
        display: inline-flex; align-items: center; justify-content: center;
        width: 36px; height: 36px; border-radius: 50%;
        background: #333; color: #fff; font-weight: 700; font-size: 1rem;
    }
    .rec-rank-top { background: #f97316; }
    .rec-name { font-size: 1.2rem; font-weight: 700; margin: 0; }
    .chip {
        display: inline-block; padding: 2px 10px; border-radius: 20px;
        font-size: 0.82rem; margin-right: 6px; margin-top: 4px;
        background: #2a2a40; color: #ccc;
    }
    .chip-rating-high { background: #166534; color: #86efac; }
    .chip-rating-mid  { background: #854d0e; color: #fde68a; }
    .chip-rating-low  { background: #7f1d1d; color: #fca5a5; }
    .why-box {
        border-left: 3px solid #f97316; padding: 0.6rem 1rem;
        margin-top: 0.75rem; background: #1e1e30; border-radius: 0 8px 8px 0;
        font-size: 0.92rem; color: #d1d5db;
    }
    .badge-ai {
        display: inline-block; padding: 2px 10px; border-radius: 20px;
        font-size: 0.78rem; background: #312e81; color: #a5b4fc;
    }
    .badge-catalog {
        display: inline-block; padding: 2px 10px; border-radius: 20px;
        font-size: 0.78rem; background: #1e3a5f; color: #93c5fd;
    }
    .summary-quote {
        border-left: 3px solid #6366f1; padding: 0.6rem 1rem;
        margin: 0.75rem 0; background: #1e1e30; border-radius: 0 8px 8px 0;
        font-style: italic; color: #c4b5fd;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown("# \U0001F525 Bangalore Culinary Pulse")
st.caption("AI-powered restaurant recommendations from a real Bangalore catalog")

# ---------------------------------------------------------------------------
# Load catalog metadata
# ---------------------------------------------------------------------------
try:
    settings, catalog, llm, budget, cache = _get_services()
    meta = catalog.meta()
    neighborhoods = sorted(meta["neighborhoods"])
    cuisines = sorted(meta["cuisines"])
    catalog_ok = True
except (CatalogUnavailableError, Exception) as exc:
    st.error(f"Could not load the restaurant catalog: {exc}")
    catalog_ok = False
    neighborhoods, cuisines = [], []

if not catalog_ok:
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar — Preference form
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Your preferences")

    location = st.selectbox(
        "Neighborhood",
        options=[""] + neighborhoods,
        format_func=lambda x: "Choose a neighborhood..." if x == "" else x,
    )

    budget_options = {"Low (up to ₹400)": "low", "Medium (₹401–800)": "medium", "High (₹801+)": "high"}
    budget_label = st.radio("Budget for two", list(budget_options.keys()), index=1)
    budget_value = budget_options[budget_label]

    cuisine_select = st.selectbox(
        "Cuisine",
        options=["Any cuisine"] + cuisines,
    )
    cuisine_text = st.text_input(
        "Or type a cuisine / dish",
        max_chars=100,
        placeholder="e.g. woodfired pizza, filter coffee",
    )
    cuisine_final = cuisine_text.strip() if cuisine_text.strip() else (
        None if cuisine_select == "Any cuisine" else cuisine_select
    )

    min_rating = st.slider(
        "Minimum rating",
        min_value=0.0, max_value=5.0, value=0.0, step=0.1,
        format="%.1f",
        help="0 = any rating",
    )

    preferences = st.text_area(
        "Vibe & preferences",
        max_chars=500,
        placeholder="e.g. family-friendly, quick service, outdoor seating",
        help="AI matches vibe, dietary and seating notes",
    )

    st.divider()
    st.caption(f"**Catalog:** {len(neighborhoods)} neighborhoods · {len(cuisines)} cuisines")

    search_clicked = st.button(
        "\U0001F50D  Get Recommendations",
        type="primary",
        use_container_width=True,
        disabled=(location == ""),
    )

# ---------------------------------------------------------------------------
# Run recommendation engine
# ---------------------------------------------------------------------------
if search_clicked and location:
    with st.spinner("Asking the AI to rank the best matches..."):
        try:
            request = RecommendationRequest(
                location=location,
                budget=budget_value,
                cuisine=cuisine_final,
                min_rating=min_rating,
                additional_preferences=preferences,
            )
            prefs = normalize_preferences(request, settings)
            retrieval = retrieve_candidates(catalog, prefs, settings)
            response = recommend(prefs, retrieval, settings, llm, budget, cache)

            st.session_state["response"] = response
            st.session_state["search_location"] = location
            st.session_state["search_budget"] = budget_label
            st.session_state["search_cuisine"] = cuisine_final
            st.session_state["search_rating"] = min_rating
        except CatalogUnavailableError as exc:
            st.error(f"Catalog error: {exc}")
        except Exception as exc:
            st.error(f"Something went wrong: {exc}")

# ---------------------------------------------------------------------------
# Display results
# ---------------------------------------------------------------------------
if "response" not in st.session_state:
    st.info("Choose a neighborhood and click **Get Recommendations** to start.")
    st.stop()

response = st.session_state["response"]
loc = st.session_state["search_location"]
meta_info = response.meta
recs = response.recommendations

# Filter summary
filter_parts = [f"**{loc}**"]
if st.session_state.get("search_budget"):
    filter_parts.append(st.session_state["search_budget"])
if st.session_state.get("search_rating", 0) > 0:
    filter_parts.append(f"★ {st.session_state['search_rating']:.1f}+")
if st.session_state.get("search_cuisine"):
    filter_parts.append(st.session_state["search_cuisine"])
st.caption("Showing results for: " + " · ".join(filter_parts))

# Header + badge
if recs:
    badge = '<span class="badge-ai">✨ AI ranked</span>' if meta_info.used_llm else '<span class="badge-catalog">\U0001F4DA Catalog ranking</span>'
    st.markdown(f"### Top {len(recs)} for {loc} {badge}", unsafe_allow_html=True)

    # Summary quote
    if response.summary:
        st.markdown(f'<div class="summary-quote">{response.summary}</div>', unsafe_allow_html=True)

    # Notices
    if meta_info.fallback:
        reason = meta_info.fallback_reason
        if reason == "rate_limited":
            retry = meta_info.retry_after_seconds
            wait_msg = f" Try again in {retry}s." if retry and retry < 120 else ""
            st.warning(f"AI ranking is at capacity — showing catalog-ranked results.{wait_msg}")
        elif reason == "no_api_key":
            st.info("No LLM API key configured — showing catalog-ranked results with standard descriptions.")
        else:
            st.warning("AI ranking unavailable — showing catalog-ranked results.")

    if meta_info.budget_relaxed:
        st.info("Few restaurants matched your exact budget, so the range was widened slightly.")

    # Recommendation cards
    for rec in recs:
        rank_class = "rec-rank-top" if rec.rank == 1 else ""
        card_class = "rec-card-top" if rec.rank == 1 else ""

        # Rating chip
        rating_text = f"★ {rec.rating:.1f}" if rec.rating is not None else "Not rated"
        if rec.rating is not None:
            if rec.rating >= 4.0:
                rating_chip_class = "chip chip-rating-high"
            elif rec.rating >= 3.5:
                rating_chip_class = "chip chip-rating-mid"
            else:
                rating_chip_class = "chip chip-rating-low"
        else:
            rating_chip_class = "chip"

        # Cost chip
        cost_text = f"₹{rec.estimated_cost:,} for two" if rec.estimated_cost else "Cost not listed"

        # Build chips
        chips_html = f'<span class="{rating_chip_class}">{rating_text}</span>'
        chips_html += f'<span class="chip">{cost_text}</span>'
        if rec.neighborhood:
            chips_html += f'<span class="chip">\U0001F4CD {rec.neighborhood}</span>'
        if rec.rest_type:
            chips_html += f'<span class="chip">{rec.rest_type}</span>'

        # Why it fits
        why_html = ""
        if rec.explanation:
            why_html = f'<div class="why-box"><strong>Why it fits:</strong> {rec.explanation}</div>'

        # Top pick tag
        top_tag = ' <span class="badge-ai">✨ Top pick</span>' if rec.rank == 1 else ""

        cuisine_display = rec.cuisine or "Cuisine not listed"

        st.markdown(f"""
        <div class="rec-card {card_class}">
            <span class="rec-rank {rank_class}">{rec.rank}</span>
            <span class="rec-name">{rec.name}</span>{top_tag}
            <div style="color:#9ca3af; margin-top:2px; font-size:0.9rem;">{cuisine_display}</div>
            <div style="margin-top:8px;">{chips_html}</div>
            {why_html}
        </div>
        """, unsafe_allow_html=True)

else:
    st.warning("No restaurants match these filters. Try a different neighborhood or widen your budget.")
