import os
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Projects Tracker Dashboard", layout="wide")

# ---- Settings: set these in Streamlit "Secrets" (see README) ----
def setting(name, default=""):
    try:
        return st.secrets[name]
    except Exception:
        return os.environ.get(name, default)

SHEET_ID = setting("SHEET_ID")
GID = setting("GID", "0")  # Daily Tracker tab id
LOCAL_FILE = os.environ.get("LOCAL_FILE", "")             # only for testing

@st.cache_data(ttl=300)  # re-reads the sheet at most every 5 minutes
def load():
    if LOCAL_FILE:
        df = pd.read_excel(LOCAL_FILE, sheet_name="Daily Tracker")
    else:
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
        df = pd.read_csv(url)
    df = df.iloc[:, :8].dropna(how="all")
    df.columns = ["Month", "Week", "Date", "Agent", "Brand", "Task", "Volume", "Hours"]
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce").fillna(0)
    df["Hours"] = pd.to_numeric(df["Hours"], errors="coerce").fillna(0)
    df = df.dropna(subset=["Date"]).drop_duplicates()
    df["Week Start"] = (df["Date"] - pd.to_timedelta(df["Date"].dt.weekday, unit="D")).dt.date
    return df

st.title("Projects Tracker Dashboard")
if not SHEET_ID and not LOCAL_FILE:
    st.error("SHEET_ID is not set. Add it in Settings > Secrets.")
    st.stop()
df = load()

# ---- Filters ----
with st.sidebar:
    st.header("Filters")
    d0, d1 = df["Date"].min().date(), df["Date"].max().date()
    rng = st.date_input("Date range", (d0, d1), min_value=d0, max_value=d1)
    brands = st.multiselect("Brand", sorted(df["Brand"].unique()))
    agents = st.multiselect("Agent", sorted(df["Agent"].unique()))
    if st.button("Refresh now"):
        st.cache_data.clear()
        st.rerun()
if len(rng) == 2:
    df = df[(df["Date"].dt.date >= rng[0]) & (df["Date"].dt.date <= rng[1])]
if brands:
    df = df[df["Brand"].isin(brands)]
if agents:
    df = df[df["Agent"].isin(agents)]

c = st.columns(4)
c[0].metric("Hours worked", f"{df['Hours'].sum():,.0f}")
c[1].metric("Volume completed", f"{df['Volume'].sum():,.0f}")
c[2].metric("Active agents", df["Agent"].nunique())
c[3].metric("Active brands", df["Brand"].nunique())
st.caption(f"Latest entry: {df['Date'].max().date() if len(df) else '-'}. Data refreshes every 5 minutes.")

t1, t2, t3, t4 = st.tabs(["Brand level", "Agent level", "Week wise", "Raw data"])
with t1:
    b = df.groupby("Brand")[["Hours", "Volume"]].sum().sort_values("Hours", ascending=False)
    st.bar_chart(b["Hours"])
    st.dataframe(b.round(1))
with t2:
    a = df.groupby("Agent")[["Hours", "Volume"]].sum().sort_values("Hours", ascending=False)
    st.bar_chart(a["Hours"])
    st.subheader("Hours by agent and brand")
    st.dataframe(df.pivot_table(index="Agent", columns="Brand", values="Hours", aggfunc="sum", fill_value=0).round(1))
with t3:
    by = st.radio("Break down by", ["Total", "Brand", "Agent"], horizontal=True)
    if by == "Total":
        w = df.groupby("Week Start")["Hours"].sum()
    else:
        w = df.pivot_table(index="Week Start", columns=by, values="Hours", aggfunc="sum", fill_value=0)
    st.bar_chart(w)
    st.dataframe(df.groupby("Week Start")[["Hours", "Volume"]].sum().round(1))
with t4:
    st.dataframe(df.sort_values("Date", ascending=False))
