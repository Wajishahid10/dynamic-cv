import streamlit as st
import google.generativeai as genai
from duckduckgo_search import DDGS
import json
import subprocess
import os

# --- PAGE CONFIG ---
st.set_page_config(page_title="AI Resume Tailor", page_icon="📄", layout="centered")

# --- FUNCTIONS ---
def get_company_research(company_name):
    """Fetches recent news and core values using DuckDuckGo."""
    try:
        results = DDGS().text(f"{company_name} company core values mission recent news", max_results=3)
        research = "\n".join([res['body'] for res in results])
        return research
    except Exception as e:
        return f"Could not fetch research: {e}"

def generate_latex_resume(api_key, master_json, jd, company_info):
    """Calls Gemini 1.5 Flash to generate the LaTeX code."""
    genai.configure(api_key=api_key)
    # Gemini 1.5 Flash is highly capable and heavily featured in the free tier
    model = genai.GenerativeModel('gemini-1.5-flash') 
    
    prompt = f"""
    You are an expert technical recruiter and resume writer. 
    I will provide my master resume data (JSON), a Job Description, and Company Research.
    
    Your task:
    1. Select ONLY the skills and projects from my JSON that are highly relevant to the Job Description.
    2. Rewrite my project bullets to naturally include keywords from the JD and align with the company's culture.
    3. Output the final customized resume STRICTLY as raw LaTeX code based on the famous "Jake's Resume" template.
    4. DO NOT wrap the output in markdown blocks (e.g., ```latex). Start directly with \documentclass.
    
    Master Data: {json.dumps(master_json)}
    Job Description: {jd}
    Company Research: {company_info}
    """
    
    response = model.generate_content(prompt)
    
    # Clean up any potential markdown formatting the LLM might stubbornly include
    latex_code = response.text.strip()
    if latex_code.startswith("```latex"):
        latex_code = latex_code[8:]
    if latex_code.endswith("```"):
        latex_code = latex_code[:-3]
        
    return latex_code

def compile_latex_to_pdf(latex_code):
    """Saves LaTeX to a file and compiles it using pdflatex."""
    with open("resume.tex", "w", encoding="utf-8") as f:
        f.write(latex_code)
    
    # Run pdflatex command (requires texlive installed on the system/cloud)
    process = subprocess.run(
        ['pdflatex', '-interaction=nonstopmode', 'resume.tex'],
        capture_output=True, text=True
    )
    
    if os.path.exists("resume.pdf"):
        with open("resume.pdf", "rb") as f:
            pdf_bytes = f.read()
        return pdf_bytes, None
    else:
        return None, process.stdout # Return error logs if compilation fails

# --- UI LAYOUT ---
st.title("📄 AI ATS Resume Generator")
st.markdown("Tailor your baseline resume to a specific job description instantly.")

# Sidebar for Setup
with st.sidebar:
    st.header("⚙️ Configuration")
    gemini_api_key = ""
    try:
        gemini_api_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        gemini_api_key = st.text_input("Gemini API Key", type="password", help="Get this free from Google AI Studio")
        # st.secrets.set("GEMINI_API_KEY", gemini_api_key)
    # gemini_api_key = st.text_input("Gemini API Key", type="password", help="Get this free from Google AI Studio")
    st.markdown("---")
    st.write("Load Master Data")
    uploaded_master = st.file_uploader("Upload master_data.json", type=["json"])

# Main Area for Job Inputs
company_name = st.text_input("Company Name", placeholder="e.g. Google, Stripe, Local Startup")
job_description = st.text_area("Job Description", height=200, placeholder="Paste the full job description here...")

if st.button("🚀 Generate Tailored Resume", type="primary"):
    if not gemini_api_key:
        st.error("Please enter your Gemini API Key in the sidebar.")
    elif not company_name or not job_description:
        st.error("Please provide both the Company Name and Job Description.")
    else:
        with st.status("Crafting your resume...", expanded=True) as status:
            
            # 1. Load Data
            st.write("Loading baseline skills...")
            if uploaded_master:
                master_data = json.load(uploaded_master)
            else:
                # Fallback to local file if not uploaded
                with open("master_data.json", "r") as f:
                    master_data = json.load(f)
            
            # 2. Research Company
            st.write(f"Researching {company_name} on the web...")
            company_research = get_company_research(company_name)
            
            # 3. Generate LaTeX
            st.write("Analyzing JD and writing LaTeX (this takes a few seconds)...")
            latex_code = generate_latex_resume(gemini_api_key, master_data, job_description, company_research)
            
            # 4. Compile PDF
            st.write("Compiling PDF...")
            pdf_bytes, error_logs = compile_latex_to_pdf(latex_code)
            
            if pdf_bytes:
                status.update(label="Resume Generated Successfully!", state="complete", expanded=False)
                
                st.success("Your highly tailored, ATS-friendly PDF is ready!")
                st.download_button(
                    label="📥 Download PDF Resume",
                    data=pdf_bytes,
                    file_name=f"Resume_{company_name.replace(' ', '_')}.pdf",
                    mime="application/pdf"
                )
                
                with st.expander("Show LaTeX Code (for Overleaf)"):
                    st.code(latex_code, language="latex")
            else:
                status.update(label="Compilation Failed", state="error")
                st.error("Failed to compile the LaTeX code into a PDF. The LLM might have generated invalid syntax.")
                with st.expander("View Compiler Error Logs"):
                    st.text(error_logs)
                with st.expander("View Generated LaTeX Code"):
                    st.code(latex_code, language="latex")