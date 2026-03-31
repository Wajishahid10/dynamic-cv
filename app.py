import streamlit as st
import json
import os
import subprocess
import google.generativeai as genai
from ddgs import DDGS

# --- PAGE CONFIG ---
st.set_page_config(page_title="AI Resume Tailor", page_icon="📄", layout="centered")

# --- INITIALIZE SESSION STATE & SECRETS ---
# Configure Gemini
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# Load default CV from secrets into session state if it doesn't exist
if "cv_data" not in st.session_state:
    try:
        st.session_state.cv_data = json.loads(st.secrets["DEFAULT_CV"], strict=False)
    except KeyError:
        st.session_state.cv_data = {}
        st.warning("No DEFAULT_CV found in Streamlit Secrets. Please upload a JSON file.")

# --- UTILITY FUNCTIONS ---
def get_company_info(company_name):
    """Fetches company mission/news using DuckDuckGo."""
    if not company_name:
        return "No company name provided."
    try:
        results = DDGS().text(f"{company_name} company core values mission recent news", max_results=3)
        return "\n".join([r['body'] for r in results]) if results else "No specific info found."
    except Exception as e:
        return f"Could not fetch company info: {e}"

def escape_latex(text):
    """Escapes special LaTeX characters to prevent compilation errors."""
    if not isinstance(text, str):
        return text
    chars = {'&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#', '_': r'\_', '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}
    for k, v in chars.items():
        text = text.replace(k, v)
    return text

def tailor_cv_with_ai(base_cv, jd, company_info):
    """Uses Gemini 1.5 Flash to tailor the CV and returns a JSON object."""
    model = genai.GenerativeModel(
        'gemini-1.5-flash', 
        generation_config={"response_mime_type": "application/json"}
    )
    
    prompt = f"""
    You are an expert ATS-friendly resume writer. Your task is to take the candidate's Base CV (JSON format) 
    and tailor it to the provided Job Description and Company Research.
    
    Rules:
    1. Output strictly valid JSON matching the exact schema of the Base CV.
    2. Keep only the most relevant skills and projects for this specific job. 
    3. Rewrite experience bullet points to match keywords from the Job Description and align with the company's core values.
    4. Keep it concise enough to fit on a single page.
    
    Base CV: {json.dumps(base_cv)}
    Job Description: {jd}
    Company Research: {company_info}
    """
    
    response = model.generate_content(prompt)
    return json.loads(response.text)

def generate_latex_content(cv_json):
    """Generates the Jake's Resume LaTeX string from the JSON data."""
    basics = cv_json.get("basics", {})
    name = escape_latex(basics.get("name", ""))
    phone = escape_latex(basics.get("phone", ""))
    email = escape_latex(basics.get("email", ""))
    
    # Extract LinkedIn/GitHub links
    linkedin = ""
    github = ""
    for profile in basics.get("profiles", []):
        if profile["network"].lower() == "linkedin":
            linkedin = escape_latex(profile["url"])
        elif profile["network"].lower() in ["github", "trailhead"]:
            github = escape_latex(profile["url"])

    # Jake's Resume Preamble
    latex = r"""
\documentclass[letterpaper,11pt]{article}
\usepackage{latexsym}
\usepackage[empty]{fullpage}
\usepackage{titlesec}
\usepackage{marvosym}
\usepackage[usenames,dvipsnames]{color}
\usepackage{verbatim}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}
\usepackage[english]{babel}
\usepackage{tabularx}
\pagestyle{fancy}
\fancyhf{} 
\fancyfoot{}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}
\addtolength{\oddsidemargin}{-0.5in}
\addtolength{\evensidemargin}{-0.5in}
\addtolength{\textwidth}{1in}
\addtolength{\topmargin}{-.5in}
\addtolength{\textheight}{1.0in}
\urlstyle{same}
\raggedbottom
\raggedright
\setlength{\tabcolsep}{0in}
\titleformat{\section}{\vspace{-4pt}\scshape\raggedright\large}{}{0em}{}[\color{black}\titlerule \vspace{-5pt}]
\newcommand{\resumeItem}[1]{\item\small{#1 \vspace{-2pt}}}
\newcommand{\resumeSubheading}[4]{
  \vspace{-2pt}\item
    \begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}
      \textbf{#1} & #2 \\
      \textit{\small#3} & \textit{\small #4} \\
    \end{tabular*}\vspace{-7pt}
}
\newcommand{\resumeProjectHeading}[2]{
    \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \small#1 & #2 \\
    \end{tabular*}\vspace{-7pt}
}
\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.15in, label={}]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}
\newcommand{\resumeItemListStart}{\begin{itemize}}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}
\begin{document}
"""
    # Header
    latex += rf"""
\begin{{center}}
    \textbf{{\Huge \scshape {name}}} \\ \vspace{{1pt}}
    \small {phone} $|$ \href{{mailto:{email}}}{{\underline{{{email}}}}} $|$ 
    \href{{https://{linkedin}}}{{\underline{{{linkedin}}}}} $|$
    \href{{https://{github}}}{{\underline{{{github}}}}}
\end{{center}}
"""
    
    # Experience
    if cv_json.get("experience"):
        latex += r"\section{Experience}" + "\n" + r"\resumeSubHeadingListStart" + "\n"
        for exp in cv_json["experience"]:
            latex += rf"\resumeSubheading{{{escape_latex(exp.get('position'))}}}{{{escape_latex(exp.get('startDate'))} -- {escape_latex(exp.get('endDate'))}}}{{{escape_latex(exp.get('company'))}}}{{{escape_latex(exp.get('location'))}}}" + "\n"
            latex += r"\resumeItemListStart" + "\n"
            for highlight in exp.get("highlights", []):
                latex += rf"\resumeItem{{{escape_latex(highlight)}}}" + "\n"
            latex += r"\resumeItemListEnd" + "\n"
        latex += r"\resumeSubHeadingListEnd" + "\n"

    # Projects
    if cv_json.get("projects"):
        latex += r"\section{Projects}" + "\n" + r"\resumeSubHeadingListStart" + "\n"
        for proj in cv_json["projects"]:
            tech = escape_latex(", ".join(proj.get("technologies", [])))
            latex += rf"\resumeProjectHeading{{\textbf{{{escape_latex(proj.get('name'))}}} $|$ \emph{{{tech}}}}}{{{escape_latex(proj.get('date'))}}}" + "\n"
            latex += r"\resumeItemListStart" + "\n"
            for highlight in proj.get("highlights", []):
                latex += rf"\resumeItem{{{escape_latex(highlight)}}}" + "\n"
            latex += r"\resumeItemListEnd" + "\n"
        latex += r"\resumeSubHeadingListEnd" + "\n"

    # Skills
    if cv_json.get("skills"):
        latex += r"\section{Technical Skills}" + "\n" + r"\begin{itemize}[leftmargin=0.15in, label={}]" + "\n" + r"\small{\item{" + "\n"
        for skill in cv_json["skills"]:
            keywords = escape_latex(", ".join(skill.get("keywords", [])))
            latex += rf"\textbf{{{escape_latex(skill.get('category'))}}}{{: {keywords} \\}}" + "\n"
        latex += r"}}" + "\n" + r"\end{itemize}" + "\n"

    latex += r"\end{document}"
    return latex

def compile_latex(tex_content, output_filename="resume"):
    """Writes the .tex file and compiles it to PDF using pdflatex."""
    with open(f"{output_filename}.tex", "w", encoding="utf-8") as f:
        f.write(tex_content)
    
    try:
        # Run pdflatex twice for proper formatting/references
        subprocess.run(["pdflatex", "-interaction=nonstopmode", f"{output_filename}.tex"], check=True, stdout=subprocess.DEVNULL)
        return f"{output_filename}.pdf"
    except subprocess.CalledProcessError as e:
        st.error(f"LaTeX Compilation Failed: Check your LaTeX syntax. {e}")
        return None

# --- UI LAYOUT ---
st.title("📄 AI ATS Resume Tailor")
st.markdown("Upload a new base CV for this session, or use the default one stored in your secrets.")

# File Uploader to override session state
uploaded_file = st.file_uploader("Upload Temporary CV (JSON)", type=["json"])
if uploaded_file is not None:
    try:
        st.session_state.cv_data = json.load(uploaded_file)
        st.success("Temporary CV loaded successfully for this session!")
    except json.JSONDecodeError:
        st.error("Invalid JSON file format.")

st.divider()

# Input Form
with st.form("resume_form"):
    company_name = st.text_input("Company Name (for background research)")
    job_description = st.text_area("Paste Job Description Here", height=200)
    submitted = st.form_submit_button("Generate Tailored CV")

if submitted:
    if not job_description:
        st.error("Please provide a Job Description.")
    elif not st.session_state.cv_data:
        st.error("No CV data found. Check your secrets or upload a JSON file.")
    else:
        with st.spinner("Researching company & tailoring CV with Gemini..."):
            # 1. Research
            company_info = get_company_info(company_name)
            
            # 2. Tailor with LLM
            try:
                tailored_cv_json = tailor_cv_with_ai(st.session_state.cv_data, job_description, company_info)
                
                # 3. Generate LaTeX
                st.info("Compiling LaTeX to PDF...")
                latex_code = generate_latex_content(tailored_cv_json)
                pdf_file = compile_latex(latex_code)
                
                if pdf_file and os.path.exists(pdf_file):
                    st.success("Resume generated successfully!")
                    
                    # Read PDF for download
                    with open(pdf_file, "rb") as f:
                        pdf_bytes = f.read()
                    
                    st.download_button(
                        label="⬇️ Download ATS PDF Resume",
                        data=pdf_bytes,
                        file_name=f"{company_name.replace(' ', '_')}_Resume.pdf",
                        mime="application/pdf"
                    )
            except Exception as e:
                st.error(f"An error occurred during generation: {e}")