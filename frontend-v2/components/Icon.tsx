/**
 * Small inline SVG icon set, self-contained (no icon-font network dependency).
 * Stroke-based, 24x24 viewBox, matches the Stitch "editorial / technical precision" brief.
 */
const PATHS: Record<string, React.ReactNode> = {
  pin: (
    <>
      <path d="M12 21s-7-6.1-7-11.2A7 7 0 0 1 12 3a7 7 0 0 1 7 6.8C19 14.9 12 21 12 21Z" />
      <circle cx="12" cy="9.8" r="2.4" />
    </>
  ),
  wallet: (
    <>
      <rect x="3" y="6" width="18" height="13" rx="2" />
      <path d="M3 10h18" />
      <circle cx="16.5" cy="14" r="1.1" fill="currentColor" stroke="none" />
    </>
  ),
  fork: (
    <>
      <path d="M8 3v7a2 2 0 0 0 4 0V3M10 10v11M16 3v7a2 2 0 0 0 2 2v9" />
    </>
  ),
  star: <path d="m12 3 2.6 5.6 6.1.6-4.6 4.1 1.3 6-5.4-3.1-5.4 3.1 1.3-6-4.6-4.1 6.1-.6Z" />,
  sparkles: (
    <>
      <path d="m12 3 1.2 3.3L16.5 7.5l-3.3 1.2L12 12l-1.2-3.3L7.5 7.5l3.3-1.2Z" />
      <path d="M19 14l.7 1.9 1.9.7-1.9.7-.7 1.9-.7-1.9-1.9-.7 1.9-.7Z" />
    </>
  ),
  layers: (
    <>
      <path d="m12 3 8 4.5-8 4.5-8-4.5Z" />
      <path d="m4 12 8 4.5 8-4.5" />
      <path d="m4 16.5 8 4.5 8-4.5" />
    </>
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v6M12 8v.01" />
    </>
  ),
  sliders: (
    <>
      <path d="M4 6h10M18 6h2M4 12h2M8 12h12M4 18h14M20 18h0" />
      <circle cx="16" cy="6" r="2" />
      <circle cx="6" cy="12" r="2" />
      <circle cx="18" cy="18" r="2" />
    </>
  ),
  alert: (
    <>
      <path d="M10.3 3.6 1.9 18a2 2 0 0 0 1.7 3h16.8a2 2 0 0 0 1.7-3L13.7 3.6a2 2 0 0 0-3.4 0Z" />
      <path d="M12 9v4M12 16.5v.01" />
    </>
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.3-4.3" />
    </>
  ),
  "search-off": (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.3-4.3M8 8l6 6" />
    </>
  ),
  x: <path d="M6 6l12 12M18 6 6 18" />,
  chevron: <path d="m6 9 6 6 6-6" />,
  arrow: <path d="M4 12h15M13 6l6 6-6 6" />,
  edit: (
    <>
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z" />
    </>
  ),
  flame: (
    <path d="M12 2s4 4.5 4 8.5a4 4 0 0 1-8 0c0-1 .4-1.8 1-2.5-.3 1.4.3 2.2 1 2.5-.2-2 .3-3.8 2-5.5Zm-4.5 8.8A6.5 6.5 0 0 0 12 22a6.5 6.5 0 0 0 4.5-11.2c.6 1 1 2.2 1 3.7a5.5 5.5 0 0 1-11 0c0-1.5.4-2.7 1-3.7Z" />
  ),
  refresh: (
    <>
      <path d="M20 11A8 8 0 0 0 6.3 6.3L4 8.6" />
      <path d="M4 4v4.6h4.6" />
      <path d="M4 13a8 8 0 0 0 13.7 4.7L20 15.4" />
      <path d="M20 20v-4.6h-4.6" />
    </>
  ),
  dish: (
    <>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="3.5" />
    </>
  ),
};

export default function Icon({
  name,
  size = 18,
  filled = false,
  className,
}: {
  name: keyof typeof PATHS;
  size?: number;
  filled?: boolean;
  className?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      {PATHS[name]}
    </svg>
  );
}
