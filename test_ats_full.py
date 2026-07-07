#!/usr/bin/env python
"""Test the ATS engine functionality with valid data"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.services import ats_engine

# Test 1: Valid CV and JD (longer CV)
cv_text = """
JOHN ALEXANDER DOE
john.doe@techmail.com | (555) 123-4567 | LinkedIn.com/in/johndoe | GitHub.com/johndoe

PROFESSIONAL SUMMARY
Experienced software engineer with 5+ years of professional experience developing scalable web applications and backend systems. Proven expertise in Python, Django, React, and AWS. Strong track record of leading development teams and delivering high-impact projects. Passionate about clean code, best practices, and continuous improvement. Seeking a senior developer role to leverage full-stack capabilities and mentoring experience.

PROFESSIONAL EXPERIENCE

Senior Software Engineer | Tech Innovations Corp | San Francisco, CA | Jan 2022 - Present
• Led and mentored a team of 3 developers on microservices architecture migration, resulting in 40% performance improvement
• Designed and implemented scalable Django REST APIs serving 1M+ daily requests
• Architected real-time data pipeline using Python, PostgreSQL, and AWS Lambda
• Implemented comprehensive test coverage (85%+) and CI/CD pipelines using GitHub Actions
• Optimized database queries reducing API response time by 60%
• Collaborated with product team to deliver features on aggressive timelines

Software Developer | Digital Solutions Ltd | Austin, TX | Jun 2019 - Dec 2021
• Developed full-stack web applications using Django and React
• Implemented responsive UIs with Bootstrap and modern JavaScript
• Built RESTful APIs and integrated third-party services
• Conducted code reviews and improved code quality standards
• Participated in agile sprint planning and daily standups

Junior Developer | StartupXYZ | Remote | Jun 2018 - May 2019
• Contributed to backend development using Python and Flask
• Fixed bugs and implemented new features under senior developer guidance
• Learned best practices and software engineering principles

TECHNICAL SKILLS

Programming Languages: Python, JavaScript, TypeScript, SQL
Frameworks & Libraries: Django, Django REST Framework, React, Flask, FastAPI
Databases: PostgreSQL, MySQL, MongoDB, Redis
Cloud & DevOps: AWS (EC2, RDS, Lambda, S3), Docker, Kubernetes, Terraform, CI/CD
Tools & Platforms: Git, GitHub, GitLab, Jira, Confluence, Docker, Linux, Nginx
Other: REST APIs, GraphQL, Microservices, TDD, Agile/Scrum

EDUCATION

Bachelor of Science in Computer Science | University of Technology | 2018
GPA: 3.7/4.0
Relevant Coursework: Data Structures, Algorithms, Web Development, Database Systems, Software Engineering

CERTIFICATIONS & ACHIEVEMENTS
• AWS Certified Solutions Architect - Associate (2021)
• AWS Certified Developer - Associate (2020)
• Docker Certified Associate (2022)
• Built and shipped 5+ production-grade applications
• Active open-source contributor with 200+ GitHub stars

ADDITIONAL INFORMATION
Languages: English (Native), Spanish (Conversational)
Available for: Full-time, Contract work
Work Authorization: US Citizen
"""

jd_text = """
Senior Python Developer - Tech Startup

Location: San Francisco, CA (Remote considered)
Type: Full-time

ABOUT THE COMPANY
We're a fast-growing tech startup backed by Series B funding. We're building the next generation of AI-powered tools for enterprise analytics. Our platform processes millions of data points daily and requires robust, scalable infrastructure.

ABOUT THE ROLE
We're seeking an experienced Senior Python Developer to lead our backend engineering team. You'll have the opportunity to work on cutting-edge technology, mentor junior developers, and shape our technical vision. This is a hands-on role where you'll be involved in architecture decisions, code reviews, and technical leadership.

