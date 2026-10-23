"use client";

import { useEffect, useId, useRef, useState } from "react";
import Icon from "./Icon";

export default function LocationField({
  value,
  onChange,
  options,
  disabled,
  error,
}: {
  value: string;
  onChange: (next: string) => void;
  options: string[];
  disabled: boolean;
  error: string | null;
}) {
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const rootRef = useRef<HTMLDivElement>(null);
  const listId = useId();

  const query = value.trim().toLowerCase();
  const matches = (query ? options.filter((o) => o.toLowerCase().includes(query)) : options).slice(0, 8);

  useEffect(() => {
    function onClickOutside(event: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  function select(name: string) {
    onChange(name);
    setOpen(false);
    setActiveIndex(-1);
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (!open && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
      setOpen(true);
      return;
    }
    if (!open) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, matches.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (event.key === "Enter" && activeIndex >= 0 && matches[activeIndex]) {
      event.preventDefault();
      select(matches[activeIndex]);
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div className="field" ref={rootRef}>
      <div className="field-label-row">
        <label className="field-label text-label-md" htmlFor="location-input">
          <Icon name="pin" size={18} className="icon-slot" />
          Location in Bangalore
        </label>
        <span className="text-label-caps muted">Required</span>
      </div>

      <div className="autocomplete">
        <div className={error ? "input-shell has-error" : "input-shell"}>
          <Icon name="search" size={18} className="icon-slot" />
          <input
            id="location-input"
            role="combobox"
            aria-expanded={open}
            aria-controls={listId}
            aria-autocomplete="list"
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? "location-error" : undefined}
            autoComplete="off"
            placeholder="Search neighborhood, e.g. Indiranagar"
            value={value}
            disabled={disabled}
            onChange={(e) => {
              onChange(e.target.value);
              setOpen(true);
              setActiveIndex(-1);
            }}
            onFocus={() => setOpen(true)}
            onKeyDown={onKeyDown}
          />
          {value && (
            <button
              type="button"
              className="input-clear"
              title="Clear"
              onClick={() => {
                onChange("");
                setOpen(false);
              }}
            >
              <Icon name="x" size={16} />
            </button>
          )}
        </div>

        {open && !disabled && (
          <div className="autocomplete-panel">
            <div className="autocomplete-panel-header">
              <span className="text-label-caps muted">
                {query ? "Matching neighborhoods" : "Popular dining precincts"}
              </span>
            </div>
            {matches.length === 0 ? (
              <p className="autocomplete-empty text-body-sm">No Bangalore neighborhood matches that yet.</p>
            ) : (
              <ul className="autocomplete-list" id={listId} role="listbox">
                {matches.map((name, i) => (
                  <li key={name} role="option" aria-selected={name === value}>
                    <button
                      type="button"
                      className="autocomplete-item"
                      data-active={i === activeIndex}
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => select(name)}
                    >
                      <Icon name="pin" size={16} className="icon-slot" />
                      <span className="text-label-md">{name}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {error && (
        <p id="location-error" className="hint-banner is-error text-body-sm" role="alert">
          <Icon name="info" size={16} className="icon-slot" />
          {error}
        </p>
      )}
    </div>
  );
}
