import streamlit as st
import json

st.set_page_config(page_title="AI Ideation Studio", page_icon="💡", layout="wide")

# Initialize session state for generated ideas
if "ideas" not in st.session_state:
    st.session_state.ideas = None
if "elaborations" not in st.session_state:
    st.session_state.elaborations = {}

st.title("💡 AI-Powered Ideation & Evaluation Studio")
st.markdown("Generate scored project concepts with market validation, risk analysis, and deep-dive elaboration.")

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

# --- Helper: Unified API Dispatcher ---
def call_llm(system_prompt, user_payload, provider, api_key, expect_json=True):
    if "OpenAI" in provider:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        kwargs = {"model": "gpt-4o", "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_payload}]}
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
        "You are an expert venture architect, product manager, and senior systems engineer. "
        "Your task is to take a seed idea and user constraints, synthesize them, and return comprehensive project concepts. "
        f"You must generate exactly {num_ideas} unique idea(s). "
        "Score each idea on a recommendation scale of 0 to 100 based on feasibility, novelty, ROI, and alignment with constraints. "
        "Rank the output array so the highest-scoring idea comes first.\n\n"
        "Return strictly valid JSON with an 'ideas' array where each object has these exact keys:\n"
        "- title (string)\n"
        "- score (integer from 0 to 100)\n"
        "- score_justification (string explaining why it received this score)\n"
        "- description (string, 3-4 comprehensive sentences)\n"
        "- system_architecture (string describing components, protocols, and data flow)\n"
        "- tech_stack (list of strings)\n"
        "- estimated_budget (string, line-item breakdown of prototype vs scaling costs)\n"
        "- difficulty_and_timeline (string, milestones breakdown)\n"
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

# --- Main Ideation Form ---
with st.form("ideation_form"):
    user_prompt = st.text_area(
        "What is your seed idea or target problem?",
        placeholder="e.g., A low-cost IoT monitor for beehive health to detect colony collapse early..."
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
            ["Weekend Hackathon (< 48 hrs)", "1 - 2 Weeks", "1 Month", "3 - 6 Months", "6+ Months"]
        )
        num_ideas = st.slider("Number of Ideas to Generate", min_value=1, max_value=3, value=3)

    submit = st.form_submit_button("🚀 Generate & Rank Concepts", use_container_width=True)

if submit:
    if not api_key:
        st.error("Please enter an API key in the sidebar.")
    elif not user_prompt.strip():
        st.warning("Please provide a seed idea or problem prompt.")
    else:
        with st.spinner("Analyzing market, pricing components, and evaluating feasibility..."):
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

# --- Display Results & Interactive Elaboration ---
if st.session_state.ideas:
    st.divider()
    st.subheader(f"🏆 Top Ranked Concepts ({len(st.session_state.ideas)})")

    for idx, idea in enumerate(st.session_state.ideas, 1):
        score = int(idea.get("score", 75))
        
        with st.expander(f"#{idx} | {idea.get('title', 'Project Concept')} — Recommendation Score: {score}/100", expanded=True):
            st.progress(score / 100)
            st.caption(f"**Recommendation Analysis:** {idea.get('score_justification', 'Strong alignment with goals.')}")

            st.markdown("### 📌 Executive Summary")
            st.write(idea.get("description"))

            st.markdown("### ⚙️ System Architecture & Tech Stack")
            st.write(idea.get("system_architecture", "Custom architecture modular pipeline."))
            tech_badges = " ".join([f"`{t}`" for t in idea.get("tech_stack", [])])
            st.markdown(f"**Tech Stack:** {tech_badges}")

            c1, c2 = st.columns(2)
            with c1:
                st.info(f"**💰 Budget Plan:**\n\n{idea.get('estimated_budget')}")
            with c2:
                st.warning(f"**⏱️ Timeline & Effort:**\n\n{idea.get('difficulty_and_timeline')}")

            col_pro, col_con = st.columns(2)
            with col_pro:
                st.success("**✅ Pros / Advantages:**\n" + "\n".join([f"- {p}" for p in idea.get("pros", [])]))
            with col_con:
                st.error("**⚠️ Cons / Challenges & Risks:**\n" + "\n".join([f"- {c}" for c in idea.get("cons", [])]))

            st.markdown("### 📊 Market Analysis & Competitors")
            st.write(idea.get("market_analysis"))

            # --- Elaboration / Deep Dive Section ---
            st.divider()
            st.markdown(f"#### 🔍 Deep Dive into *{idea.get('title')}*")
            
            elaboration_query = st.text_input(
                f"Ask a specific question or request deeper specs for #{idx}:",
                placeholder="e.g., Provide a step-by-step Bill of Materials, or write the MVP backend architecture...",
                key=f"input_elab_{idx}"
            )
            
            if st.button(f"Elaborate on #{idx}", key=f"btn_elab_{idx}"):
                if not api_key:
                    st.error("API key required.")
                elif not elaboration_query.strip():
                    st.warning("Please specify what you want to elaborate on.")
                else:
                    with st.spinner("Generating detailed breakdown..."):
                        try:
                            sys_elab = (
                                "You are an expert technical advisor and product strategist. "
                                f"You are elaborating on this project: {idea.get('title')}.\n"
                                f"Project Context: {idea.get('description')}\n"
                                f"Tech Stack: {', '.join(idea.get('tech_stack', []))}\n"
                                "Provide an exhaustive, highly practical, and technically deep response to the user's inquiry."
                            )
                            elaboration_result = call_llm(
                                sys_elab,
                                elaboration_query,
                                provider,
                                api_key,
                                expect_json=False
                            )
                            st.session_state.elabor