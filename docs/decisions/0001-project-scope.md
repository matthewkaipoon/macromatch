# Decision 0001: Initial project scope and architecture

Status: Accepted

## Context

MacroMatch is being developed as a new data engineering
project for The Data School application.

The main evaluation priority is the transformation
of raw API data into clean, reliable, well-modelled
information.

## Decisions

1. Use USDA FoodData Central as the primary API.
2. Initially focus on Foundation Foods and SR Legacy.
3. Use Python for API extraction and orchestration.
4. Use DuckDB and SQL for data transformation.
5. Preserve original API responses in the repository.
6. Build a lightweight Streamlit application.
7. Separate data preparation from recommendation logic.
8. Use transparent, deterministic nutritional scoring.
9. Avoid user accounts and meal planning in version one.

## Rationale

USDA provides free, publicly reusable nutritional data.

The initial API audit identified meaningful opportunities
for missing-value handling, source-aware nutrient
standardisation and ingredient classification.

DuckDB allows the entire pipeline to run locally without
requiring a paid database or cloud infrastructure.

## Trade-offs

- The initial dataset will contain a limited food catalogue.
- The application will not cover all UK supermarket products.
- Food classification may require manually reviewed mappings.
- Nutritional suitability scores are decision aids,
  not clinical dietary recommendations.

## Future review

Reassess these decisions if later data-quality tests
identify significant problems with coverage or comparability.