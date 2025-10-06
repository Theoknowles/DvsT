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
if "refresh_data" not in st.session_state:
    st.session_state["refresh_data"] = False

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
        st.session_state["refresh_data"] = True

# --- Sports tabs ---
sports = ["Golf", "Driving", "Tennis"]
tabs = st.tabs(sports)

for i, sport in enumerate(sports):
    with tabs[i]:
        # --- Fetch current season fresh ---
        season_row = supabase.table("season_tracker").select("*").eq("sport", sport).execute().data
        if not season_row:
            supabase_admin.table("season_tracker").insert({"sport": sport, "current_season": 1}).execute()
            current_season = 1
        else:
            current_season = season_row[0]["current_season"]

        st.subheader(f"{sport} - Current Season: {current_season}")

        # --- Cached fetch for matches ---
        @st.cache_data
        def get_matches(sport, season):
            return supabase.table("matches").select("*").eq("sport", sport).eq("season", season).order("date", desc=True).execute().data

        matches = get_matches(sport, current_season)

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
                st.session_state["refresh_data"] = True
                st.success("Match added!")

            if st.button(f"End Season ({sport})"):
                supabase_admin.table("season_tracker").update(
                    {"current_season": current_season + 1}
                ).eq("sport", sport).execute()
                st.session_state["refresh_data"] = True
                st.success(f"Season ended. New season is {current_season + 1}")

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
        current_season_matches = matches

        if sport.lower() == "tennis":
            t_total = sum(1 for m in current_season_matches if (m.get("theo_score") or 0) > (m.get("denet_score") or 0))
            d_total = sum(1 for m in current_season_matches if (m.get("denet_score") or 0) > (m.get("theo_score") or 0))
        else:
            t_total = sum(m.get("theo_score") or 0 for m in current_season_matches)
            d_total = sum(m.get("denet_score") or 0 for m in current_season_matches)

        col1, col2 = st.columns(2)
        col1.metric(label="T Total Score", value=t_total)
        col2.metric(label="D Total Score", value=d_total)
