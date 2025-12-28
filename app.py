import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import date, datetime, timedelta

st.set_page_config(page_title="Macro × Markets", layout="wide")

st.title("Macro × Markets")
st.caption("Vibe-coded macro + event tracker for your watchlist.")

# ---------- Watchlist (stored in session) ----------
if "watchlist" not in st.session_state:
    st.session_state.watchlist = ["AAPL", "MSFT"]

with st.sidebar:
    st.header("Watchlist")
    new_ticker = st.text_input("Add a ticker (e.g., NVDA)").strip().upper()
    col_add, col_clear = st.columns(2)

    if col_add.button("Add") and new_ticker:
        if new_ticker not in st.session_state.watchlist:
            st.session_state.watchlist.append(new_ticker)

    if col_clear.button("Clear"):
        st.session_state.watchlist = []

    st.write("Current:")
    if st.session_state.watchlist:
        st.write(", ".join(st.session_state.watchlist))
    else:
        st.info("No tickers yet. Add one above.")

# ---------- Macro events (hard-coded for now) 


st.subheader("Macro calendar (v1)")
today = date.today()

# You can edit these anytime. For MVP, hard-coding is totally fine.
macro_events = [
    {"date": today + timedelta(days=1), "event": "CPI (Inflation) release", "why": "Can move rates & growth stocks; affects valuations."},
    {"date": today + timedelta(days=7), "event": "FOMC / Fed decision", "why": "Rate path + forward guidance; big driver of market regime."},
    {"date": today + timedelta(days=14), "event": "Jobs report (NFP)", "why": "Labor tightness → inflation pressure → rate expectations."},
]

macro_df = pd.DataFrame(macro_events).sort_values("date")
macro_df["date"] = pd.to_datetime(macro_df["date"])
st.dataframe(macro_df, use_container_width=True, hide_index=True)

# ---------- Earnings tracker ----------
st.subheader("Company events (earnings)")
st.caption("This pulls 'earnings date' from yfinance when available (it’s not perfect, but great for MVP).")

def safe_earnings_date(ticker: str):
    try:
        t = yf.Ticker(ticker)
        cal = t.calendar  # can be empty / inconsistent
        if isinstance(cal, pd.DataFrame) and not cal.empty:
            # common format: rows are fields, columns include 'Earnings Date'
            if "Earnings Date" in cal.index:
                val = cal.loc["Earnings Date"].values[0]
                # sometimes it’s a list/tuple of dates
                if isinstance(val, (list, tuple)) and len(val) > 0:
                    val = val[0]
                return pd.to_datetime(val)
    except Exception:
        return None
    return None

rows = []
for tic in st.session_state.watchlist:
    ed = safe_earnings_date(tic)
    rows.append({
        "ticker": tic,
        "earnings_date": ed.date().isoformat() if ed is not None else None,
        "days_until": (ed.date() - today).days if ed is not None else None
    })

earn_df = pd.DataFrame(rows).sort_values(["earnings_date", "ticker"], na_position="last")
st.dataframe(earn_df, use_container_width=True, hide_index=True)
# ---------- ALERTS ----------
st.subheader("Alerts")

now = datetime.now()

# Macro alerts: next 48 hours
macro_df_alert = macro_df.copy()
macro_df_alert["hours_until"] = (macro_df_alert["date"] - pd.Timestamp(now)) / pd.Timedelta(hours=1)

soon_macro = macro_df_alert[(macro_df_alert["hours_until"] >= 0) & (macro_df_alert["hours_until"] <= 48)]

if len(soon_macro) > 0:
    top = soon_macro.iloc[0]
    st.error(
        f"🚨 **Macro in the next 48 hours:** {top['event']} on **{top['date'].date().isoformat()}** — {top['why']}"
    )
else:
   st.success("✅ **Clear macro window:** no major releases in the next 48 hours. Volatility risk from macro is low.")

# Earnings alerts: next 7 days
earn_df_alert = earn_df.dropna(subset=["days_until"]).copy()
soon_earn_7d = earn_df_alert[(earn_df_alert["days_until"] >= 0) & (earn_df_alert["days_until"] <= 7)]

if len(soon_earn_7d) > 0:
    tickers = ", ".join(soon_earn_7d["ticker"].tolist())
    st.warning(f"🟡 **Earnings in the next 7 days (watchlist):** {tickers}")
else:
    st.info("ℹ️ No watchlist earnings in the next 7 days (based on available earnings dates).")

# ---------- EXPOSURE & INTERPRETATION ----------
st.subheader("Exposure & interpretation")

# 1) Sector -> macro sensitivity mapping (edit anytime)
sector_to_tags = {
    "Technology": ["rate-sensitive", "growth"],
    "Communication Services": ["rate-sensitive", "growth"],
    "Consumer Discretionary": ["cyclical", "rate-sensitive"],
    "Financial Services": ["rate-sensitive", "macro-sensitive"],
    "Real Estate": ["rate-sensitive"],
    "Utilities": ["defensive", "rate-sensitive"],
    "Consumer Staples": ["defensive", "inflation-sensitive"],
    "Health Care": ["defensive"],
    "Industrials": ["cyclical"],
    "Energy": ["inflation-sensitive", "commodities"],
    "Basic Materials": ["inflation-sensitive", "commodities"],
}

