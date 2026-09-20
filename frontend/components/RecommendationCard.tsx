import type { Recommendation } from "../lib/api";
import { cleanText, ratingTone } from "../lib/text";

export default function RecommendationCard({ item }: { item: Recommendation }) {
  const name = cleanText(item.name, 120);
  const cuisine = cleanText(item.cuisine, 160);
  const explanation = cleanText(item.explanation);
  const neighborhood = cleanText(item.neighborhood, 80);
  const restType = cleanText(item.rest_type, 80);
  const tone = ratingTone(item.rating);

  return (
    <li className="card">
      <div className="rank" aria-hidden="true">
        {item.rank}
      </div>
      <div className="card-body">
        <h3>
          <span className="visually-hidden">Rank {item.rank}: </span>
          {name}
        </h3>
        <p className="cuisine">{cuisine || "Cuisine not listed"}</p>

        <ul className="facts" aria-label="Key facts">
          <li className={`chip rating rating-${tone}`}>
            <span aria-hidden="true">★ </span>
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
          {neighborhood && <li className="chip chip-muted">{neighborhood}</li>}
          {restType && <li className="chip chip-muted">{restType}</li>}
        </ul>

        {explanation && (
          <div className="explanation">
            <span className="explanation-label">Why it fits</span>
            <p>{explanation}</p>
          </div>
        )}
      </div>
    </li>
  );
}
