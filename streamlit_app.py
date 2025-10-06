import streamlit as st
from datetime import date
from supabase import create_client
import pandas as pd

# --- Connect to Supabase ---
url = st.secrets["supabase_url"]
anon_key = st.secrets["supabase_anon_key"]
service_key = st.secrets["supabase_service_key"]
admin_email = st.secrets["admin_email"]

supabase = create_client(url, anon_key)
supabase_admin = create_client(url, service_key)

st.title("Multi-Sport Score Tracker: D vs T")

# --- Session state ---
if "admin_logged_in" not in st.session_state:
    st.session_state["admin_logged_in"] = False
if "user_email" not in st.session_state:
    st.session_state["user_email"] = None

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

# --- Helper functions ---
def fetch_current_season(sport):
    """Fetch maximum current_season for the sport using admin client (avoids RLS issues)."""
    result = supabase_admin.table("season_tracker")\
        .select("current_season")\
        .eq("sport", sport)\
        .order("current_season", desc=True)\
        .limit(1)\
        .execute()
    data = result.data or []

    if data:
        return data[0]["current_season"]
    else:
        st.error(f"No season found for sport '{sport}'. Please create it manually in Supabase.")
        return 1

def fetch_matches(sport, season=None):
    """Fetch matches for a given sport and optionally a specific season."""
    query = supabase.table("matches").select("*").eq("sport", sport)
    if season:
        query = query.eq("season", season)
    result = query.order("date", desc=True).execute()
    return result.data or []

# --- Sports tabs ---
sports = ["Golf", "Driving", "Tennis"]
tabs = st.tabs(sports)

for i, sport in enumerate(sports):
    with tabs[i]:
        # --- Current season ---
        current_season = fetch_current_season(sport)
        st.subheader(f"{sport} - Current Season: {current_season}")

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

            if st.button(f"End Season ({sport})"):
                # Increment current season for the sport
                new_season = current_season + 1
                supabase_admin.table("season_tracker").update(
                    {"current_season": new_season}
                ).eq("sport", sport).execute()
                st.success(f"Season ended. New season is {new_season}")
                current_season = new_season

        # --- Fetch current season matches ---
        matches = fetch_matches(sport, current_season)

        # --- Display table ---
        st.subheader("All Matches")
        if matches:
            df = pd.DataFrame([{
                "Season": m.get("season"),
                "Date": m.get("date"),
                "Theo Score": m.get("theo_score") or 0,
                "Denet Score": m.get("denet_score") or 0
            } for m in matches])
            st.dataframe(df, height=200)
        else:
            st.write("No matches recorded yet.")

        # --- Current season score tracker ---
        st.subheader("Current Season Score Tracker")
        if sport.lower() == "tennis":
            t_total = sum(1 for m in matches if (m.get("theo_score") or 0) > (m.get("denet_score") or 0))
            d_total = sum(1 for m in matches if (m.get("denet_score") or 0) > (m.get("theo_score") or 0))
        else:
            t_total = sum(m.get("theo_score") or 0 for m in matches)
            d_total = sum(m.get("denet_score") or 0 for m in matches)

        col1, col2 = st.columns(2)
        col1.metric(label="T Total Score", value=t_total)
        col2.metric(label="D Total Score", value=d_total)

        # --- Season Wins Tracker ---
        st.subheader("Season Wins Tracker")

        all_matches = fetch_matches(sport)
        season_totals = {}
        for m in all_matches:
            season = m.get("season")
            if season == current_season:
                continue  # skip current season
            t_score = m.get("theo_score") or 0
            d_score = m.get("denet_score") or 0
            if season not in season_totals:
                season_totals[season] = {"Theo": 0, "Denet": 0}
            season_totals[season]["Theo"] += t_score
            season_totals[season]["Denet"] += d_score

        t_wins = 0
        d_wins = 0
        for season, scores in season_totals.items():
            if scores["Theo"] > scores["Denet"]:
                t_wins += 1
            elif scores["Denet"] > scores["Theo"]:
                d_wins += 1
            # Ties ignored

        st.write(f"🏆 Theo has won **{t_wins}** season(s)")
        st.write(f"🏆 Denet has won **{d_wins}** season(s)")
