"use client";

import { useEffect, useState } from "react";
import Icon from "./Icon";
import { fetchMeta } from "../lib/api";

type SyncState = "checking" | "ok" | "error";

export default function Header() {
  const [sync, setSync] = useState<SyncState>("checking");

  useEffect(() => {
    const controller = new AbortController();
    fetchMeta(controller.signal)
      .then(() => setSync("ok"))
      .catch(() => !controller.signal.aborted && setSync("error"));
    return () => controller.abort();
  }, []);

  return (
    <header className="site-header">
      <div className="site-header-inner">
        <div className="brand">
          <div className="brand-mark">
            <Icon name="flame" size={22} filled />
          </div>
          <div className="brand-text">
            <div className="brand-title-row">
              <span className="text-title-md brand-name">Bangalore Culinary Pulse</span>
              <span className="badge-tag text-label-caps">AI Discovery</span>
            </div>
            <span className="text-body-sm muted">Curated AI Dining Explorer</span>
          </div>
        </div>
        <div className="sync-pill">
          <span className={sync === "error" ? "pulse-dot is-error" : "pulse-dot"} />
          <span className="text-label-caps muted">
            {sync === "error" ? "Catalog unavailable" : "Catalog synced • Bangalore, IN"}
          </span>
        </div>
      </div>
    </header>
  );
}
