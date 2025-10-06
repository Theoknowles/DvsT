import streamlit as st
from datetime import date
from supabase import create_client

# --- Connect to Supabase ---
url = st.secrets["supabase_url"]
anon_key = st.secrets["supabase_anon_key"]
service_key = st.secrets["supabase_service_key"]
admin_email = st.secrets["admin_email"]

# Clients
supabase = create_client(url, anon_key)           # For auth & read
supabase_admin = create_client(url, service_key)  # For write operations

st.title("Multi-Sport Score Tracker: D vs T")

# --- Admin login ---
if "admin_logged_in" not in st.session_state:
    st.session_state["admin_logged_in"] = False

if not st.session_state["admin_logged_in"]:
    st.subheader("Admin Login")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        try:
            user = supabase.auth.sign_in(email=email, password=password)
            if user.user.email == admin_email:
                st.session_state["admin_logged_in"] = True
                st.success("Logged in as admin!")
            else:
                st.error("You are not authorized to modify data.")
        except Exception as e:
            st.error("Login failed: " + str(e))
    st.stop()  # Stop rendering rest of app until logged in

# --- Multi-sport tabs ---
sports = ["Tennis", "Ping Pong", "Badminton"]
tabs = st.tabs(sports)

for i, sport in enumerate(sports):
    with tabs[i]:
        st.header(f"{sport} Matches")

        # --- Current season for this sport ---
        season_row = supabase.table("season_tracker").select("*").eq("sport", sport).execute().data
        if not season_row:
            supabase_admin.table("season_tracker").insert({"sport": sport, "current_season": 1}).execute()
            current_season = 1
        else:
            current_season = season_row[0]["current_season"]

        st.subheader(f"Current Season: {current_season}")

        # --- Record a new match (admin only) ---
        st.subheader("Record a new match")
        col1, col2 = st.columns(2)
        with col1:
            t_score = st.number_input(f"T Score ({sport})", min_value=0, step=1, key=f"t_{sport}")
        with col2:
            d_score = st.number_input(f"D Score ({sport})", min_value=0, step=1, key=f"d_{sport}")

        match_date = st.date_input(f"Match Date ({sport})", value=date.today(), key=f"date_{sport}")

        if st.button(f"Add Match ({sport})"):
            if st.session_state["admin_logged_in"]:
                supabase_admin.table("matches").insert([{
                    "sport": sport,
                    "season": current_season,
                    "date": match_date,
                    "t_score": t_score,
                    "d_score": d_score
                }]).execute()
                st.success("Match added!")
                st.experimental_rerun()

        # --- End the season (admin only) ---
        if st.button(f"End Season ({sport})"):
            if st.session_state["admin_logged_in"]:
                supabase_admin.table("season_tracker").update({"current_season": current_season + 1}).eq("sport", sport).execute()
                st.success(f"Season ended. New season is {current_season + 1}")
                st.experimental_rerun()

        # --- Display all matches ---
        st.subheader("All Matches")
        matches_response = supabase.table("matches").select("*").eq("sport", sport).order("date", desc=True).execute()
        matches = matches_response.data

        if matches:
            st.table([{
                "Season": m["season"],
                "Date": m["date"],
                "T Score": m["t_score"],
                "D Score": m["d_score"]
            } for m in matches])
        else:
            st.write("No matches recorded yet.")

        # --- Current season score tracker ---
        st.subheader("Current Season Score Tracker")
        current_season_matches = [m for m in matches if m["season"] == current_season]
        t_total = sum(m["t_score"] for m in current_season_matches)
        d_total = sum(m["d_score"] for m in current_season_matches)

        st.metric(label="T Total Score", value=t_total)
        st.metric(label="D Total Score", value=d_total)
