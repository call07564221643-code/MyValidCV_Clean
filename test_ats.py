#!/usr/bin/env python
"""Test the ATS engine functionality"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.services import ats_engine

# Test 1: Valid CV and JD
cv_text = """
John Doe
john@example.com | (555) 123-4567

SUMMARY
Experienced software engineer with 5 years in Python, Django, and React development.

EXPERIENCE
Senior Developer at Tech Corp (2021-2024)
- Led team of 3 developers
- Built scalable Django REST APIs
- Implemented React frontend

SKILLS
Python, Django, JavaScript, React, PostgreSQL, Docker, AWS, Git

EDUCATION
B.S. Computer Science, University of Tech (2019)

CERTIFICATIONS
AWS Certified Solutions Architect
"""

jd_text = """
Senior Python Developer - Tech Startup

About the Role:
We're looking for an experienced Python developer to join our team.

Responsibilities:
- Build and maintain Django REST APIs
- Develop new features using Python
- Collaborate with frontend team using React
- Work with AWS infrastructure

Requirements:
- 5+ years Python experience
- Strong Django knowledge
- Experience with React preferred
- AWS experience required
- Bachelor's degree in Computer Science

Nice to Have:
- Docker experience
- AWS certifications
"""

result = ats_engine.analyse(cv_text, jd_text)

print("=" * 60)
print("ATS ENGINE TEST RESULTS")
print("=" * 60)
print(f"Success: {result['success']}")
if result['success']:
    data = result['data']
    print(f"\nOverall Score: {data['overall_score']}/100")
    print(f"ATS Score: {data['ats_score']}/100")
    print(f"Skills Match: {data['skills_score']}/100")
    print(f"Keywords Match: {data['keywords_score']}/100")
    print(f"Experience Score: {data['experience_score']}/100")
    print(f"Qualification Score: {data['qualification_score']}/100")
    print(f"\nMatched Skills: {len(data['matched_skills'])} - {', '.join(data['matched_skills'][:5])}")
    print(f"Missing Skills: {len(data['missing_skills'])} - {', '.join(data['missing_skills'][:3])}")
    print(f"\nCV Confidence: {data['cv_confidence']}%")
    print(f"Job Description Confidence: {data['job_confidence']}%")
else:
    print(f"Error: {result['error']}")

print("\n" + "=" * 60)
print("✓ ATS Engine Test Passed!")
print("=" * 60)
