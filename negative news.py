import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
from typing import List

st.set_page_config(page_title="PAPG Negative Mentions Dashboard", page_icon=":bar_chart:", layout="wide")

# --- Configuration ---
COMPANIES = ["Juspay", "Razorpay", "Cashfree", "PayU"]
SOURCES = ["X (Twitter)", "LinkedIn", "News", "Forums", "Blogs"]
NEGATIVE_KEYWORDS = [
    "scam", "fraud", "ripoff", "complaint", "disappointed", "bad", "failure",
    "charges", "overcharge", "refund", "not working", "downtime", "issues",
    "bharosa", "angry", "hate", "problem", "breach", "error"
]

# --- Helper functions ---
@st.cache_data
def load_sample_data(num_rows: int = 200):
    import random
    base_date = datetime.today()
    rows = []
    for i in range(num_rows):
        company = random.choice(COMPANIES)
        source = random.choice(SOURCES)
        days_ago = random.randint(0, 365 * 5)
        date = (base_date - timedelta(days=days_ago)).date()
        if random.random() < 0.5:
            kw = random.choice(NEGATIVE_KEYWORDS)
            text = f"This is a user rant about {company}: {kw} encountered while using their payments." 
            score = - (0.2 + random.random() * 0.8)
        else:
            text = f"User mentions {company} in passing — neutral comment."
            score = 0.0 + random.random() * 0.2
        link = f"https://example.com/post/{i}"
        rows.append({"company": company, "source": source, "date": pd.to_datetime(date), "text": text, "link": link, "score": score})
    return pd.DataFrame(rows)


def simple_sentiment_score(text: str) -> float:
    text_l = text.lower()
    neg_hits = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text_l)
    if neg_hits == 0:
        return 0.0
    score = - min(1.0, 0.2 * neg_hits)
    return score

# --- UI: Sidebar Filters ---
st.sidebar.header("Filters")
use_sample = st.sidebar.checkbox("Use sample demo data", value=True)
uploaded_file = st.sidebar.file_uploader("Or upload a CSV (company,source,date,text,link) ", type=["csv", "xlsx"]) 

selected_companies = st.sidebar.multiselect("Companies", options=COMPANIES, default=COMPANIES)
selected_sources = st.sidebar.multiselect("Sources", options=SOURCES, default=SOURCES)

end_date = datetime.today().date()
start_date = st.sidebar.date_input("Start date", value=end_date - timedelta(days=365*5), min_value=end_date - timedelta(days=365*10), max_value=end_date)
end_date = st.sidebar.date_input("End date", value=end_date, min_value=start_date, max_value=datetime.today().date())

negative_only = st.sidebar.checkbox("Show negative mentions only", value=True)
min_score = st.sidebar.slider("Minimum (<=) sentiment score (negative scale)", min_value=-1.0, max_value=0.5, value=-1.0, step=0.05)

st.sidebar.markdown("---")
st.sidebar.markdown("**Notes**:\n- LinkedIn/X scraping requires API access and adherence to ToS.\n- Upload exported CSVs from your archival sources or integrate APIs to populate data.")

# --- Data Loading ---
if use_sample and uploaded_file is None:
    df = load_sample_data(500)
else:
    try:
        if uploaded_file is not None:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file, parse_dates=["date"]) 
            else:
                df = pd.read_excel(uploaded_file, parse_dates=["date"]) 
        else:
            df = load_sample_data(200)
    except Exception as e:
        st.error(f"Failed to load file: {e}")
        st.stop()

required_cols = {"company", "source", "date", "text", "link"}
if not required_cols.issubset(set(df.columns)):
    st.warning("Uploaded data missing required columns. Showing sample data instead.")
    df = load_sample_data(200)

if "score" not in df.columns:
    df["score"] = df["text"].astype(str).apply(simple_sentiment_score)

df["date"] = pd.to_datetime(df["date"]).dt.date

# --- Filtering ---
mask = (
    (df["company"].isin(selected_companies)) &
    (df["source"].isin(selected_sources)) &
    (df["date"] >= start_date) &
    (df["date"] <= end_date)
)

if negative_only:
    mask &= (df["score"] <= min_score)

filtered = df[mask].sort_values(by="date", ascending=False)

# --- Pagination controls ---
st.header("Negative Mentions Feed")
col1, col2 = st.columns([3, 1])

with col1:
    st.subheader(f"Showing {len(filtered)} mentions")
    page_size = st.number_input("Items per page", min_value=5, max_value=50, value=10)
    total_pages = max(1, (len(filtered) + page_size - 1) // page_size)

    # Session state for page tracking
    if "page" not in st.session_state:
        st.session_state.page = 1

    col_nav1, col_nav2, col_nav3 = st.columns([1,2,1])
    with col_nav1:
        if st.button("⬅️ Previous", disabled=st.session_state.page <= 1):
            st.session_state.page -= 1
    with col_nav2:
        st.write(f"Page {st.session_state.page} of {total_pages}")
    with col_nav3:
        if st.button("Next ➡️", disabled=st.session_state.page >= total_pages):
            st.session_state.page += 1

    page = st.session_state.page
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    display_df = filtered.iloc[start_idx:end_idx]

    for idx, row in display_df.iterrows():
        st.markdown(f"**{row['company']}** — {row['source']} — {row['date'].isoformat()}")
        st.write(row['text'])
        st.markdown(f"[View original]({row['link']})")
        st.markdown("---")

with col2:
    st.subheader("Trends & Summary")
    if not filtered.empty:
        trend = filtered.copy()
        trend["year"] = pd.to_datetime(trend["date"]).dt.year
        counts = trend.groupby(["year", "company"]).size().reset_index(name="count")
        chart = alt.Chart(counts).mark_line(point=True).encode(
            x="year:O",
            y="count:Q",
            color="company:N",
            tooltip=["year", "company", "count"]
        ).properties(height=300)
        st.altair_chart(chart, use_container_width=True)

    st.markdown("**Top negative keywords (simple heuristic)**")
    keyword_counts = {}
    for kw in NEGATIVE_KEYWORDS:
        keyword_counts[kw] = filtered['text'].str.lower().str.count(kw).sum()
    kw_df = pd.DataFrame([{"keyword": k, "count": v} for k, v in keyword_counts.items()])
    kw_df = kw_df.sort_values(by='count', ascending=False).head(20)
    st.table(kw_df)

# --- Download filtered results ---
st.download_button("Download filtered results (CSV)", filtered.to_csv(index=False).encode('utf-8'), "negative_mentions.csv", "text/csv")

# --- Next steps guidance ---
st.info("How to make this production-ready:\n1) Integrate X API (Twitter) with academic or elevated access for historical tweets.\n2) Use news APIs (NewsAPI, GDELT, MediaCloud) for article archives.\n3) For LinkedIn, export data from company pages or use a compliant enterprise partner.\n4) Replace the simple_sentiment_score with a transformer-based classifier or VADER for better accuracy.\n5) Persist ingested data into a DB (Postgres) for efficient 5-year queries.")

st.caption("This dashboard is a front-end skeleton. Replace the sample data loader with real fetchers to populate it with real posts and links.")
