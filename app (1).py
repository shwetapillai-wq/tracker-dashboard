import os
import altair as alt
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Projects Tracker Dashboard", layout="wide")

def setting(name, default=""):
    try:
        return st.secrets[name]
    except Exception:
        return os.environ.get(name, default)

SHEET_ID = setting("SHEET_ID")
GID = setting("GID", "0")          # Daily Tracker tab id
LOCAL_FILE = os.environ.get("LOCAL_FILE", "")  # only for testing
TEST_BRANDS = ["Sample", "RF"]     # names treated as test projects

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
    df = df.dropna(subset=["Date"])
    for c in ["Agent", "Brand", "Task"]:
        df[c] = df[c].astype(str).str.strip()
    before = len(df)
    df = df.drop_duplicates()
    df.attrs["dups"] = before - len(df)
    df["Week Start"] = (df["Date"] - pd.to_timedelta(df["Date"].dt.weekday, unit="D")).dt.date
    return df

def bar(series, horizontal=False):
    """Bar chart sorted from highest to lowest."""
    d = series.reset_index()
    d.columns = ["Name", "Hours"]
    x, y = ("Hours:Q", alt.Y("Name:N", sort="-x", title=None)) if horizontal else (alt.X("Name:N", sort="-y", title=None), "Hours:Q")
    base = alt.Chart(d).mark_bar().encode(x=x, y=y, tooltip=["Name", alt.Tooltip("Hours:Q", format=",.1f")])
    st.altair_chart(base.properties(width="container", height=320))

st.title("Projects Tracker Dashboard")
if not SHEET_ID and not LOCAL_FILE:
    st.error("SHEET_ID is not set. Add it in Settings > Secrets.")
    st.stop()
full = load()
dups = full.attrs.get("dups", 0)
df = full

with st.sidebar:
    st.header("Filters")
    d0, d1 = df["Date"].min().date(), df["Date"].max().date()
    rng = st.date_input("Date range", (d0, d1), min_value=d0, max_value=d1)
    brands = st.multiselect("Brand", sorted(df["Brand"].unique()))
    agents = st.multiselect("Agent", sorted(df["Agent"].unique()))
    hide = st.checkbox("Hide test projects (Sample, RF)", value=True)
    if st.button("Refresh now"):
        st.cache_data.clear()
        st.rerun()
if hide:
    df = df[~df["Brand"].isin(TEST_BRANDS)]
if len(rng) == 2:
    df = df[(df["Date"].dt.date >= rng[0]) & (df["Date"].dt.date <= rng[1])]
if brands:
    df = df[df["Brand"].isin(brands)]
if agents:
    df = df[df["Agent"].isin(agents)]

# Average hours per agent per day worked
agent_days = df.groupby(["Agent", "Date"])["Hours"].sum()
avg_day = agent_days.mean() if len(agent_days) else 0

c = st.columns(5)
c[0].metric("Hours worked", f"{df['Hours'].sum():,.0f}")
c[1].metric("Volume completed", f"{df['Volume'].sum():,.0f}")
c[2].metric("Active agents", df["Agent"].nunique())
c[3].metric("Active brands", df["Brand"].nunique())
c[4].metric("Avg hours / agent / day", f"{avg_day:.1f}")
st.caption(f"Latest entry: {df['Date'].max().date() if len(df) else '-'}. Data refreshes every 5 minutes. "
           "Volume counts different work types (orders, cases, listings), so compare it within the same task only.")

t1, t2, t3, t4, t5 = st.tabs(["Brand level", "Agent level", "Week wise", "Data checks", "Raw data"])

with t1:
    b = df.groupby("Brand")[["Hours", "Volume"]].sum().sort_values("Hours", ascending=False)
    bar(b["Hours"])
    pick = st.selectbox("See the task split for a brand", ["(choose)"] + list(b.index))
    if pick != "(choose)":
        tk = df[df["Brand"] == pick].groupby("Task")[["Hours", "Volume"]].sum().sort_values("Hours", ascending=False)
        bar(tk["Hours"], horizontal=True)
        st.dataframe(tk.round(1))
    st.dataframe(b.round(1))

with t2:
    a = df.groupby("Agent")[["Hours", "Volume"]].sum().sort_values("Hours", ascending=False)
    a["Days worked"] = df.groupby("Agent")["Date"].nunique()
    a["Avg hours / day"] = (a["Hours"] / a["Days worked"]).round(1)
    bar(a["Hours"], horizontal=True)
    st.dataframe(a.round(1))
    st.subheader("Hours by agent and brand")
    st.dataframe(df.pivot_table(index="Agent", columns="Brand", values="Hours", aggfunc="sum", fill_value=0).round(1))
    st.subheader("Hours by agent and week")
    st.dataframe(df.pivot_table(index="Agent", columns="Week Start", values="Hours", aggfunc="sum", fill_value=0).round(1))

with t3:
    by = st.radio("Break down by", ["Total", "Brand", "Agent"], horizontal=True)
    if by == "Total":
        w = df.groupby("Week Start")["Hours"].sum()
    else:
        w = df.pivot_table(index="Week Start", columns=by, values="Hours", aggfunc="sum", fill_value=0)
    st.bar_chart(w)
    st.caption("Each bar is one week, shown by its Monday date.")
    st.dataframe(df.groupby("Week Start")[["Hours", "Volume"]].sum().round(1))

with t4:
    st.write(f"Duplicate rows removed automatically: **{dups}**")
    ad = df.groupby(["Agent", "Date"])["Hours"].sum().reset_index()
    over, under = ad[ad["Hours"] > 10], ad[ad["Hours"] < 4]
    st.write(f"Agent-days with more than 10 hours: **{len(over)}**")
    if len(over): st.dataframe(over.assign(Date=over["Date"].dt.date))
    st.write(f"Agent-days with less than 4 hours: **{len(under)}**")
    if len(under): st.dataframe(under.assign(Date=under["Date"].dt.date))
    st.write(f"Rows with 0 hours: **{int((df['Hours'] == 0).sum())}**")
    st.write(f"Distinct task names: **{df['Task'].nunique()}**. Similar names split the numbers, so keep them consistent.")

with t5:
    st.dataframe(df.sort_values("Date", ascending=False))
