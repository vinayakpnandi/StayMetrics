
import io
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="StayMetrics | Dynamic Pricing & Revenue Dashboard",
    page_icon="🏨",
    layout="wide",
)

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "staymetrics.db"

# -----------------------------
# Demo data + database helpers
# -----------------------------
@st.cache_data
def make_demo_data():
    dates = pd.date_range("2026-01-01", "2026-12-31", freq="D")
    properties = [
        ("SM001", "Urban Nest", "Bengaluru", 3200),
        ("SM002", "Lakeview Stay", "Udupi", 2800),
        ("SM003", "Heritage Rooms", "Mysuru", 2500),
        ("SM004", "Tech Park Suites", "Bengaluru", 4200),
    ]

    rows = []
    for pid, name, city, base_price in properties:
        for d in dates:
            weekend = d.dayofweek >= 5
            month = d.month
            seasonal = 1.0
            if month in [10, 11, 12]:
                seasonal = 1.18
            elif month in [4, 5, 6]:
                seasonal = 0.90

            demand = 0.68 * seasonal + (0.12 if weekend else -0.03)
            # Deterministic pseudo-pattern; no ML needed.
            demand += ((d.day * 7 + d.month * 3 + len(pid)) % 13 - 6) / 100
            demand = max(0.25, min(0.96, demand))

            booked = int(round(demand))
            occupied = booked == 1
            rows.append(
                {
                    "date": d,
                    "property_id": pid,
                    "property_name": name,
                    "city": city,
                    "base_price": base_price,
                    "available_rooms": 1,
                    "occupied_rooms": int(occupied),
                    "price": round(base_price * (1.0 + (0.08 if weekend else 0) + (seasonal - 1) * 0.35), 2),
                }
            )
    return pd.DataFrame(rows)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stays (
            date TEXT,
            property_id TEXT,
            property_name TEXT,
            city TEXT,
            base_price REAL,
            available_rooms INTEGER,
            occupied_rooms INTEGER,
            price REAL
        )
    """)
    conn.commit()
    return conn


def save_to_sqlite(df):
    conn = init_db()
    df.to_sql("stays", conn, if_exists="replace", index=False)
    conn.close()


def load_from_sqlite():
    conn = init_db()
    df = pd.read_sql_query("SELECT * FROM stays", conn)
    conn.close()
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


# -----------------------------
# Pricing engine
# -----------------------------
def calculate_metrics(df):
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"])
    out["weekday"] = out["date"].dt.day_name()
    out["day_type"] = out["date"].dt.dayofweek.map(
        lambda x: "Weekend" if x >= 5 else "Weekday"
    )
    out["month"] = out["date"].dt.month
    out["season"] = out["month"].map(
        lambda m: "Peak" if m in [10, 11, 12] else ("Off-Peak" if m in [4, 5, 6] else "Regular")
    )
    out["revenue"] = out["price"] * out["occupied_rooms"]
    return out


def pricing_recommendation(
    base_price,
    occupancy,
    demand_index,
    weekend,
    seasonal_multiplier,
    min_price,
    max_price,
    occupancy_weight,
    demand_weight,
):
    # Transparent rule-based pricing:
    # low occupancy/demand -> discount; high occupancy/demand -> premium.
    occupancy_factor = (occupancy - 0.50) * 2 * occupancy_weight
    demand_factor = (demand_index - 0.50) * 2 * demand_weight
    weekend_factor = 0.08 if weekend else 0.0

    multiplier = (
        1
        + occupancy_factor
        + demand_factor
        + weekend_factor
        + (seasonal_multiplier - 1) * 0.50
    )
    recommended = base_price * multiplier
    recommended = max(min_price, min(max_price, recommended))
    return round(recommended, 2), multiplier


def explain_price(
    base_price,
    occupancy,
    demand_index,
    weekend,
    seasonal_multiplier,
    recommended,
    min_price,
    max_price,
):
    reasons = []
    if occupancy >= 0.75:
        reasons.append(f"occupancy is high at {occupancy:.0%}, so the engine adds a premium")
    elif occupancy <= 0.40:
        reasons.append(f"occupancy is low at {occupancy:.0%}, so the engine applies a discount")
    else:
        reasons.append(f"occupancy is moderate at {occupancy:.0%}")

    if demand_index >= 0.70:
        reasons.append(f"demand is strong at {demand_index:.0%}")
    elif demand_index <= 0.40:
        reasons.append(f"demand is soft at {demand_index:.0%}")
    else:
        reasons.append(f"demand is balanced at {demand_index:.0%}")

    if weekend:
        reasons.append("weekend demand adds an 8% premium")

    if seasonal_multiplier > 1:
        reasons.append(f"peak-season uplift contributes to the price")
    elif seasonal_multiplier < 1:
        reasons.append("off-peak season pushes the price lower")

    capped = recommended <= min_price or recommended >= max_price
    cap_text = " The final value is also constrained by your configured price limits." if capped else ""

    return (
        f"**₹{recommended:,.0f}** is recommended from a base price of "
        f"**₹{base_price:,.0f}** because " + ", ".join(reasons) + "." + cap_text
    )


# -----------------------------
# UI
# -----------------------------
st.title("🏨 StayMetrics")
st.caption("Dynamic Pricing & Revenue Dashboard — rule-based pricing with transparent business logic")

with st.sidebar:
    st.header("1. Data")
    uploaded = st.file_uploader("Upload CSV", type=["csv"])

    use_demo = st.button("Load demo data", use_container_width=True)

    st.divider()
    st.header("2. Pricing assumptions")
    base_price = st.number_input("Base price (₹)", 500, 100000, 3500, step=100)
    min_price = st.number_input("Minimum price (₹)", 300, 100000, 1800, step=100)
    max_price = st.number_input("Maximum price (₹)", 500, 200000, 7000, step=100)
    occupancy_weight = st.slider("Occupancy impact", 0.0, 1.0, 0.45, 0.05)
    demand_weight = st.slider("Demand impact", 0.0, 1.0, 0.35, 0.05)
    weekend_premium = st.slider("Weekend premium", 0.0, 0.30, 0.08, 0.01)

if uploaded:
    raw = pd.read_csv(uploaded)
    source = "uploaded CSV"
elif use_demo or "data" not in st.session_state:
    raw = make_demo_data()
    source = "demo data"
else:
    raw = st.session_state["data"]
    source = "previous selection"

required = {
    "date", "property_id", "property_name", "city",
    "base_price", "available_rooms", "occupied_rooms", "price"
}
missing = required - set(raw.columns)

if missing:
    st.error("Missing required columns: " + ", ".join(sorted(missing)))
    st.info("Use the included `data/sample_listings.csv` as the template.")
    st.stop()

st.session_state["data"] = raw.copy()
df = calculate_metrics(raw)

# Allow weekend premium assumption to affect dashboard scenario price.
df["scenario_price"] = df["price"] * (1 + df["day_type"].eq("Weekend") * (weekend_premium - 0.08))
df["scenario_revenue"] = df["scenario_price"] * df["occupied_rooms"]

occupancy_rate = df["occupied_rooms"].sum() / max(df["available_rooms"].sum(), 1)
adr = df.loc[df["occupied_rooms"] > 0, "price"].mean()
revenue = df["revenue"].sum()
rooms = df["available_rooms"].sum()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Occupancy Rate", f"{occupancy_rate:.1%}")
c2.metric("ADR", f"₹{adr:,.0f}")
c3.metric("Revenue", f"₹{revenue:,.0f}")
c4.metric("Available Room Nights", f"{rooms:,}")

st.caption(f"Data source: {source} · {len(df):,} rows")

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📊 Overview", "📅 Demand", "🌦 Seasonality", "💰 Pricing Engine", "🗄 SQL Data"]
)

with tab1:
    left, right = st.columns(2)

    daily = df.groupby("date", as_index=False).agg(
        occupancy=("occupied_rooms", "mean"),
        revenue=("revenue", "sum"),
    )

    with left:
        fig = px.line(daily, x="date", y="occupancy", title="Daily Occupancy")
        fig.update_yaxes(tickformat=".0%", range=[0, 1])
        st.plotly_chart(fig, use_container_width=True)

    with right:
        fig = px.line(daily, x="date", y="revenue", title="Daily Revenue")
        st.plotly_chart(fig, use_container_width=True)

    city = (
        df.groupby("city", as_index=False)
        .agg(occupancy=("occupied_rooms", "mean"), revenue=("revenue", "sum"))
        .sort_values("revenue", ascending=False)
    )
    st.subheader("Property / city performance")
    st.dataframe(city, use_container_width=True, hide_index=True)

with tab2:
    demand = (
        df.groupby("day_type", as_index=False)
        .agg(
            occupancy=("occupied_rooms", "mean"),
            revenue=("revenue", "sum"),
            adr=("price", lambda x: x[df.loc[x.index, "occupied_rooms"] > 0].mean()),
        )
    )

    col1, col2 = st.columns(2)
    with col1:
        fig = px.bar(demand, x="day_type", y="occupancy", title="Weekday vs Weekend Occupancy")
        fig.update_yaxes(tickformat=".0%", range=[0, 1])
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = px.bar(demand, x="day_type", y="revenue", title="Weekday vs Weekend Revenue")
        st.plotly_chart(fig, use_container_width=True)

    st.dataframe(demand, use_container_width=True, hide_index=True)

with tab3:
    season = (
        df.groupby("season", as_index=False)
        .agg(
            occupancy=("occupied_rooms", "mean"),
            revenue=("revenue", "sum"),
            adr=("price", lambda x: x[df.loc[x.index, "occupied_rooms"] > 0].mean()),
        )
    )

    fig = px.bar(season, x="season", y="occupancy", title="Seasonal Occupancy")
    fig.update_yaxes(tickformat=".0%", range=[0, 1])
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(season, use_container_width=True, hide_index=True)

with tab4:
    st.subheader("Rule-based recommended price")

    a, b, c = st.columns(3)
    sim_occupancy = a.slider("Simulated occupancy", 0.0, 1.0, float(occupancy_rate), 0.01)
    sim_demand = b.slider("Demand index", 0.0, 1.0, 0.65, 0.01)
    sim_weekend = c.toggle("Weekend", value=True)

    seasonal_options = {"Off-Peak": 0.90, "Regular": 1.00, "Peak": 1.18}
    sim_season = st.selectbox("Season", list(seasonal_options))
    seasonal_multiplier = seasonal_options[sim_season]

    recommended, multiplier = pricing_recommendation(
        base_price,
        sim_occupancy,
        sim_demand,
        sim_weekend,
        seasonal_multiplier,
        min_price,
        max_price,
        occupancy_weight,
        demand_weight,
    )

    # Use user's assumption instead of hard-coded 8% when weekend is selected.
    if sim_weekend:
        adjusted = base_price * (multiplier - 0.08 + weekend_premium)
        recommended = round(max(min_price, min(max_price, adjusted)), 2)

    st.metric("Recommended Price", f"₹{recommended:,.0f}", f"{(recommended / base_price - 1):+.1%} vs base")

    st.markdown(
        explain_price(
            base_price,
            sim_occupancy,
            sim_demand,
            sim_weekend,
            seasonal_multiplier,
            recommended,
            min_price,
            max_price,
        )
    )

    st.divider()
    st.subheader("Revenue sensitivity")
    scenario_occupancy = st.slider("Scenario occupancy", 0.1, 1.0, 0.70, 0.01)
    nights = st.number_input("Room nights in scenario", 1, 10000, 100, 1)

    baseline_rev = base_price * scenario_occupancy * nights
    dynamic_rev = recommended * scenario_occupancy * nights
    delta = dynamic_rev - baseline_rev

    r1, r2, r3 = st.columns(3)
    r1.metric("Baseline Revenue", f"₹{baseline_rev:,.0f}")
    r2.metric("Dynamic Revenue", f"₹{dynamic_rev:,.0f}", f"₹{delta:,.0f}")
    r3.metric("Revenue Change", f"{delta / baseline_rev:.1%}")

    chart_df = pd.DataFrame({
        "Strategy": ["Baseline", "Dynamic"],
        "Revenue": [baseline_rev, dynamic_rev],
    })
    fig = px.bar(chart_df, x="Strategy", y="Revenue", title="Scenario Revenue Comparison")
    st.plotly_chart(fig, use_container_width=True)

with tab5:
    st.subheader("SQLite storage")
    st.write("The dashboard can persist uploaded/demo data into a local SQLite database.")

    if st.button("Save current data to SQLite"):
        save_to_sqlite(raw)
        st.success(f"Saved {len(raw):,} rows to {DB_PATH.name}")

    if st.button("Load from SQLite"):
        stored = load_from_sqlite()
        if stored.empty:
            st.warning("No data found in SQLite yet.")
        else:
            st.session_state["data"] = stored
            st.success(f"Loaded {len(stored):,} rows. Reloading dashboard...")
            st.rerun()

    st.code(
        """CREATE TABLE stays (
    date TEXT,
    property_id TEXT,
    property_name TEXT,
    city TEXT,
    base_price REAL,
    available_rooms INTEGER,
    occupied_rooms INTEGER,
    price REAL
);""",
        language="sql",
    )

st.divider()
st.caption("StayMetrics is intentionally explainable: no black-box ML is required for the pricing recommendation.")
