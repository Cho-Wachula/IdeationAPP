import streamlit as st
import json

# Page Setup
st.set_page_config(page_title="AI Ideation Studio", page_icon="💡", layout="wide")

st.title("💡 AI-Powered Ideation Studio")
st.markdown("Generate fleshed-out project concepts with budgets, market context, and technical feasibility.")

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
st.sidebar.caption("Keys are never stored persistently; they are only used for the active session.")

# --- Helper: Unified API Dispatcher ---
def generate_ideas(prompt, constraints, num_ideas, provider, api_key):
    system_prompt = (
        "You are an expert venture architect, hardware/software engineer, and product manager. "
        "Your task is to take a seed idea and user constraints, and return fully formed, realistic project concepts. "
        f"You must generate exactly {num_ideas} unique idea(s).\n\n"
        "Return strictly a valid JSON array of objects. Do not include markdown codeblocks or extra text. "
        "Each object must have these exact keys:\n"
        "- title (string)\n"
        "- description (string)\n"
        "- tech_stack (list of strings)\n"
        "- estimated_budget (string, detailing hardware/cloud/tooling costs)\n"
        "- difficulty_and_timeline (string)\n"
        "- market_analysis (string, analyzing existing products, competitors, and differentiation)"
    )

    user_payload = f"""
    Seed Concept/Prompt: {prompt}
    Constraints:
    - Budget Limit: {constraints['budget']}
    - Target Technologies: {', '.join(constraints['tech']) if constraints['tech'] else 'Any'}
    - Target Difficulty: {constraints['difficulty']}
    - Target Timeline: {constraints['timeline']}
    - Number of Ideas: {num_ideas}
    """

    if "OpenAI" in provider:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_payload}
            ],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        # Handle cases where model wraps the array in an outer dictionary
        return data.get("ideas", data) if isinstance(data, dict) else data

    elif "Anthropic" in provider:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=2500,
            system=system_prompt + " Ensure output is raw valid JSON starting with [ and ending with ].",
            messages=[{"role": "user", "content": user_payload}]
        )
        content = response.content[0].text.strip()
        if content.startswith("```json"):
            content = content[7:-3].strip()
        return json.loads(content)

    elif "Google" in provider:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-pro", generation_config={"response_mime_type": "application/json"})
        response = model.generate_content(f"{system_prompt}\n\n{user_payload}")
        return json.loads(response.text)

# --- Main Form ---
with st.form("ideation_form"):
    user_prompt = st.text_area("What is your seed idea or area of interest?", 
                               placeholder="e.g., A smart garden device that saves water, or an AI tool for independent screenwriters...")

    col1, col2 = st.columns(2)
    with col1:
        tech_options = st.multiselect(
            "Technologies / Domains",
            ["AI / Machine Learning", "LLMs / Generative AI", "Embedded Systems / IoT", "3D Printing & CAD", "Robotics", "Web / Mobile App", "Computer Vision", "AR / VR"],
            default=["AI / Machine Learning"]
        )
        budget = st.select_slider(
            "Budget Constraint",
            options=["< $100 (Hobby/Free Tier)", "$100 - $500", "$500 - $2,000", "$2,000 - $10,000", "$10,000+ (Commercial Prototype)"],
            value="$100 - $500"
        )

    with col2:
        difficulty = st.select_slider(
            "Difficulty Level",
            options=["Beginner", "Intermediate", "Advanced", "Production/Enterprise Ready"],
            value="Intermediate"
        )
        timeline = st.selectbox(
            "Timeline Range",
            ["Weekend Hackathon (< 48 hrs)", "1 - 2 Weeks", "1 Month", "3 - 6 Months", "6+ Months"]
        )
        num_ideas = st.slider("Number of Ideas to Generate", min_value=1, max_value=3, value=2)

    submit = st.form_submit_button("🚀 Generate Concepts", use_container_width=True)

# --- Handling Execution & Display ---
if submit:
    if not api_key:
        st.error("Please provide an API key in the sidebar to proceed.")
    elif not user_prompt.strip():
        st.warning("Please provide a seed idea or problem prompt.")
    else:
        with st.spinner("Brainstorming, calculating budgets, and compiling market research..."):
            constraints = {
                "budget": budget,
                "tech": tech_options,
                "difficulty": difficulty,
                "timeline": timeline
            }
            try:
                ideas = generate_ideas(user_prompt, constraints, num_ideas, provider, api_key)
                if isinstance(ideas, dict):
                    # Handle single object return or nested dictionary
                    ideas = ideas.get("ideas", [ideas])

                st.success(f"Generated {len(ideas)} project concepts!")

                for idx, idea in enumerate(ideas, 1):
                    with st.expander(f"📌 Idea {idx}: {idea.get('title', 'Untitled Project')}", expanded=True):
                        st.markdown(f"### Description\n{idea.get('description')}")
                        
                        cols = st.columns([1, 1, 1])
                        with cols[0]:
                            st.info(f"**Budget Details:**\n{idea.get('estimated_budget')}")
                        with cols[1]:
                            st.warning(f"**Timeline & Effort:**\n{idea.get('difficulty_and_timeline')}")
                        with cols[2]:
                            techs = ", ".join(idea.get('tech_stack', []))
                            st.success(f"**Tech Stack:**\n{techs}")

                        st.markdown("#### 📊 Market Analysis & Existing Solutions")
                        st.write(idea.get("market_analysis"))

            except Exception as e:
                st.error(f"An error occurred: {str(e)}")