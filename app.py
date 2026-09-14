import streamlit as st
import json

st.set_page_config(page_title="AI Ideation Studio", page_icon="💡", layout="wide")

# Initialize session state for storage
if "ideas" not in st.session_state:
    st.session_state.ideas = None
if "elaborations" not in st.session_state:
    st.session_state.elaborations = {}
if "saved_ideas" not in st.session_state:
    st.session_state.saved_ideas = []

st.title("💡 AI-Powered Ideation & Evaluation Studio")
st.markdown("Generate scored project concepts with market validation, granular hardware/cloud budgets, month-by-month roadmaps, and save your favorites.")

# --- Sidebar: Model & API Configuration + Bookmarks Manager ---
st.sidebar.header("⚙️ Model Configuration")
provider = st.sidebar.selectbox(
    "Select AI Provider / Model",
    [
        "OpenAI (gpt-4o)",
        "Anthropic (claude-3-5-sonnet-20240620)",
        "Google (gemini-1.5-pro)"
    ]
)

api_key = st.sidebar.text_input("Enter API Key for Selected Provider", type="password")
st.sidebar.caption("Keys are stored only in your active browser session.")

# --- Sidebar: Saved Projects Management ---
st.sidebar.divider()
st.sidebar.header(f"💾 Saved Projects ({len(st.session_state.saved_ideas)})")

# Export saved ideas
if st.session_state.saved_ideas:
    saved_json_str = json.dumps(st.session_state.saved_ideas, indent=2)
    st.sidebar.download_button(
        label="📥 Export Saved Ideas (JSON)",
        data=saved_json_str,
        file_name="saved_project_ideas.json",
        mime="application/json",
        use_container_width=True
    )

# Import previously saved ideas
uploaded_file = st.sidebar.file_uploader("Upload Saved Projects (.json)", type=["json"])
if uploaded_file is not None:
    try:
        imported_ideas = json.load(uploaded_file)
        if isinstance(imported_ideas, list):
            # Avoid duplicates by title
            current_titles = {i.get("title") for i in st.session_state.saved_ideas}
            added = 0
            for item in imported_ideas:
                if item.get("title") not in current_titles:
                    st.session_state.saved_ideas.append(item)
                    added += 1
            if added > 0:
                st.sidebar.success(f"Imported {added} new project(s)!")
    except Exception as e:
        st.sidebar.error("Invalid JSON file.")

# Clear saved projects
if st.session_state.saved_ideas:
    if st.sidebar.button("🗑️ Clear All Saved", use_container_width=True):
        st.session_state.saved_ideas = []
        st.rerun()

# --- Helper: Unified API Dispatcher ---
def call_llm(system_prompt, user_payload, provider, api_key, expect_json=True):
    if "OpenAI" in provider:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        kwargs = {
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_payload}
            ]
        }
        if expect_json:
            kwargs["response_format"] = {"type": "json_object"}
        response = client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        return json.loads(content) if expect_json else content

    elif "Anthropic" in provider:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        sys_msg = system_prompt
        if expect_json:
            sys_msg += "\nEnsure output is raw valid JSON starting with { or [ and ending with } or ]."
        response = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=4000,
            system=sys_msg,
            messages=[{"role": "user", "content": user_payload}]
        )
        content = response.content[0].text.strip()
        if expect_json:
            if content.startswith("```json"):
                content = content[7:-3].strip()
            return json.loads(content)
        return content

    elif "Google" in provider:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        config = {"response_mime_type": "application/json"} if expect_json else {}
        model = genai.GenerativeModel("gemini-1.5-pro", generation_config=config)
        response = model.generate_content(f"{system_prompt}\n\n{user_payload}")
        return json.loads(response.text) if expect_json else response.text

