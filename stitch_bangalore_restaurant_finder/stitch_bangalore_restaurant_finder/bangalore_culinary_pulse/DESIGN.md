---
name: Bangalore Culinary Pulse
colors:
  surface: '#051424'
  surface-dim: '#051424'
  surface-bright: '#2c3a4c'
  surface-container-lowest: '#010f1f'
  surface-container-low: '#0d1c2d'
  surface-container: '#122131'
  surface-container-high: '#1c2b3c'
  surface-container-highest: '#273647'
  on-surface: '#d4e4fa'
  on-surface-variant: '#e0c0b1'
  inverse-surface: '#d4e4fa'
  inverse-on-surface: '#233143'
  outline: '#a78b7d'
  outline-variant: '#584237'
  surface-tint: '#ffb690'
  primary: '#ffb690'
  on-primary: '#552100'
  primary-container: '#f97316'
  on-primary-container: '#582200'
  inverse-primary: '#9d4300'
  secondary: '#ffb783'
  on-secondary: '#4f2500'
  secondary-container: '#d97722'
  on-secondary-container: '#451f00'
  tertiary: '#7bd0ff'
  on-tertiary: '#00354a'
  tertiary-container: '#00a6df'
  on-tertiary-container: '#00374d'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#ffdbca'
  primary-fixed-dim: '#ffb690'
  on-primary-fixed: '#341100'
  on-primary-fixed-variant: '#783200'
  secondary-fixed: '#ffdcc5'
  secondary-fixed-dim: '#ffb783'
  on-secondary-fixed: '#301400'
  on-secondary-fixed-variant: '#713700'
  tertiary-fixed: '#c4e7ff'
  tertiary-fixed-dim: '#7bd0ff'
  on-tertiary-fixed: '#001e2c'
  on-tertiary-fixed-variant: '#004c69'
  background: '#051424'
  on-background: '#d4e4fa'
  surface-variant: '#273647'
typography:
  headline-xl:
    fontFamily: Plus Jakarta Sans
    fontSize: 3rem
    fontWeight: '700'
    lineHeight: 3.5rem
    letterSpacing: -0.025em
  headline-xl-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 2rem
    fontWeight: '700'
    lineHeight: 2.5rem
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 2.25rem
    fontWeight: '700'
    lineHeight: 2.75rem
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 1.75rem
    fontWeight: '700'
    lineHeight: 2.25rem
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 1.5rem
    fontWeight: '600'
    lineHeight: 2rem
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 1.25rem
    fontWeight: '600'
    lineHeight: 1.75rem
    letterSpacing: -0.01em
  title-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 1.125rem
    fontWeight: '600'
    lineHeight: 1.625rem
  body-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 1rem
    fontWeight: '400'
    lineHeight: 1.625rem
  body-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 0.875rem
    fontWeight: '400'
    lineHeight: 1.375rem
  body-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 0.75rem
    fontWeight: '400'
    lineHeight: 1.125rem
  label-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 0.875rem
    fontWeight: '600'
    lineHeight: 1.25rem
    letterSpacing: 0.01em
  label-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 0.75rem
    fontWeight: '600'
    lineHeight: 1rem
    letterSpacing: 0.025em
  label-caps:
    fontFamily: Plus Jakarta Sans
    fontSize: 0.6875rem
    fontWeight: '700'
    lineHeight: 0.875rem
    letterSpacing: 0.06em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-md: 1.5rem
  gutter-lg: 2rem
  margin: 1rem
  margin-md: 1.5rem
  margin-lg: 3rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1.25rem
  space-xl: 2rem
  space-2xl: 3rem
---

## Brand & Style
The design system establishes a night-out editorial food discovery experience tailored specifically for Bangalore’s discerning dining culture. Balancing the sleek precision of high-tech lifestyle products with the atmospheric warmth of intimate cocktail rooms, craft breweries, and third-wave roasteries, it exudes sophisticated urban curation. 

