import streamlit as st
import pandas as pd
import plotly.express as px
import httpx

API_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="LearnPath AI",
    page_icon="🎓",
    layout="wide"
)

st.title("🎓 LearnPath AI")
st.caption("Adaptive Learning Intelligence Platform | YottaFlex AI")


def api_get(endpoint):
    try:
        response = httpx.get(
            f"{API_URL}{endpoint}",
            timeout=20
        )
        response.raise_for_status()
        return response.json()
    except Exception as error:
        st.error(str(error))
        return None


def api_post(endpoint):
    try:
        response = httpx.post(
            f"{API_URL}{endpoint}",
            timeout=60
        )
        response.raise_for_status()
        return response.json()
    except Exception as error:
        st.error(str(error))
        return None


stats = api_get("/api/stats")

if stats:
    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Learners", stats["learners"])
    c2.metric("Skills", stats["skills"])
    c3.metric("Content Items", stats["content_items"])
    c4.metric("Attempts", stats["attempts"])

st.divider()

learners_data = api_get("/api/learners?limit=100")

if not learners_data:
    st.stop()

learners = learners_data["learners"]

options = {
    f"{item['name']} ({item['learner_id']})": item["learner_id"]
    for item in learners
}

selected = st.selectbox(
    "Select Learner",
    list(options)
)

learner_id = options[selected]

tab1, tab2, tab3 = st.tabs([
    "Skill Mastery",
    "AI Recommendations",
    "Learning Paths"
])

with tab1:
    st.subheader("Skill Mastery Analysis")

    data = api_get(
        f"/api/learners/{learner_id}/mastery"
    )

    if data and data["skills"]:
        df = pd.DataFrame(data["skills"])
        df["mastery_percent"] = df["mastery_score"] * 100

        fig = px.bar(
            df,
            x="skill_id",
            y="mastery_percent",
            color="mastery_percent",
            color_continuous_scale="RdYlGn",
            title="Skill Mastery"
        )

        fig.add_hline(
            y=70,
            line_dash="dash",
            annotation_text="Mastery Threshold"
        )

        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No mastery history available.")

with tab2:
    st.subheader("Adaptive Recommendations")

    limit = st.slider(
        "Number of recommendations",
        1,
        10,
        5
    )

    if st.button("Generate Recommendations", type="primary"):
        result = api_post(
            f"/api/learners/{learner_id}/recommend?limit={limit}"
        )

        if result:
            st.session_state["recommendations"] = result["recommendations"]
            st.session_state["selected_learner"] = learner_id

    if st.session_state.get("selected_learner") == learner_id:
        for item in st.session_state.get("recommendations", []):
            with st.container(border=True):
                st.subheader(item["content_title"])
                st.write(f"Skill: {item['skill_name']}")
                st.write(f"Format: {item['format']}")
                st.write(f"Difficulty: {item['difficulty']}")
                st.write(f"Mastery: {item['mastery'] * 100:.1f}%")
                st.info(item["rationale"])
                st.caption(item["recommendation_id"])

with tab3:
    st.subheader("Learning Paths")

    data = api_get(
        f"/api/learners/{learner_id}/paths"
    )

    if data and data["paths"]:
        st.dataframe(
            pd.DataFrame(data["paths"]),
            use_container_width=True
        )
    else:
        st.info("No learning paths available.")