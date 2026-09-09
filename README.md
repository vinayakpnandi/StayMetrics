# 🏨 StayMetrics – Dynamic Pricing & Revenue Dashboard

StayMetrics is a portfolio project that demonstrates **Python, Pandas, Streamlit, SQL/SQLite and Plotly** through a business-oriented hotel/property revenue dashboard.

The project deliberately uses an **explainable rule-based pricing engine** instead of an advanced ML model.

## Features

- Upload property/listing data from CSV
- Occupancy-rate KPI
- Weekday vs weekend demand analysis
- Seasonal demand analysis
- Average Daily Rate (ADR)
- Revenue calculation
- Rule-based recommended price
- Interactive pricing assumptions
- Revenue sensitivity / what-if analysis
- "Why is my recommended price ₹X?" explanation
- SQLite persistence
- PostgreSQL-ready architecture

## CSV format

The uploaded CSV should contain:

`date, property_id, property_name, city, base_price, available_rooms, occupied_rooms, price`

See `data/sample_listings.csv`.

## Run locally

### 1. Create a virtual environment

Windows:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Start Streamlit

```bash
streamlit run app.py
```

Then open the local URL shown by Streamlit.

## PostgreSQL

The current dashboard uses SQLite for zero-configuration local persistence.

PostgreSQL can be added using SQLAlchemy with a connection string such as:

```text
postgresql+psycopg2://username:password@localhost:5432/staymetrics
```

A natural next step is to move the `save_to_sqlite()` and `load_from_sqlite()` functions into a small database layer using SQLAlchemy so the same app can switch between SQLite and PostgreSQL via an environment variable.

## Pricing logic

The recommendation combines:

- Base price
- Occupancy pressure
- Demand index
- Weekend premium
- Seasonal multiplier
- Minimum and maximum price guardrails

This makes the recommendation easy to explain to a recruiter or interviewer.

## Suggested interview explanation

> "I built a rule-based dynamic pricing engine because the objective was not to create a complex ML model. I wanted the recommendation to be transparent. The engine increases price when occupancy and demand are strong, adds a weekend/seasonal premium, and keeps the final price within business-defined limits. Streamlit lets a user change those assumptions and immediately see the revenue impact."

## Project structure

```text
StayMetrics/
├── app.py
├── requirements.txt
├── README.md
├── data/
│   └── sample_listings.csv
└── staymetrics.db   # created automatically after SQLite save
```
