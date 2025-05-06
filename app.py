# app.py

from flask import Flask, request, jsonify, render_template, redirect
import fitz
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import os
from werkzeug.utils import secure_filename
import re
import spacy
from pdfminer.high_level import extract_text

app = Flask(__name__)

UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/recruiter')
def recruiter():
    return render_template('recruiter.html')

@app.route('/applicant')
def applicant():
    return render_template('applicant.html')

# Extract name (first PERSON entity)
def extract_name(doc):
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            return ent.text
    return None

# Extract email
def extract_email(text):
    match = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    return match[0] if match else None

# Extract phone number
def extract_phone(text):
    match = re.findall(r"[\+]?[\d\s\-()]{10,}", text)
    return match[0] if match else None

# Extract skills
def extract_skills(text):
    SKILLS_DB = ["python", "java", "mysql", "c++", "c", "html", "css", "javascript",
                 "react", "node.js", "mongodb", "express", "tensorflow", "keras", "git"]
    return [skill for skill in SKILLS_DB if skill.lower() in text.lower()]

# Extract degrees
def extract_degrees(text):
    DEGREE_KEYWORDS = ['b.tech', 'm.tech', 'bachelor', 'master', 'b.sc', 'm.sc', 'mba', 'phd']
    return [degree for degree in DEGREE_KEYWORDS if degree in text.lower()]

# Extract experience
def extract_experience(text):
    experience_lines = [line for line in text.split('\n') if 'experience' in line.lower()]
    return experience_lines

# Extract projects
def extract_projects(text):
    project_lines = [line.strip() for line in text.split('\n') if 'project' in line.lower()]
    return project_lines

@app.route('/applicant_analyse', methods=['POST'])
def applicant_analyse():
    # Extract data from form
    job_description = request.form['jobDescription']
    resume_file = request.files.get('resumeFile')

    # Step 1: Collect and process all resume texts
    if resume_file:
        filename = secure_filename(resume_file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        # resume_file.save(file_path)

        resume_text = ""
        doc = fitz.open(file_path)
        for page in doc:
            resume_text += page.get_text()
        resume_data = [resume_text]

        # Step 2: Compute embeddings
        model = SentenceTransformer('all-MiniLM-L6-v2')
        jd_embedding = model.encode([job_description])[0]
        resume_embeddings = model.encode(resume_data)

        # Step 3: Load spaCy model
        nlp = spacy.load("en_core_web_sm")
        file_path = file_path
        text = extract_text(file_path)
        # NLP doc
        doc = nlp(text)

        parsed_data = {
            "Name": extract_name(doc),
            "Email": extract_email(text),
            "Phone": extract_phone(text),
            "Skills": extract_skills(text),
            "Degrees": extract_degrees(text),
            "Experience": extract_experience(text),
            "Projects": extract_projects(text)
        }

        # Step 4: Compute cosine similarities
        similarities = cosine_similarity([jd_embedding], resume_embeddings)[0]

        # Step 5: Calculating the resume score
        resume_score = round(similarities[0] * 100, 2)  # Convert to percentage

        # Step 6: Generate feedback messages based on parsed_data
        filled_fields = [key for key, value in parsed_data.items() if value]
        missing_fields = [key for key, value in parsed_data.items() if not value]

        feedback = ""
        if filled_fields:
            feedback += "✅ Good that you included: <strong>" + ", ".join(filled_fields) + "</strong>.<br>"
        if missing_fields:
            feedback += "💡 Consider adding more information regarding <strong>" + ", ".join(missing_fields) + "</strong> to make your resume stronger."

        # Step 7: Returning the data to the HTML page.
        return render_template(
            'applicant.html',
            name=parsed_data['Name'],
            score=resume_score,
            resume_path=f'uploads/{filename}',
            feedback=feedback
        )
    
    return render_template('applicant.html', score="No resume uploaded.")

@app.route('/recuiter_analyse', methods=['POST'])
def recuiter_analyse():
    # Extract data from form
    job_description = request.form['jobDescription']
    resume_count = int(request.form['resumeCount'])

    resume_texts = []
    # Step 1: Collect and process all resume texts
    for i in range(1, resume_count + 1):
        resume_file = request.files.get(f'resumeFile{i}')
        if resume_file:
            filename = secure_filename(resume_file.filename)
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            # resume_file.save(file_path)
            # Extract text using PyMuPDF
            resume_text = ""
            try:
                doc = fitz.open(file_path)
                for page in doc:
                    resume_text += page.get_text()
                doc.close()
                resume_texts.append(resume_text)
            except Exception as e:
                print(f"Error reading resume {filename}: {e}")
    
    # Step 2: Ensure we have valid resume texts
    if not resume_texts:
        # flash("No valid resumes were uploaded.")
        return redirect(request.url)

    # Step 3: Compute embeddings
    model = SentenceTransformer('all-MiniLM-L6-v2')
    jd_embedding = model.encode([job_description])
    resume_embeddings = model.encode(resume_texts)

    # Step 4: Compute cosine similarities
    similarities = cosine_similarity(jd_embedding, resume_embeddings)[0]

    # Step 5: Rank resumes
    ranked_resumes = sorted(list(enumerate(similarities)), key=lambda x: x[1], reverse=True)

    # Step 6: Returning the data to the HTML page.
    return render_template("recruiter.html", ranked_resumes=ranked_resumes)

if __name__ == "__main__":
    app.run(debug=True)