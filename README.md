# MacroMatch



## What I built and who for

abc

## The data

**Source:** USDA FoodData Central

**API documentation:** [https://fdc.nal.usda.gov/api-guide/](https://fdc.nal.usda.gov/api-guide/)

**Licence:** CC0 1.0 Universal (Public Domain)

The project will initially use two FoodData Central datasets:

- Foundation Foods
- SR Legacy

### Exploratory API audit

An initial investigation sampled 156 USDA food records
across Foundation Foods and SR Legacy.

The audit found:
- 96.8% completeness for core macros.
- 73.7% completeness when including fibre.
- Different energy calculation definitions.
- Missing nutritional measurements and anomalous values.
- Ambiguous search results and overlapping food descriptions.

These findings inform the data cleaning, modelling and
validation requirements for MacroMatch.

[Read the full data audit](docs/data_audit.md)

[View the audit code and results](audits/usda/)

## How it works

**Planned architecture:**

1. **Extract:** Retrieve nutritional data using Python and the USDA API.
2. **Preserve:** Store the original API responses for reproducibility.
3. **Transform:** Use SQL and DuckDB to clean, standardise and model the data.
4. **Validate:** Detect missing, inconsistent and anomalous nutritional values.
5. **Curate:** Produce reliable, structured nutritional datasets.
6. **Analyse:** Calculate goal-based suitability scores and nutritional comparisons.
7. **Present:** Provide an interactive Streamlit interface.

Development is organised into incremental milestones, with individual features added and tested progressively.

## How to run it

The current repository contains the initial project structure and environment verification tests.

**Requirements:** Python 3.10 or newer.

Clone the repository and navigate to its directory.

Create a virtual environment:

```powershell
py -3 -m venv .venv
```

Install the dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Run the tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

The full data pipeline and application will be introduced in later milestones.

## What I would do next

The next development milestones will:

- Document the exploratory API audit and its findings.
- Implement a configurable USDA data extraction process.
- Preserve raw API responses and load them into DuckDB.
- Develop SQL staging and curated models.
- Implement data-quality validation and ingredient classification.
- Build the recommendation and comparison functionality.
- Create the Streamlit interface.
- Introduce end-to-end testing and continuous integration.

## Where AI helped

abc

**Data attribution:** Nutritional information sourced from USDA FoodData Central, U.S. Department of Agriculture, Agricultural Research Service. The USDA data is available under CC0 1.0 Universal.
