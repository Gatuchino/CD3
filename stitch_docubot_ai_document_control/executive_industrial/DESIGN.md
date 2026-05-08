---
name: Executive Industrial
colors:
  surface: '#f8f9ff'
  surface-dim: '#d8dae0'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f3f9'
  surface-container: '#eceef3'
  surface-container-high: '#e7e8ee'
  surface-container-highest: '#e1e2e8'
  on-surface: '#191c20'
  on-surface-variant: '#45474c'
  inverse-surface: '#2e3135'
  inverse-on-surface: '#eff0f6'
  outline: '#75777d'
  outline-variant: '#c5c6cd'
  surface-tint: '#555f71'
  primary: '#000000'
  on-primary: '#ffffff'
  primary-container: '#121c2c'
  on-primary-container: '#7a8498'
  inverse-primary: '#bdc7dd'
  secondary: '#835410'
  on-secondary: '#ffffff'
  secondary-container: '#fdbd71'
  on-secondary-container: '#774a04'
  tertiary: '#000000'
  on-tertiary: '#ffffff'
  tertiary-container: '#001f25'
  on-tertiary-container: '#418e9d'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d9e3f9'
  primary-fixed-dim: '#bdc7dd'
  on-primary-fixed: '#121c2c'
  on-primary-fixed-variant: '#3d4759'
  secondary-fixed: '#ffddb9'
  secondary-fixed-dim: '#faba6f'
  on-secondary-fixed: '#2b1700'
  on-secondary-fixed-variant: '#663e00'
  tertiary-fixed: '#a3eeff'
  tertiary-fixed-dim: '#87d2e2'
  on-tertiary-fixed: '#001f25'
  on-tertiary-fixed-variant: '#004e5a'
  background: '#f8f9ff'
  on-background: '#191c20'
  surface-variant: '#e1e2e8'
typography:
  h1:
    fontFamily: Noto Serif
    fontSize: 40px
    fontWeight: '700'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  h2:
    fontFamily: Noto Serif
    fontSize: 32px
    fontWeight: '600'
    lineHeight: '1.3'
    letterSpacing: -0.01em
  h3:
    fontFamily: Noto Serif
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.4'
    letterSpacing: '0'
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.6'
    letterSpacing: '0'
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.5'
    letterSpacing: '0'
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.5'
    letterSpacing: '0'
  label-caps:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '700'
    lineHeight: '1'
    letterSpacing: 0.1em
  mono:
    fontFamily: monospace
    fontSize: 13px
    fontWeight: '400'
    lineHeight: '1.5'
    letterSpacing: '0'
spacing:
  unit: 8px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 40px
  gutter: 16px
  margin: 32px
---

## Brand & Style

The brand personality for this design system is defined by "Brutalist-executive" logic—a synthesis of high-level administrative authority and the raw, structural integrity of the mining and construction sectors. It evokes a sense of architectural permanence and technical precision. 

The aesthetic rejects the softness of consumer SaaS in favor of sharp 0px corners, high-contrast borders, and clear hierarchy. It is designed to feel like an official instrument: reliable, uncompromising, and highly structured. The interface should feel like an interactive blueprint or a high-end technical ledger, providing users with a sense of absolute control over complex document ecosystems.

## Colors

The palette is rooted in a "Deep Midnight Blue" that provides a heavy, grounding foundation. This is contrasted by "Mist White" backgrounds to maintain executive clarity and prevent visual fatigue during long periods of document review.

Accents are used with industrial intent:
- **Executive Copper (#835410)**: Used for warnings, high-priority highlights, and interactive accents that suggest value and urgency.
- **Technical Teal (#4491A0)**: Used for success states and secondary actions, offering a calm, clinical contrast to the darker primary tones.
- **Borders**: Standard UI borders should use a 1px solid stroke of the Primary color at 15-20% opacity to maintain the "sharp line" aesthetic without overwhelming the content.

## Typography

This design system employs a sophisticated typographic pairing to balance editorial authority with technical utility.

**Noto Serif** is reserved for headings and document titles. It brings a "Newspaper of Record" feel to the interface, signaling that the information presented is final and authoritative.

**Inter** handles all functional UI elements, data grids, and body copy. Its neutral, systematic nature ensures high readability for complex technical specs and document metadata. 

Use **Label-Caps** for category headers and table column titles to evoke the look of stamped industrial crates or technical documentation folders.

## Layout & Spacing

The layout philosophy follows a rigid, 8px-based grid system to reinforce the brutalist aesthetic. All components must align to this grid to ensure mathematical precision.

- **Grid Model**: A 12-column fluid grid is used for the main content area, while the sidebar remains fixed at 280px.
- **Rhythm**: Use `16px` (md) for internal component padding and `24px` (lg) for spacing between distinct sections or cards.
- **Tightness**: For data-heavy views (like the project tree), reduce vertical padding to `8px` (sm) to maximize information density.

## Elevation & Depth

In alignment with the "Brutalist-executive" style, depth is created through **tonal layering** and **bold borders** rather than soft, ambient shadows.

1.  **Level 0 (Background)**: Mist White (#F8F9FF).
2.  **Level 1 (Surface)**: Pure White cards and panels. Separation is achieved through a 1px solid border (#000615 at 10% opacity).
3.  **Level 2 (Active/Floating)**: Elements that require focus use a "Hard Shadow"—a 2px or 4px offset with 100% opacity in a light grey or the primary color at very low alpha, creating a "lifted paper" effect without blurring the edges.

Avoid all blurs. Depth is a matter of stacking and structural outlines, never atmospheric gradients.

## Shapes

The shape language of this design system is absolute: **0px border-radius**. 

Every element—buttons, cards, input fields, and badges—must have sharp, right-angled corners. This choice reflects the industrial nature of the mining and construction sectors, mimicking the precision of cut steel and architectural beams. To provide visual variety, use varying stroke weights (1px to 2px) rather than rounding corners.

## Components

### Sidebar (Project Tree)
The sidebar utilizes a hierarchical tree structure with sharp vertical guide lines to indicate nesting levels. Folders use the Primary color when active; text remains secondary when inactive.

### Buttons
- **Primary**: Solid Deep Midnight Blue (#000615) with white Inter text (Bold). 0px radius.
- **Secondary**: 1px solid Deep Midnight Blue border, no fill.
- **Action**: Use Technical Teal for "Upload" or "Approve" actions.

### Cards
Cards must have a white surface, 0px radius, and a 1px border (#000615 at 10%). For "Executive" summaries, a 4px top-border in Executive Copper (#835410) may be added to indicate priority.

### Badges & RAG Indicators
- **Confidence Indicators**: Small rectangular blocks. Teal (High), Copper (Medium), and a muted Slate (Low). No icons; use the **Label-Caps** typography style.
- **Status Labels**: Filled rectangles with white text.

### Timeline (Version History)
A vertical 2px solid line in Primary color. Version nodes are solid squares (not circles). Each entry features a Noto Serif timestamp and an Inter-based changelog description.

### Input Fields
Strict rectangular boxes with a 1px border. On focus, the border weight increases to 2px in Executive Copper. No glowing effects.