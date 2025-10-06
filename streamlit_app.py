import streamlit as st
from datetime import date
from supabase import create_client
import pandas as pd
import altair as alt

# --- Connect to Supabase ---
url = st.secrets["supabase_url"]
anon_key = st.secrets["supabase_anon_key"]
service_key = st.secrets["supabase_service_key"]
admin_email = st.secrets["admin_email"]

# Clients
supabase = create_client(url, anon_key)
supabase_admin = create_client(url, service_key)

st.title("Multi-Sport Score Tracker: D vs T")

# --- Session state ---
if "admin_logged_in" not in st.session_state:
    st.session_state["admin_logged_in"] = False
if "user_email" not in st.session_state:
    st.session_state["user_email"] = None
if "selected_tab" not in st.session_state:
    st.session_state["selected_tab"] = "Golf"

# --- Admin login ---
if not st.session_state["admin_logged_in"]:
    with st.expander("🔒 Admin Login"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            try:
                auth_response = supabase.auth.sign_in_with_password(
                    {"email": email, "password": password}
                )
                if auth_response.user and auth_response.user.email == admin_email:
                    st.session_state["admin_logged_in"] = True
                    st.session_state["user_email"] = auth_response.user.email
                    st.success("Logged in as admin!")
                    st.experimental_rerun()
                else:
                    st.error("You are not authorized to modify data.")
            except Exception as e:
                st.error("Login failed: " + str(e))

# --- Logout ---
if st.session_state["admin_logged_in"]:
    st.sidebar.write(f"Logged in as: {st.session_state['user_email']}")
    if st.sidebar.button("Logout"):
        st.session_state["admin_logged_in"] = False
        st.session_state["user_email"] = None
        st.experimental_rerun()

# --- Sports selection (lazy loading tabs) ---
sports = ["Golf", "Driving", "Tennis"]
st.session_state["selected_tab"] = st.radio("Select Sport", sports, index=sports.index(st.session_state["selected_tab"]))
sport = st.session_state["selected_tab"]

st.header(f"{sport} Matches")

# --- Cached Supabase fetch ---
@st.cache_data
def get_matches(sport):
    return supabase.table("matches").select("*").eq("sport", sport).order("date", desc=True).execute().data

@st.cache_data
def get_current_season(sport):
    season_row = supabase.table("season_tracker").select("*").eq("sport", sport).execute().data
    if not season_row:
        supabase_admin.table("season_tracker").insert({"sport": sport, "current_season": 1}).execute()
        return 1
    else:
        return season_row[0]["current_season"]

# --- Current season ---
current_season = get_current_season(sport)
st.subheader(f"Current Season: {current_season}")

# --- Admin controls ---
if st.session_state["admin_logged_in"]:
    st.subheader("Record a new match")
    col1, col2 = st.columns(2)
    with col1:
        theo_score = st.number_input(f"T Score ({sport})", min_value=0, step=1, key=f"t_{sport}")
    with col2:
        denet_score = st.number_input(f"D Score ({sport})", min_value=0, step=1, key=f"d_{sport}")

    match_date = st.date_input(f"Match Date ({sport})", value=date.today(), key=f"date_{sport}")

    if st.button(f"Add Match ({sport})"):
        supabase_admin.table("matches").insert([{
            "sport": sport,
            "season": current_season,
            "date": match_date.isoformat(),
            "theo_score": theo_score,
            "denet_score": denet_score
        }]).execute()
        st.success("Match added!")
        st.cache_data.clear()
        st.experimental_rerun()

    if st.button(f"End Season ({sport})"):
        supabase_admin.table("season_tracker").update(
            {"current_season": current_season + 1}
        ).eq("sport", sport).execute()
        st.success(f"Season ended. New season is {current_season + 1}")
        st.cache_data.clear()
        st.experimental_rerun()

# --- Fetch matches ---
matches = get_matches(sport)

# --- Display table ---
st.subheader("All Matches")
if matches:
    st.dataframe(pd.DataFrame([{
        "Season": m.get("season"),
        "Date": m.get("date"),
        "Theo Score": m.get("theo_score") if m.get("theo_score") is not None else 0,
        "Denet Score": m.get("denet_score") if m.get("denet_score") is not None else 0
    } for m in matches]), height=250)
else:
    st.write("No matches recorded yet.")

# --- Current season score tracker ---
st.subheader("Current Season Score Tracker")
current_season_matches = [m for m in matches if m.get("season") == current_season]

if sport.lower() == "tennis":
    # Tennis: count matches won
    t_total = sum(1 for m in current_season_matches if (m.get("theo_score") or 0) > (m.get("denet_score") or 0))
    d_total = sum(1 for m in current_season_matches if (m.get("denet_score") or 0) > (m.get("theo_score") or 0))
else:
    # Other sports: sum raw scores
    t_total = sum(int(m.get("theo_score") or 0) for m in current_season_matches)
    d_total = sum(int(m.get("denet_score") or 0) for m in current_season_matches)

st.metric(label="T Total Score", value=t_total)
st.metric(label="D Total Score", value=d_total)

# --- Line graph: score over time ---
if current_season_matches:
    df = pd.DataFrame(current_season_matches)

    if sport.lower() == "tennis":
        df["t_win"] = df.apply(lambda row: 1 if (row.get("theo_score") or 0) > (row.get("denet_score") or 0) else 0, axis=1)
        df["d_win"] = df.apply(lambda row: 1 if (row.get("denet_score") or 0) > (row.get("theo_score") or 0) else 0, axis=1)
        df["t_cum"] = df["t_win"].cumsum()
        df["d_cum"] = df["d_win"].cumsum()
        chart_data = df[["date", "t_cum", "d_cum"]].copy()
        chart_data = chart_data.melt(id_vars=["date"], value_vars=["t_cum", "d_cum"], var_name="Player", value_name="Score")
        chart_data["Player"] = chart_data["Player"].map({"t_cum": "T", "d_cum": "D"})
    else:
        df["t_cum"] = df["theo_score"].cumsum()
        df["d_cum"] = df["denet_score"].cumsum()
        chart_data = df[["date", "t_cum", "d_cum"]].copy()
        chart_data = chart_data.melt(id_vars=["date"], value_vars=["t_cum", "d_cum"], var_name="Player", value_name="Score")
        chart_data["Player"] = chart_data["Player"].map({"t_cum": "T", "d_cum": "D"})

    chart_data["date"] = pd.to_datetime(chart_data["date"])

    st.subheader("Score Over Time")
    line_chart = alt.Chart(chart_data).mark_line(point=True).encode(
        x="date:T",
        y="Score:Q",
        color="Player:N",
        tooltip=["date:T", "Player:N", "Score:Q"]
    ).properties(
        width=700,
        height=400
    )
    st.altair_chart(line_chart)