# --- Helper: Idea Generator ---
def generate_ideas(prompt, constraints, num_ideas, provider, api_key):
    system_prompt = (
        "You are an expert venture architect, hardware engineer, and senior technical program manager. "
        "Your task is to take a seed idea and user constraints, synthesize them, and return deeply detailed project concepts. "
        f"You must generate exactly {num_ideas} unique idea(s). "
        "Score each idea on a recommendation scale of 0 to 100 based on feasibility, novelty, ROI, and alignment with constraints. "
        "Rank the output array so the highest-scoring idea comes first.\n\n"
        "Return strictly valid JSON with an 'ideas' array where each object has these exact keys:\n"
        "- title (string)\n"
        "- score (integer from 0 to 100)\n"
        "- score_justification (string explaining why it received this score)\n"
        "- description (string, 3-4 comprehensive sentences)\n"
        "- system_architecture (string describing hardware/software components, protocols, and data pipeline)\n"
        "- tech_stack (list of strings)\n"
        "- hardware_bom (list of objects with keys 'item', 'purpose', and 'est_cost') listing all physical components, sensors, microcontrollers, 3D printing filament, tooling, etc.\n"
        "- software_cloud_budget (string detailing cloud compute, API token usage, third-party software, and subscriptions)\n"
        "- total_estimated_cost (string summarizing the total budget range from prototype to MVP)\n"
        "- monthly_timeline (list of objects with keys 'month' and 'milestones', detailing a realistic month-by-month progression covering design, CAD/BOM, embedded firmware, API integration, bench testing, and field pilot/MVP)\n"
        "- pros (list of strings, minimum 3)\n"
        "- cons (list of strings, minimum 3)\n"
        "- market_analysis (string evaluating target audience, direct/indirect competitors, and unique value proposition)"
    )

    user_payload = f"""
    Seed Concept/Problem: {prompt}
    Constraints:
    - Budget Limit: {constraints['budget']}
    - Target Technologies: {', '.join(constraints['tech']) if constraints['tech'] else 'Any'}
    - Target Difficulty: {constraints['difficulty']}
    - Target Timeline: {constraints['timeline']}
    - Number of Ideas: {num_ideas}
    """
    res = call_llm(system_prompt, user_payload, provider, api_key, expect_json=True)
    return res.get("ideas", res) if isinstance(res, dict) else res

# --- Main Navigation Tabs ---
tab_generate, tab_saved = st.tabs(["🚀 Ideation Engine", f"📁 Bookmarked Ideas ({len(st.session_state.saved_ideas)})"])

# ================= TAB 1: GENERATE =================
with tab_generate:
    with st.form("ideation_form"):
        user_prompt = st.text_area(
            "What is your seed idea or target problem?",
            placeholder="e.g., A smart precision irrigation system using embedded soil sensors and local edge ML to detect plant stress..."
        )

        col1, col2 = st.columns(2)
        with col1:
            tech_options = st.multiselect(
                "Target Technologies",
                ["AI / Machine Learning", "LLMs / Generative AI", "Embedded Systems / IoT", "3D Printing & Rapid Prototyping", "Robotics", "Web / Mobile App", "Computer Vision", "AR / VR"],
                default=["AI / Machine Learning", "Embedded Systems / IoT"]
            )
            budget = st.select_slider(
                "Budget Constraint",
                options=["< $100 (Hobbyist)", "$100 - $500", "$500 - $2,000", "$2,000 - $10,000", "$10,000+ (Commercial Demo)"],
                value="$100 - $500"
            )

        with col2:
            difficulty = st.select_slider(
                "Target Difficulty",
                options=["Beginner", "Intermediate", "Advanced", "Enterprise / Industrial Grade"],
                value="Intermediate"
            )
            timeline = st.selectbox(
                "Timeline Range",
                ["Weekend Hackathon (< 48 hrs)", "1 - 2 Months", "3 - 4 Months", "6 Months", "12 Months"]
            )
            num_ideas = st.slider("Number of Ideas to Generate", min_value=1, max_value=3, value=2)

        submit = st.form_submit_button("🚀 Generate & Rank Concepts", use_container_width=True)

    if submit:
        if not api_key:
            st.error("Please enter an API key in the sidebar.")
        elif not user_prompt.strip():
            st.warning("Please provide a seed idea or problem prompt.")
        else:
            with st.spinner("Analyzing hardware bills of materials, month-by-month roadmaps, and market viability..."):
                constraints = {
                    "budget": budget,
                    "tech": tech_options,
                    "difficulty": difficulty,
                    "timeline": timeline
                }
                try:
                    ideas = generate_ideas(user_prompt, constraints, num_ideas, provider, api_key)
                    st.session_state.ideas = sorted(ideas, key=lambda x: x.get("score", 0), reverse=True)
                    st.session_state.elaborations = {}
                    st.rerun()
                except Exception as e:
                    st.error(f"Error generating ideas: {str(e)}")

    # --- Display Generated Ideas ---
    if st.session_state.ideas:
