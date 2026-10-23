import Icon from "./Icon";
import type { Recommendation } from "../lib/api";
import { cleanText, rankAccent, ratingTone } from "../lib/text";

export default function RecommendationCard({ item }: { item: Recommendation }) {
  const name = cleanText(item.name, 120);
  const cuisine = cleanText(item.cuisine, 160);
  const explanation = cleanText(item.explanation);
  const neighborhood = cleanText(item.neighborhood, 80);
  const restType = cleanText(item.rest_type, 80);
  const tone = ratingTone(item.rating);
  const accent = rankAccent(item.rank);
  const isTop = item.rank === 1;

  return (
    <li className={isTop ? "rec-card rank-1" : "rec-card"}>
      <div className="rec-card-top">
        <div className="rec-rank" aria-hidden="true">
          {item.rank}
        </div>
        <div className="rec-card-title-block">
          <div className="rec-card-top" style={{ gap: "0.5rem" }}>
            <h3 className="text-headline-sm" style={{ flex: 1 }}>
              <span className="visually-hidden">Rank {item.rank}: </span>
              {name}
            </h3>
            {isTop && (
              <span className="top-pick-tag text-label-caps">
                <Icon name="sparkles" size={13} className="icon-slot" />
                Top pick
              </span>
            )}
          </div>
          <p className="text-body-sm rec-cuisine">{cuisine || "Cuisine not listed"}</p>
        </div>
      </div>

      <ul className="chip-list" aria-label="Key facts">
        <li className={`chip is-rating rating-${tone}`}>
          <Icon name="star" size={14} filled className="icon-slot" />
          {item.rating !== null ? (
            <>
              {item.rating.toFixed(1)}
              <span className="visually-hidden"> out of 5</span>
            </>
          ) : (
            "Not rated"
          )}
        </li>
        <li className="chip">
          {item.estimated_cost !== null ? `₹${item.estimated_cost.toLocaleString("en-IN")} for two` : "Cost not listed"}
        </li>
        {neighborhood && (
          <li className="chip">
            <Icon name="pin" size={13} className="icon-slot" />
            {neighborhood}
          </li>
        )}
        {restType && <li className="chip">{restType}</li>}
      </ul>

      {explanation && (
        <div className={`why-fits accent-${accent}`}>
          <span className="why-fits-label text-label-caps">Why it fits</span>
          <p className="text-body-sm">{explanation}</p>
        </div>
      )}
    </li>
  );
}
