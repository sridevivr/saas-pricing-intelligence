"""
SaaS Pricing Intelligence Dashboard
====================================
Interactive Streamlit dashboard to visualize pricing data and
track pricing changes over time.

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


@st.cache_data
def load_changes():
    """Load pricing changes from CSV."""
    csv_path = "pricing_changes.csv"
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
    st.markdown("**SaaS Pricing Intelligence** — Real-time pricing analysis across 150+ companies")
    st.divider()

    # Load data
    df = load_data()
    if df is None:
        st.error("No pricing data found. Run `scraper.py` then `classify.py` first.")
        st.code("python scraper.py\npython classify.py", language="bash")
        return

    changes_df = load_changes()

    # --- Tabs ---
    tab_pricing, tab_changes = st.tabs(["Current Pricing", "Pricing Changes"])

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
        subsectors = ["All"] + sorted(filtered["subsector"].dropna().unique().tolist())
    if selected_sub != "All":
        filtered = filtered[filtered["subsector"] == selected_sub]
    if selected_model != "All":
        filtered = filtered[filtered["pricing_model"] == selected_model]
    if show_ai_only:
        filtered = filtered[filtered["has_ai_features"] == True]

    # ============================================================
    # TAB 1: CURRENT PRICING
    # ============================================================
    with tab_pricing:

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
            st.subheader("Pricing Models by Subsector")
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
                import numpy as np
                bins = [0, 25, 50, 75, 100, 150, 200, 300, 500, 1000]
                labels = ["$0-25", "$25-50", "$50-75", "$75-100", "$100-150",
                           "$150-200", "$200-300", "$300-500", "$500+"]
                prices = prices.copy()
                prices["price_bucket"] = pd.cut(
                    prices["monthly_price"], bins=bins, labels=labels, right=True
                )

                bubble_df = (
                    prices.groupby(["subsector", "price_bucket"], observed=False)
                    .size()
                    .reset_index(name="count")
                )
                bubble_df = bubble_df[bubble_df["count"] > 0]

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

        if len(filtered) > 0:
            display_cols = [
                "company", "subsector", "pricing_model", "tier_name",
                "monthly_price", "annual_price_per_month", "price_unit",
                "free_tier_exists", "has_ai_features", "ai_in_pricing",
            ]
            available_cols = [c for c in display_cols if c in filtered.columns]
            display_df = filtered[available_cols].copy()

            for col in ["monthly_price", "annual_price_per_month"]:
                if col in display_df.columns:
                    display_df[col] = display_df[col].apply(
                        lambda x: f"${x:,.0f}" if pd.notna(x) and x > 0 else "---"
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

    # ============================================================
    # TAB 2: PRICING CHANGES
    # ============================================================
    with tab_changes:

        if changes_df is None or len(changes_df) == 0:
            st.info(
                "No pricing changes detected yet. "
                "Run the scraper at least twice (e.g. weekly), then run "
                "`python compare.py` to detect changes between snapshots."
            )
        else:
            # --- Change Summary Metrics ---
            ch_col1, ch_col2, ch_col3, ch_col4 = st.columns(4)

            total_changes = len(changes_df)
            companies_changed = changes_df["company"].nunique()
            snapshots = ""
            if "old_snapshot" in changes_df.columns and "new_snapshot" in changes_df.columns:
                old_snap = changes_df["old_snapshot"].iloc[0]
                new_snap = changes_df["new_snapshot"].iloc[0]
                snapshots = f"{old_snap} to {new_snap}"

            # Count by type
            type_counts = changes_df["type"].value_counts()
            price_increases = type_counts.get("price_increase", 0)
            price_decreases = type_counts.get("price_decrease", 0)

            ch_col1.metric("Total Changes", total_changes)
            ch_col2.metric("Companies Changed", companies_changed)
            ch_col3.metric("Price Increases", price_increases)
            ch_col4.metric("Price Decreases", price_decreases)

            if snapshots:
                st.caption(f"Comparing snapshots: **{snapshots}**")

            st.divider()

            # --- Changes by Type Chart ---
            ch_chart1, ch_chart2 = st.columns(2)

            with ch_chart1:
                st.subheader("Changes by Type")
                type_df = type_counts.reset_index()
                type_df.columns = ["Change Type", "Count"]
                type_df["Change Type"] = type_df["Change Type"].str.replace("_", " ").str.title()
                type_df = type_df.sort_values("Count", ascending=True)

                fig = px.bar(
                    type_df,
                    x="Count",
                    y="Change Type",
                    orientation="h",
                    color_discrete_sequence=["#636EFA"],
                )
                fig.update_layout(
                    xaxis_title="Number of Changes",
                    yaxis_title="",
                    height=400,
                    showlegend=False,
                )
                st.plotly_chart(fig, width="stretch")

            with ch_chart2:
                st.subheader("Most Active Companies")
                company_counts = (
                    changes_df["company"]
                    .value_counts()
                    .head(15)
                    .reset_index()
                )
                company_counts.columns = ["Company", "Changes"]
                company_counts = company_counts.sort_values("Changes", ascending=True)

                fig = px.bar(
                    company_counts,
                    x="Changes",
                    y="Company",
                    orientation="h",
                    color_discrete_sequence=["#EF553B"],
                )
                fig.update_layout(
                    xaxis_title="Number of Changes",
                    yaxis_title="",
                    height=400,
                    showlegend=False,
                )
                st.plotly_chart(fig, width="stretch")

            st.divider()

            # --- Key Signals ---
            st.subheader("Key Pricing Signals")

            signal_col1, signal_col2, signal_col3 = st.columns(3)

            with signal_col1:
                st.markdown("**Free Tier Changes**")
                free_added = changes_df[changes_df["type"] == "free_tier_added"]
                free_removed = changes_df[changes_df["type"] == "free_tier_removed"]
                if len(free_added) > 0:
                    st.markdown("Added free tier:")
                    for _, row in free_added.iterrows():
                        st.markdown(f"- {row['company']}")
                if len(free_removed) > 0:
                    st.markdown("Removed free tier:")
                    for _, row in free_removed.iterrows():
                        st.markdown(f"- {row['company']}")
                if len(free_added) == 0 and len(free_removed) == 0:
                    st.markdown("No free tier changes")

            with signal_col2:
                st.markdown("**Pricing Model Shifts**")
                model_changes = changes_df[changes_df["type"] == "model_change"]
                if len(model_changes) > 0:
                    for _, row in model_changes.iterrows():
                        st.markdown(f"- {row['company']}: {row['detail']}")
                else:
                    st.markdown("No pricing model changes")

            with signal_col3:
                st.markdown("**Price Movements**")
                price_ups = changes_df[changes_df["type"] == "price_increase"]
                price_downs = changes_df[changes_df["type"] == "price_decrease"]
                if len(price_ups) > 0:
                    st.markdown("Price increases:")
                    for _, row in price_ups.iterrows():
                        st.markdown(f"- {row['company']}: {row['detail']}")
                if len(price_downs) > 0:
                    st.markdown("Price decreases:")
                    for _, row in price_downs.iterrows():
                        st.markdown(f"- {row['company']}: {row['detail']}")
                if len(price_ups) == 0 and len(price_downs) == 0:
                    st.markdown("No price movements")

            st.divider()

            # --- AI Feature Changes ---
            st.subheader("AI Feature Changes")
            ai_changes = changes_df[
                changes_df["type"].isin(["ai_feature_added", "ai_feature_removed"])
            ]
            if len(ai_changes) > 0:
                ai_added = ai_changes[ai_changes["type"] == "ai_feature_added"]
                ai_removed = ai_changes[ai_changes["type"] == "ai_feature_removed"]

                ai_summary = st.columns(2)
                with ai_summary[0]:
                    st.markdown(f"**AI Features Added** ({len(ai_added)} changes)")
                    for _, row in ai_added.head(20).iterrows():
                        st.markdown(f"- **{row['company']}**: {row['detail']}")
                    if len(ai_added) > 20:
                        st.caption(f"...and {len(ai_added) - 20} more")

                with ai_summary[1]:
                    st.markdown(f"**AI Features Removed/Renamed** ({len(ai_removed)} changes)")
                    for _, row in ai_removed.head(20).iterrows():
                        st.markdown(f"- **{row['company']}**: {row['detail']}")
                    if len(ai_removed) > 20:
                        st.caption(f"...and {len(ai_removed) - 20} more")
            else:
                st.info("No AI feature changes detected.")

            st.divider()

            # --- Full Changes Table ---
            st.subheader("All Changes")
            display_changes = changes_df.copy()
            display_cols = ["company", "type", "detail", "old_value", "new_value"]
            if "strategic_category" in display_changes.columns:
                display_cols.append("strategic_category")
            available_cols = [c for c in display_cols if c in display_changes.columns]

            st.dataframe(
                display_changes[available_cols],
                width="stretch",
                height=500,
                hide_index=True,
            )

    # --- Footer ---
    st.divider()
    unique_companies = filtered["company"].nunique()
    st.caption(
        f"Data last updated: {filtered['classified_at'].max() if 'classified_at' in filtered.columns else 'Unknown'} "
        f"| {unique_companies} companies tracked"
    )


if __name__ == "__main__":
    main()
