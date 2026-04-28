"""
SaaS Pricing Intelligence Dashboard
====================================
Interactive Streamlit dashboard to visualize pricing data from the
Sales & Revenue SaaS sector.

Usage:
    streamlit run dashboard.py

Requirements:
    pip install streamlit pandas plotly

Note: Run scraper.py and classify.py first to generate pricing_data.csv
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
from pathlib import Path


# --- Page Config ---
st.set_page_config(
    page_title="SaaS Pricing Intelligence Tracker",
    page_icon="📊",
    layout="wide",
)


@st.cache_data
def load_data():
    """Load pricing data from CSV."""
    csv_path = "pricing_data.csv"
    if not Path(csv_path).exists():
        return None
    df = pd.read_csv(csv_path)
    return df


def load_json_data():
    """Load full JSON data for detailed views."""
    json_path = "pricing_data.json"
    if not Path(json_path).exists():
        return None
    with open(json_path) as f:
        return json.load(f)


def main():
    # --- Header ---
    st.title("📊 SaaS Pricing Intelligence Tracker")
    total_companies = "150+"
    st.markdown("**SaaS Pricing Intelligence** — Real-time pricing analysis across " + total_companies + " companies")
    st.divider()

    # Load data
    df = load_data()
    if df is None:
        st.error("No pricing data found. Run `scraper.py` then `classify.py` first.")
        st.code("python scraper.py\npython classify.py", language="bash")
        return

    # --- Sidebar Filters ---
    st.sidebar.header("Filters")

    if "sector" in df.columns:
        sectors = ["All"] + sorted(df["sector"].dropna().unique().tolist())
        selected_sector = st.sidebar.selectbox("Sector", sectors)
    else:
        selected_sector = "All"

    subsectors = ["All"] + sorted(df["subsector"].dropna().unique().tolist())
    selected_sub = st.sidebar.selectbox("Subsector", subsectors)

    pricing_models = ["All"] + sorted(df["pricing_model"].dropna().unique().tolist())
    selected_model = st.sidebar.selectbox("Pricing Model", pricing_models)

    show_ai_only = st.sidebar.checkbox("Only show companies with AI features")

    # Apply filters
    filtered = df.copy()
    if selected_sector != "All":
        filtered = filtered[filtered["sector"] == selected_sector]
        # Update subsector list based on selected sector
        subsectors = ["All"] + sorted(filtered["subsector"].dropna().unique().tolist())
    if selected_sub != "All":
        filtered = filtered[filtered["subsector"] == selected_sub]
    if selected_model != "All":
        filtered = filtered[filtered["pricing_model"] == selected_model]
    if show_ai_only:
        filtered = filtered[filtered["has_ai_features"] == True]

    # --- Key Metrics Row ---
    col1, col2, col3, col4, col5 = st.columns(5)

    unique_companies = filtered["company"].nunique()
    public_pricing_pct = (
        filtered.groupby("company")["has_public_pricing"]
        .first().mean() * 100
        if len(filtered) > 0 else 0
    )
    free_tier_pct = (
        filtered.groupby("company")["free_tier_exists"]
        .first().mean() * 100
        if len(filtered) > 0 else 0
    )
    ai_feature_pct = (
        filtered.groupby("company")["has_ai_features"]
        .first().mean() * 100
        if len(filtered) > 0 else 0
    )
    median_price = filtered["monthly_price"].dropna()
    median_price = median_price[median_price > 0].median() if len(median_price) > 0 else 0

    col1.metric("Companies", unique_companies)
    col2.metric("Public Pricing", f"{public_pricing_pct:.0f}%")
    col3.metric("Offer Free Tier", f"{free_tier_pct:.0f}%")
    col4.metric("AI Features", f"{ai_feature_pct:.0f}%")
    col5.metric("Median Price/mo", f"${median_price:,.0f}" if median_price else "N/A")

    st.divider()

    # --- Charts Row 1 ---
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.subheader("Pricing Models by Subcategory")
        if len(filtered) > 0:
            model_counts = (
                filtered.groupby(["subsector", "pricing_model"])["company"]
                .nunique()
                .reset_index()
                .rename(columns={"company": "count"})
            )
            fig = px.bar(
                model_counts,
                x="subsector",
                y="count",
                color="pricing_model",
                barmode="group",
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            fig.update_layout(
                xaxis_title="",
                yaxis_title="Number of Companies",
                legend_title="Pricing Model",
                height=400,
            )
            st.plotly_chart(fig, width="stretch")

    with chart_col2:
        st.subheader("Free Tier vs Enterprise-Only")
        if len(filtered) > 0:
            company_level = filtered.groupby("company").agg({
                "free_tier_exists": "first",
                "enterprise_contact_sales": "first",
                "subsector": "first",
            }).reset_index()

            tier_summary = pd.DataFrame({
                "Type": ["Free Tier Available", "Enterprise/Contact Sales", "Neither"],
                "Count": [
                    company_level["free_tier_exists"].sum(),
                    company_level["enterprise_contact_sales"].sum(),
                    len(company_level) - company_level["free_tier_exists"].sum()
                    - company_level["enterprise_contact_sales"].sum(),
                ]
            })
            tier_summary = tier_summary[tier_summary["Count"] > 0]

            fig = px.pie(
                tier_summary,
                values="Count",
                names="Type",
                color_discrete_sequence=px.colors.qualitative.Pastel,
                hole=0.4,
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, width="stretch")

    # --- Charts Row 2 ---
    chart_col3, chart_col4 = st.columns(2)

    with chart_col3:
        st.subheader("Where Companies Price Their Tiers")
        prices = filtered[
            (filtered["monthly_price"].notna())
            & (filtered["monthly_price"] > 0)
            & (filtered["monthly_price"] < 1000)
        ]
        if len(prices) > 0:
            # Bucket prices into ranges
            import numpy as np
            bins = [0, 25, 50, 75, 100, 150, 200, 300, 500, 1000]
            labels = ["$0-25", "$25-50", "$50-75", "$75-100", "$100-150",
                       "$150-200", "$200-300", "$300-500", "$500+"]
            prices = prices.copy()
            prices["price_bucket"] = pd.cut(
                prices["monthly_price"], bins=bins, labels=labels, right=True
            )

            # Count tiers per subsector per bucket
            bubble_df = (
                prices.groupby(["subsector", "price_bucket"], observed=False)
                .size()
                .reset_index(name="count")
            )
            # Drop zero-count rows
            bubble_df = bubble_df[bubble_df["count"] > 0]

            # Map bucket labels to numeric x positions for plotting
            bucket_positions = {label: i for i, label in enumerate(labels)}
            bubble_df["x_pos"] = bubble_df["price_bucket"].astype(str).map(bucket_positions)

            fig = px.scatter(
                bubble_df,
                x="price_bucket",
                y="subsector",
                size="count",
                color="subsector",
                size_max=45,
                color_discrete_sequence=px.colors.qualitative.Set2,
                hover_data={"count": True, "price_bucket": True, "subsector": True},
            )
            fig.update_layout(
                xaxis_title="Monthly Price Range",
                yaxis_title="",
                height=420,
                showlegend=False,
                xaxis=dict(categoryorder="array", categoryarray=labels),
            )
            fig.update_traces(
                hovertemplate=(
                    "<b>%{y}</b><br>"
                    "Price range: %{x}<br>"
                    "Tiers in this range: %{marker.size:,}"
                    "<extra></extra>"
                ),
            )
            st.plotly_chart(fig, width="stretch")

    with chart_col4:
        st.subheader("AI Features Adoption")
        if len(filtered) > 0:
            ai_by_sub = (
                filtered.groupby("subsector")
                .agg(
                    total=("company", "nunique"),
                    with_ai=("has_ai_features", lambda x: x.any()),
                )
                .reset_index()
            )
            # Recalculate properly
            ai_by_sub = (
                filtered.groupby(["subsector", "company"])["has_ai_features"]
                .first()
                .reset_index()
                .groupby("subsector")
                .agg(
                    total=("company", "count"),
                    with_ai=("has_ai_features", "sum"),
                )
                .reset_index()
            )
            ai_by_sub["pct"] = (ai_by_sub["with_ai"] / ai_by_sub["total"] * 100).round(1)

            fig = px.bar(
                ai_by_sub,
                x="subsector",
                y="pct",
                color_discrete_sequence=["#636EFA"],
                text="pct",
            )
            fig.update_layout(
                xaxis_title="",
                yaxis_title="% with AI Features",
                height=400,
                showlegend=False,
            )
            fig.update_traces(texttemplate="%{text}%", textposition="outside")
            st.plotly_chart(fig, width="stretch")

    st.divider()

    # --- Price Comparison Table ---
    st.subheader("Company Pricing Comparison")

    # Pivot: one row per company, show key tier prices
    if len(filtered) > 0:
        display_cols = [
            "company", "subsector", "pricing_model", "tier_name",
            "monthly_price", "annual_price_per_month", "price_unit",
            "free_tier_exists", "has_ai_features", "ai_in_pricing",
        ]
        available_cols = [c for c in display_cols if c in filtered.columns]
        display_df = filtered[available_cols].copy()

        # Format prices
        for col in ["monthly_price", "annual_price_per_month"]:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(
                    lambda x: f"${x:,.0f}" if pd.notna(x) and x > 0 else "—"
                )

        st.dataframe(
            display_df,
            width="stretch",
            height=500,
            hide_index=True,
        )

    st.divider()

    # --- AI Features Detail ---
    st.subheader("AI Features Mentioned")
    if len(filtered) > 0:
        ai_companies = filtered[
            (filtered["has_ai_features"] == True)
            & (filtered["ai_features_list"].notna())
            & (filtered["ai_features_list"] != "")
        ].groupby("company")["ai_features_list"].first().reset_index()

        if len(ai_companies) > 0:
            for _, row in ai_companies.iterrows():
                st.markdown(f"**{row['company']}**: {row['ai_features_list']}")
        else:
            st.info("No AI features detected in filtered companies.")

    # --- Footer ---
    st.divider()
    st.caption(
        f"Data last updated: {filtered['classified_at'].max() if 'classified_at' in filtered.columns else 'Unknown'} "
        f"| {unique_companies} companies tracked | Sales & Revenue Sector"
    )


if __name__ == "__main__":
    main()