def get_sector(ticker: str):
    try:
        info = yf.Ticker(ticker).info
        return info.get("sector")
    except Exception:
        return None

# 2) Build an exposure table
ex_rows = []
for tic in st.session_state.watchlist:
    sector = get_sector(tic)
    tags = sector_to_tags.get(sector, ["unknown"]) if sector else ["unknown"]
    ex_rows.append({"ticker": tic, "sector": sector, "tags": ", ".join(tags)})

ex_df = pd.DataFrame(ex_rows)

st.dataframe(ex_df, use_container_width=True, hide_index=True)

# 3) Summarize concentration in tags
all_tags = []
for t in ex_df["tags"].fillna("unknown"):
    all_tags.extend([x.strip() for x in t.split(",")])

tag_counts = pd.Series(all_tags).value_counts()

top_tag = tag_counts.index[0] if len(tag_counts) else "unknown"
top_share = (tag_counts.iloc[0] / max(len(st.session_state.watchlist), 1)) if len(tag_counts) else 0

# 4) Tie it to the next macro event
next_event = macro_df.sort_values("date").iloc[0]["event"]

if top_tag == "rate-sensitive":
    st.info(f"🧠 **Interpretation:** Your watchlist leans **rate-sensitive** (~{top_share:.0%}). If **{next_event}** surprises hotter/hawkish, expect higher volatility—especially in growth names.")
elif top_tag == "cyclical":
    st.info(f"🧠 **Interpretation:** Your watchlist leans **cyclical** (~{top_share:.0%}). **{next_event}** matters because it can shift growth expectations and risk appetite.")
elif top_tag == "defensive":
    st.info(f"🧠 **Interpretation:** Your watchlist leans **defensive** (~{top_share:.0%}). **{next_event}** may move the market, but your names may be relatively insulated (not immune).")
elif top_tag == "inflation-sensitive":
    st.info(f"🧠 **Interpretation:** Your watchlist has **inflation-sensitive** exposure (~{top_share:.0%}). **{next_event}** can move input-cost expectations and sector leadership.")
else:
    st.info(f"🧠 **Interpretation:** Mixed/unclear exposure (some tickers missing sector data). **{next_event}** is still your next macro catalyst.")

# ---------- WEEKLY MEMO ----------
st.subheader("Weekly memo")
tone = st.selectbox("Tone", ["Base", "Bull", "Bear"], index=0)


next_macro = macro_df.sort_values("date").iloc[0]
macro_name = next_macro["event"]

# exposure language
if top_tag == "rate-sensitive":
    exposure_line = "Your watchlist leans toward rate-sensitive, growth-oriented names."
elif top_tag == "cyclical":
    exposure_line = "Your watchlist has meaningful exposure to cyclical sectors."
elif top_tag == "defensive":
    exposure_line = "Your watchlist is relatively defensive compared to the broader market."
elif top_tag == "inflation-sensitive":
    exposure_line = "Your watchlist has notable inflation-sensitive exposure."
else:
    exposure_line = "Your watchlist has mixed exposure across sectors."

# earnings language
if len(soon_earn_7d) > 0:
    earn_line = f"Earnings to watch this week include {', '.join(soon_earn_7d['ticker'].tolist())}."
else:
    earn_line = "There are no major watchlist earnings scheduled in the coming week."

# ----- tone-aware memo text -----
if tone == "Bull":
    opener = f"This week’s key macro focus is **{macro_name}**—a potential tailwind if it comes in supportive for risk sentiment."
    closer = "Net: the setup looks constructive if the data validates the current narrative, with upside led by rate-sensitive names."
elif tone == "Bear":
    opener = f"This week’s key macro focus is **{macro_name}**—a key risk if it surprises against expectations."
    closer = "Net: caution is warranted; adverse macro outcomes could drive downside volatility, particularly in rate-sensitive sectors."
else:  # Base
    opener = f"This week’s key macro focus is **{macro_name}**, which may influence rate expectations and broader risk sentiment."
    closer = "Net: macro data is likely to be the primary near-term driver, with market reactions hinging on surprises versus expectations."

memo_text = (
    f"{opener} "
    f"{exposure_line} "
    f"{earn_line} "
    f"{closer}"
)
st.markdown(memo_text)

st.text_area(
    "Copy memo",
    memo_text.replace("**", ""),
    height=150
)
  
   
# ---------- Quick “why it matters” vibe panel ----------
st.subheader("This week: what should you care about?")
next_macro = macro_df.iloc[0]
st.write(
    f"**Next macro event:** {next_macro['event']} on **{next_macro['date'].date().isoformat()}** — {next_macro['why']}"
)

soon_earn = earn_df.dropna(subset=["days_until"])
soon_earn = soon_earn[(soon_earn["days_until"] >= 0) & (soon_earn["days_until"] <= 7)]

if len(soon_earn) > 0:
    st.write("**Earnings in the next 7 days (watchlist):**")
    st.write(", ".join(soon_earn["ticker"].tolist()))
else:
    st.write("**No watchlist earnings in the next 7 days** (based on available data).")

