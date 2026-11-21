# FitPilot design system

## Product

FitPilot is a consumer wellness app with an Advanced reviewer console for demonstrating its multi-agent planning architecture. Primary user pages are calm and simple; Advanced can be denser and more operational while remaining part of the same product.

## Brand

- Calm, credible, lightweight wellness—not clinical and not “AI neon.”
- Use DM Sans only.
- Emerald `#09815b` is the single primary action/accent.
- Ink `#17241e`, muted `#61716a`, line `#e3e9e5`, canvas `#f8faf9`, surface white.
- Avoid gradients, purple/blue AI styling, glassmorphism, oversized empty cards, and excessive rounded containers.

## Layout

- Preserve the existing 248px sidebar and 65px top bar.
- Advanced page should use a centered max-width around 1180–1240px.
- Prefer a compact command-center layout:
  - concise page header with reviewer badge and one-line explanation
  - two-column main area at desktop: specialist selector/composer on the left, result/empty state on the right
  - compact recent-runs list or table below
  - architecture explanation last and collapsed
- On mobile, stack composer, result, history, then architecture.

## Components

- Cards: white, 1px border, 14–16px radius, subtle or no shadow.
- Buttons: 42–44px height; solid emerald only for the current primary action.
- Inputs: soft `#f8faf9` fill, 1px border, 10–12px radius.
- Status/source pills: compact, neutral backgrounds; green only for completed/healthy.
- Disclosures: clear chevron, 48px minimum row, no nested card-on-card styling.
- Result view: readable hierarchy for nested data; avoid raw JSON appearance.

## Advanced page content

- Title: “Advanced”
- Supporting label: “Reviewer tools”
- Primary task: choose one specialist, add optional context, run it, inspect the response.
- Secondary task: inspect recent runs.
- Tertiary task: understand the workflow architecture.
- Do not include model connection settings.

## Motion and accessibility

- 150–200ms color/border transitions only.
- Respect reduced motion.
- Strong keyboard focus ring using emerald.
- Minimum 44px interactive targets where practical.
- Maintain readable contrast and explicit status text.