Drawing from modern dark-mode editorial aesthetics and layered glass-and-slate minimalism, the interface relies on deep, chromatic twilight tones rather than pitch blacks. Visual hierarchy is achieved through distinct tonal layering, fine hairline borders, and targeted moments of warm culinary embers. It minimizes distraction to highlight rich food imagery, curated critique, and social validation. The interface feels discerning, nocturnal, highly legible under low ambient light, and distinctly premium.

## Colors
The palette is built around deep, atmospheric slate-navies, lit sparingly by vibrant culinary ember-orange:

- **Primary & Secondary Accent (`#F97316` / `#FB923C`):** Reserved exclusively for high-intent actions (primary booking/save actions), active rating states, and critical match indicators. Secondary orange (`#FB923C`) acts as the hover/focus highlight.
- **Tertiary Accent (`#38BDF8`):** A cool sky-cyan used strictly for informational metadata, verified culinary tags, or neighborhood location badges (e.g., Indiranagar, Koramangala) to prevent orange fatigue.
- **Surface Elevation Steps:**
  - Base Canvas / Scrim: `#0B111A`
  - Elevated Container / Cards: `#111A24`
  - Floating / Interactive Surfaces (inputs, hover overlays, dialogs): `#192330`
  - Active / Selected Container Fill: `#1E2D3D`
- **Borders & Separators:**
  - Subtle structural lines: `#233142`
  - Active / Focus boundaries: `#33465C`
- **Typography & Foreground:**
  - Headings / Key Metrics: `#F8FAFC`
  - Primary Body / High Emphasis: `#E2E8F0`
  - Secondary / Form Labels / Subtitles: `#94A3B8`
  - Tertiary / Captions / Counters: `#64748B`

## Typography
Plus Jakarta Sans delivers geometric clarity blended with warm, inviting curves, making it ideal for clean mobile interfaces and rich editorial headlines.

- **Weight Distinctions:** Headlines use bold (`700`) and semi-bold (`600`) to create instant hierarchy against dark backgrounds. Regular (`400`) is used across body copy to maintain open counters and high legibility.
- **Letter Spacing:** Tighter tracking (`-0.01em` to `-0.025em`) is applied to large sizes for a polished editorial lockup. Micro labels and metadata tags utilize wide tracking (`+0.025em` to `+0.06em`) in all-caps or small format to ensure scanning speed.
- **Contrast Ratios:** Pure white (`#F8FAFC`) is strictly paired with large display headlines. Body copy is softly stepped down to `#E2E8F0` and secondary details to `#94A3B8` to eliminate retina fatigue during extended low-light browsing sessions.

## Layout & Spacing
A fluid 12-column grid is utilized for desktop and tablet screens, shifting down to a single-column or 2-column card stack on mobile viewports.

- **Breakpoints:**
  - **Mobile:** `< 640px` (4-column layout, `1rem` margin, `1rem` gutters)
  - **Tablet:** `640px – 1024px` (8-column layout, `1.5rem` margin, `1.5rem` gutters)
  - **Desktop:** `> 1024px` (12-column layout max-width 1280px, `3rem` margins, `2rem` gutters)
- **Rhythm Rules:** All layout units and element spacings adhere to a 4px/8px incremental base. Internal card padding is consistently `1.25rem` (`space-lg`), while compact input elements utilize `0.75rem` (`space-md`). Vertical stacks prioritize content groupings through tight label-to-input gaps (`0.5rem`) and pronounced section boundaries (`2rem` to `3rem`).

## Elevation & Depth
In alignment with accessible dark-mode UI best practices, elevation avoids harsh drop-shadows that look murky against dark canvases. Depth is articulated through surface luminosity and hairline borders:

- **Surface Tiers:**
  - **Canvas (Layer 0):** `#0B111A` — Base background of the viewport.
  - **Cards & Surfaces (Layer 1):** `#111A24` — Framed by a continuous `1px` border of `#233142`.
  - **Input Fields & Insets (Layer 1.5):** `#0E1620` with a `1px` `#233142` border, generating inset tactile depth.
  - **Floating Menus, Dropdowns & Modals (Layer 2):** `#192330` with `1px solid #33465C` border and an ambient, low-opacity, diffused spread: `box-shadow: 0 12px 32px -4px rgba(0, 0, 0, 0.6)`.