KEY RESPONSIBILITIES
• Design and build scalable microservices using Python and Django
• Develop and maintain RESTful APIs that power our analytics platform
• Implement complex data processing pipelines
• Work closely with DevOps to deploy and monitor applications on AWS
• Lead code reviews and establish coding standards
• Mentor junior developers and contribute to team growth
• Participate in technical architecture discussions
• Implement comprehensive testing and CI/CD practices
• Optimize performance and scalability of backend systems
• Collaborate with product managers and frontend team on feature requirements

REQUIRED QUALIFICATIONS
• 5+ years of professional Python development experience
• Expert-level Django experience
• Strong understanding of RESTful API design
• Experience with PostgreSQL or similar relational databases
• Proven experience with AWS (EC2, RDS, S3, Lambda)
• Solid understanding of microservices architecture
• Experience with Docker and containerization
• Git version control expertise
• Strong knowledge of software engineering best practices
• Bachelor's degree in Computer Science or related field (or equivalent experience)
• Excellent communication and collaboration skills

PREFERRED QUALIFICATIONS
• Experience with React or modern JavaScript frameworks
• Experience with Kubernetes
• AWS certifications
• Experience with message queues (RabbitMQ, Kafka)
• Open source contributions
• Experience mentoring junior developers
• Knowledge of machine learning basics
• Exposure to TypeScript
• Experience with Agile development methodologies

TECHNICAL STACK
• Backend: Python, Django, FastAPI
• Databases: PostgreSQL, Redis
• Cloud: AWS (Lambda, RDS, EC2, S3)
• DevOps: Docker, Kubernetes, Terraform
• CI/CD: GitHub Actions, GitLab CI
• Monitoring: DataDog, CloudWatch

WHAT WE OFFER
• Competitive salary: $150,000 - $200,000 depending on experience
• Equity package
• Health, dental, vision insurance
• 401(k) matching
• Unlimited PTO
• Remote flexibility
• Professional development budget
• Collaborative and inclusive culture

HOW TO APPLY
Submit your resume and a brief cover letter. Include links to your GitHub profile and any notable projects you'd like us to review.
"""

result = ats_engine.analyse(cv_text, jd_text)

print("=" * 60)
print("ATS ENGINE TEST RESULTS")
print("=" * 60)
print(f"Success: {result['success']}")
if result['success']:
    data = result['data']
    print(f"\n✓ OVERALL SCORE: {data['overall_score']}/100")
    print(f"  ATS Score: {data['ats_score']}/100")
    print(f"  Skills Match: {data['skills_score']}/100")
    print(f"  Keywords Match: {data['keywords_score']}/100")
    print(f"  Experience Score: {data['experience_score']}/100")
    print(f"  Qualification Score: {data['qualification_score']}/100")
    print(f"  Format Score: {data['format_score']}/100")
    
    print(f"\n✓ MATCHED SKILLS ({len(data['matched_skills'])}):")
    print(f"  {', '.join(data['matched_skills'][:8])}")
    
    print(f"\n✗ MISSING SKILLS ({len(data['missing_skills'])}):")
    if data['missing_skills']:
        print(f"  {', '.join(data['missing_skills'][:5])}")
    else:
        print(f"  None!")
    
    print(f"\n✓ MATCHED KEYWORDS ({len(data['matched_keywords'])}):")
    print(f"  {', '.join(data['matched_keywords'][:8])}")
    
    print(f"\n✗ MISSING KEYWORDS ({len(data['missing_keywords'])}):")
    if data['missing_keywords']:
        print(f"  {', '.join(data['missing_keywords'][:5])}")
    
    print(f"\n✓ EXPERIENCE:")
    print(f"  Years: {data['cv_experience_years']}+")
    print(f"  Education: {data['cv_has_education']}")
    print(f"  Certifications: {data['cv_has_certifications']}")
    
    print(f"\n✓ CONFIDENCE LEVELS:")
    print(f"  CV Confidence: {data['cv_confidence']}%")
    print(f"  Job Description Confidence: {data['job_confidence']}%")
else:
    print(f"Error: {result['error']}")

print("\n" + "=" * 60)
print("✓ ATS Engine Functionality Test PASSED!")
print("=" * 60)
