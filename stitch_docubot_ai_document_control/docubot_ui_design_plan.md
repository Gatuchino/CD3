# DocuBot UI Design Specification

## Module Overview
DocuBot is the AI Document Control module for Aurenza Group, specializing in mining, construction, and EPC/EPCM projects. It focuses on converting complex contractual and technical documents into actionable, queryable data with total traceability.

## Visual Identity
- **Tone:** Professional, technical, reliable, "mining-industrial executive".
- **Aesthetic:** Architectural and sharp (0px border radius).
- **Core Palette:** 
    - `#000615` (Deep Blue) for headers, primary text, and depth.
    - `#835410` (Executive Copper) for primary brand accents and critical alerts.
    - `#F8F9FF` (Mist White) for page backgrounds.
    - `#4491A0` (Technical Teal) for processing states and confidence indicators.

## Screen List
1. **Dashboard:** Executive summary with KPI cards (total documents, OCR progress, active alerts).
2. **Semantic Search:** "Copilot" style interface. Prominent search bar with semantic autocomplete. Results showing document source, revision, and highlighted snippets.
3. **Document Viewer:** Split view with document preview on the left and metadata/AI-extracted obligations on the right. Highlighted relevant fragments.
4. **Document Uploader:** Drag-and-drop zone with real-time OCR progress bars and AI-suggested classifications.
5. **Alerts Panel:** Critical deadlines, unanswered RFIs, and detected contractual inconsistencies.
6. **Query History:** Auditable log of user-IA interactions.

## Key UI Components
- **Project Sidebar:** Hierarchical tree of projects and document types.
- **RAG Confidence Badge:** Circular or linear progress indicating AI certainty.
- **Version Timeline:** Vertical stepper showing document revisions.
- **Traceability Link:** Explicit citation format [Doc Code | Rev.N | Page X].