- **Active State Highlights:** Active or hovered borders shift subtly from `#233142` to `#33465C` or `#F97316` (accent), without adding heavy glow filters.

## Shapes
The design system employs a soft, contemporary silhouette calibrated between technical precision and friendly warmth:

- Standard structural components (inputs, list rows, notification banners) use `rounded-lg` (`0.5rem`).
- Larger organizational cards, modal sheets, and hero recommendation containers use `rounded-xl` (`0.75rem`).
- Badges, status pills, category filter chips, and circular icon triggers use fully rounded pill geometry (`rounded-full` / `9999px`) to maintain distinctive visual separation from rectangular content modules.

## Components

### 1. Primary Buttons & Loading States
- **Default:** `#F97316` solid background with `#0B111A` heavy bold text (`label-lg`), `0.5rem` radius, padding `0.75rem 1.5rem`.
- **Hover/Active:** Smooth transition to `#FB923C`. Focus has a 2px `#F97316` ring with `2px` offset (`#0B111A`).
- **Loading State:** Disabled button with opacity preserved, text replaced or accompanied by a spinning geometric ring in `#0B111A`, preventing layout shift.

### 2. Form Inputs, Combos & Textareas
- **Text Inputs with Dropdown Suggestions:** Background `#0E1620`, border `1px solid #233142`, text `#F8FAFC`. Floating dropdown menu mounts at `#192330` with `#233142` separators; highlighted suggestions use `#1E2D3D` with orange text accents.
- **Dual Combo Inputs (e.g., Location + Cuisine):** Contained in a unified `#0E1620` bar split by a vertical `1px solid #233142` divider. Seamless tab flow between nested left and right segments.
- **Textareas with Counters:** Flexible text area with character counter (`0.75rem`, `#64748B`) anchored bottom-right. Exceeding capacity transitions counter text to `#F8FAFC` on `#EF4444`.

### 3. Segmented Selectors & Live Sliders
- **Segmented Selectors:** Recessed track (`#0E1620`, padding `4px`) hosting tabs. Active tab renders with `#192330` surface, `1px solid #233142`, and `#F8FAFC` text; inactive tabs render `#94A3B8`.
- **Live Rating Sliders:** Thin `4px` track (`#233142`), filled active bar in `#F97316`. Slider thumb has a `18px` circular `#F8FAFC` node with a centered `#F97316` core dot. Live score callout floats above in a `#192330` tooltip.

### 4. Status Pills, Rank Badges & Metadata Chips
- **Rank Badges:** High-contrast pill situated on card top-left (`#F97316` background, `#0B111A` text, `label-caps`).
- **Status Pills:** Open/Closed indicators. Open uses `#10B981` (10% alpha fill `#064E3B`, solid border, `#34D399` text).
- **Metadata Chips:** Pill-shaped, background `#192330`, border `1px solid #233142`, text `#94A3B8`, interactive hover brings border to `#33465C`.

### 5. Editorial Recommendation Cards
- Elevated `#111A24` container, `1px solid #233142` border, `rounded-xl` overflow hidden.
- Top section: 16:9 imagery paired with an absolute-positioned Rank Badge and favorite button.
- Body section: Title (`headline-sm`, `#F8FAFC`), neighborhood & price metadata (`body-sm`, `#94A3B8`).
- **'Why It Fits' Editorial Callout:** Inset card section styled with `#16202C` background, subtle dashed left border (`2px solid #F97316`), and curated excerpt in `#E2E8F0` (`body-sm`).

### 6. Notice Banners, Skeletons & Empty States
- **Notice Banners:** `#111A24` base with an accent left border (`3px solid #F97316`), icon, dismiss button, and `#E2E8F0` messaging.
- **Skeleton Loaders:** Base tone `#111A24` with a linear shimmer gradient traveling across `#192330` to `#111A24`.
- **Empty & Error States:** Centered slate vector icon with `#233142` geometric backdrop, `#F8FAFC` heading, `#94A3B8` supporting copy, and a secondary or primary action button.