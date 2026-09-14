import streamlit as st
import json
import os

SAVED_FILE = "saved_ideas.json"

def load_persisted_ideas():
    if os.path.exists(SAVED_FILE):
        try:
            with open(SAVED_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_persisted_ideas(ideas_list):
    try:
        with open(SAVED_FILE, "w") as f:
            json.dump(ideas_list, f, indent=2)
    except Exception as e:
        st.error(f"Failed to persist bookmarks: {e}")

# Page Setup
st.set_page_config(page_title="AI Ideation Studio", page_icon="💡", layout="wide")

# Initialize session state
if "ideas" not in st.session_state:
    st.session_state.ideas = None
if "elaborations" not in st.session_state:
    st.session_state.elaborations = {}
if "saved_ideas" not in st.session_state:
    st.session_state.saved_ideas = load_persisted_ideas()

st.title("💡 AI-Powered Ideation & Evaluation Studio")
st.markdown("Generate scored project concepts with market validation, granular hardware/cloud budgets, month-by-month roadmaps, and persistent bookmarks.")

# --- Sidebar: Model & API Configuration ---
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
            current_titles = {i.get("title") for i in st.session_state.saved_ideas}
            added = 0
            for item in imported_ideas:
                if item.get("title") not in current_titles:
                    st.session_state.saved_ideas.append(item)
                    added += 1
            if added > 0:
                save_persisted_ideas(st.session_state.saved_ideas)
                st.sidebar.success(f"Imported {added} new project(s)!")
    except Exception:
        st.sidebar.error("Invalid JSON file.")

# Clear saved projects
if st.session_state.saved_ideas:
    if st.sidebar.button("🗑️ Clear All Saved", use_container_width=True):
        st.session_state.saved_ideas = []
        save_persisted_ideas([])
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
        "- total_estimated_cost (string summarizing the total budget range from prototype to MVP in USD)\n"
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
            budget_limit = st.slider(
                "Maximum Budget Limit (USD)",
                min_value=50,
                max_value=10000,
                value=500,
                step=50,
                format="$%d USD",
                help="Set the strict upper spending limit in US Dollars for prototype materials, tooling, and cloud compute."
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
                    "budget": f"Strict maximum cap of ${budget_limit:,} USD",
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
        st.divider()
        st.subheader(f"🏆 Top Ranked Concepts ({len(st.session_state.ideas)})")

        for idx, idea in enumerate(st.session_state.ideas, 1):
            score = int(idea.get("score", 75))
            
            with st.expander(f"#{idx} | {idea.get('title', 'Project Concept')} — Recommendation Score: {score}/100", expanded=True):
                top_cols = st.columns([4, 1])
                with top_cols[0]:
                    st.progress(score / 100)
                    st.caption(f"**Recommendation Analysis:** {idea.get('score_justification', 'Strong alignment with requirements.')}")
                with top_cols[1]:
                    is_saved = any(s.get("title") == idea.get("title") for s in st.session_state.saved_ideas)
                    if is_saved:
                        if st.button("⭐ Saved", key=f"save_btn_{idx}", use_container_width=True):
                            st.session_state.saved_ideas = [s for s in st.session_state.saved_ideas if s.get("title") != idea.get("title")]
                            save_persisted_ideas(st.session_state.saved_ideas)
                            st.rerun()
                    else:
                        if st.button("🔖 Bookmark", key=f"save_btn_{idx}", use_container_width=True):
                            st.session_state.saved_ideas.append(idea)
                            save_persisted_ideas(st.session_state.saved_ideas)
                            st.rerun()

                st.markdown("### 📌 Executive Summary")
                st.write(idea.get("description"))

                st.markdown("### ⚙️ System Architecture & Tech Stack")
                st.write(idea.get("system_architecture", "Modular architecture integrating edge hardware and cloud software."))
                tech_badges = " ".join([f"`{t}`" for t in idea.get("tech_stack", [])])
                st.markdown(f"**Tech Stack:** {tech_badges}")

                # --- Budget & BOM Breakdown ---
                st.markdown("### 💰 Comprehensive Budget & Hardware BOM")
                st.info(f"**Estimated Total Cost:** {idea.get('total_estimated_cost', 'N/A')}")
                
                hardware_items = idea.get("hardware_bom", [])
                if hardware_items:
                    st.markdown("#### 🛠️ Potential Hardware & Material Requirements (BOM)")
                    bom_table = "| Item / Component | Purpose | Estimated Cost |\n|---|---|---|\n"
                    for item in hardware_items:
                        bom_table += f"| {item.get('item', 'N/A')} | {item.get('purpose', 'N/A')} | {item.get('est_cost', 'N/A')} |\n"
                    st.markdown(bom_table)
                
                st.markdown(f"**Cloud, Tooling & Subscriptions:**\n\n{idea.get('software_cloud_budget', 'N/A')}")

                # --- Timeline & Month-by-Month Progression ---
                st.markdown("### 📅 Month-by-Month Execution Roadmap")
                monthly_plan = idea.get("monthly_timeline", [])
                if monthly_plan:
                    for phase in monthly_plan:
                        st.markdown(f"- **{phase.get('month', 'Phase')}**: {phase.get('milestones', '')}")
                else:
                    st.write(idea.get("difficulty_and_timeline", "Iterative agile rollout."))

                # --- Pros & Cons ---
                col_pro, col_con = st.columns(2)
                with col_pro:
                    st.success("**✅ Pros / Strategic Advantages:**\n" + "\n".join([f"- {p}" for p in idea.get("pros", [])]))
                with col_con:
                    st.error("**⚠️ Cons / Technical & Supply Risks:**\n" + "\n".join([f"- {c}" for c in idea.get("cons", [])]))

                st.markdown("### 📊 Market Analysis & Competitor Landscape")
                st.write(idea.get("market_analysis"))

                # --- Elaboration / Deep Dive Section ---
                st.divider()
                st.markdown(f"#### 🔍 Deep Dive into *{idea.get('title')}*")
                
                elaboration_query = st.text_input(
                    f"Ask a specific follow-up or request deeper specs for #{idx}:",
                    placeholder="e.g., Provide the wiring diagram / pinouts for the sensors, or draft the firmware state machine...",
                    key=f"input_elab_{idx}"
                )
                
                if st.button(f"Elaborate on #{idx}", key=f"btn_elab_{idx}"):
                    if not api_key:
                        st.error("API key required.")
                    elif not elaboration_query.strip():
                        st.warning("Please specify what you want to elaborate on.")
                    else:
                        with st.spinner("Generating deep technical breakdown..."):
                            try:
                                sys_elab = (
                                    "You are an expert technical advisor and systems engineer. "
                                    f"You are elaborating on this project: {idea.get('title')}.\n"
                                    f"Project Context: {idea.get('description')}\n"
                                    f"Tech Stack: {', '.join(idea.get('tech_stack', []))}\n"
                                    "Provide an exhaustive, highly practical, and technically deep response with schematics logic, code snippets, or supplier advice where relevant."
                                )
                                elaboration_result = call_llm(
                                    sys_elab,
                                    elaboration_query,
                                    provider,
                                    api_key,
                                    expect_json=False
                                )
                                st.session_state.elaborations[f"{idx}_{elaboration_query}"] = elaboration_result
                            except Exception as e:
                                st.error(f"Error elaborating: {str(e)}")

                for key, response_text in st.session_state.elaborations.items():
                    if key.startswith(f"{idx}_"):
                        question_asked = key.split(f"{idx}_", 1)[1]
                        with st.chat_message("user"):
                            st.write(question_asked)
                        with st.chat_message("assistant"):
                            st.markdown(response_text)

# ================= TAB 2: SAVED IDEAS =================
with tab_saved:
    if not st.session_state.saved_ideas:
        st.info("No ideas bookmarked yet. Click the '🔖 Bookmark' button on any generated concept to save it here.")
    else:
        st.subheader(f"📌 Your Bookmarked Projects ({len(st.session_state.saved_ideas)})")
        for s_idx, s_idea in enumerate(st.session_state.saved_ideas, 1):
            with st.expander(f"📁 {s_idea.get('title')} — Score: {s_idea.get('score')}/100", expanded=False):
                col_del, _ = st.columns([1, 5])
                with col_del:
                    if st.button("❌ Remove from Bookmarks", key=f"del_saved_{s_idx}"):
                        st.session_state.saved_ideas.pop(s_idx - 1)
                        save_persisted_ideas(st.session_state.saved_ideas)
                        st.rerun()

                st.markdown(f"**Description:** {s_idea.get('description')}")
                st.markdown(f"**Total Budget:** {s_idea.get('total_estimated_cost')}")
                st.markdown(f"**Tech Stack:** {', '.join(s_idea.get('tech_stack', []))}")
                
                bom = s_idea.get("hardware_bom", [])
                if bom:
                    st.markdown("**Hardware BOM:**")
                    table = "| Item | Purpose | Cost |\n|---|---|---|\n"
                    for b in bom:
                        table += f"| {b.get('item')} | {b.get('purpose')} | {b.get('est_cost')} |\n"
                    st.markdown(table)

                st.markdown(f"**Market Analysis:** {s_idea.get('market_analysis')}")
