"""Curated, auditable product knowledge used by Maya at request time."""

import re


def _topic(keywords, content, answer, followups=()):
    return {"keywords": tuple(keywords), "content": content, "answer": answer, "followups": tuple(followups)}


KNOWLEDGE_TOPICS = {
    "getting_started": _topic(
        ("myvalidcv work", "get started", "start", "upload cv", "use myvalidcv"),
        "The individual journey is Upload CV, Add Job, Validate, Verify Evidence, Improve and Apply.",
        "Start with one real vacancy: upload your PDF, DOCX or TXT CV, add the job title and full advert, then select Validate CV. Review the score and Truth Gate before changing any wording.",
        ("What can I upload?", "What does the report show?", "Explain the Truth Gate"),
    ),
    "uploads": _topic(
        ("upload", "pdf", "docx", "txt", "file", "scanned", "document error", "rejected cv"),
        "MyValidCV accepts PDF, DOCX and TXT documents up to 5 MB. Image-only documents may not contain readable text.",
        "Upload a PDF, DOCX or TXT file up to 5 MB. Use a text-based CV with clear Profile, Skills, Experience and Education sections; image-only scans may fail because their text cannot be read reliably.",
        ("Why was my CV rejected?", "How long is my CV stored?", "How do I add a job?"),
    ),
    "job_input": _topic(
        ("job advert", "job description", "vacancy url", "job url", "add a job", "paste advert"),
        "A job can be supplied as a title, pasted description, public vacancy URL or uploaded advert file.",
        "Add the exact vacancy you intend to apply for. Paste its description, use a readable public URL, or upload the advert. Include responsibilities, skills and qualifications; remove unrelated page text and personal notes for the cleanest analysis.",
        ("What does the score mean?", "Why is an advert rejected?", "How does matching work?"),
    ),
    "score": _topic(
        ("score", "percentage", "match", "ats report", "ats result", "low score", "high score", "readiness"),
        "The MyValidCV score measures document alignment for one CV and one job, not hiring probability.",
        "Your percentage is a MyValidCV document-alignment score for that vacancy—not a universal ATS score or hiring probability. Review Skills, Requirements, Evidence and Readability, then verify each requirement in the Truth Gate.",
        ("Explain the score components", "Explain the Truth Gate", "How can I improve my score?"),
    ),
    "score_components": _topic(
        ("score component", "skills score", "requirements score", "evidence score", "readability", "format score"),
        "The report separates skills, requirements, evidence and readability and caps results when mandatory proof is missing.",
        "Skills checks recognised capabilities; Requirements checks role criteria; Evidence looks for supporting CV passages rather than isolated words; Readability checks basic CV structure. Missing mandatory licences or qualifications can cap the overall result.",
        ("What counts as evidence?", "What is mandatory evidence?", "How do I improve the CV?"),
    ),
    "truth_gate": _topic(
        ("truth gate", "i have this", "training", "do not have", "evidence question", "verify evidence"),
        "Truth Gate asks the candidate to verify high-confidence skills, qualifications and mandatory requirements.",
        "Truth Gate separates detected wording from facts only you can confirm. Choose “I have this” only with genuine evidence, “I’m training” for work in progress, or “I don’t have this” to keep an unsupported claim out. The summary updates after each answer.",
        ("Why is a requirement shown?", "What happens next?", "Can I change an answer?"),
    ),
    "improvements": _topic(
        ("improve score", "increase score", "better match", "fix cv", "missing keyword", "missing skill"),
        "CV improvements must stay grounded in real experience and qualifications.",
        "Improve alignment by moving verified evidence higher, using accurate terminology from the advert, adding measurable outcomes and clarifying relevant responsibilities. Never add a missing skill, licence or qualification unless you genuinely have it.",
        ("Can MyValidCV rewrite my CV?", "Explain missing evidence", "What does Plus include?"),
    ),
    "documents": _topic(
        ("rewrite", "cv draft", "suggested cv", "download docx", "download txt", "edit draft", "bullet", "cover letter"),
        "Plus includes editable evidence-grounded CV and cover-letter drafts with candidate-controlled review.",
        "Plus can prepare an editable CV draft, experience-bullet suggestions and a tailored cover letter grounded in the source CV. Accept, edit or reject changes, then verify names, dates, employers, qualifications and figures before exporting DOCX or TXT.",
        ("How does bullet review work?", "What do the colours mean?", "How do cover letters work?"),
    ),
    "interview": _topic(
        ("interview", "interview studio", "prepare", "questions"),
        "Interview Studio combines standard preparation with prompts from the advert and Truth Gate.",
        "Interview Studio helps you prepare truthful examples for the target role. Use real situations, explain your personal contribution and quantify outcomes where possible; describe training and missing experience honestly.",
        ("Explain the Truth Gate", "How do I use confirmed evidence?", "What happens after the report?"),
    ),
    "plans": _topic(
        ("which plan", "compare plans", "plan", "pricing", "price", "free", "plus", "enterprise"),
        "Free provides 5 role checks; Plus provides 20 checks and generated documents; Enterprise provides bulk screening for 50 CVs.",
        "Choose Free to test one CV against up to five roles, Plus for up to twenty checks plus editable CV and cover-letter drafts, or Enterprise Starter to screen up to fifty applicant CVs. Paid access lasts 30 days and renews only when you choose.",
        ("What does Free include?", "What does Plus include?", "What does Enterprise include?"),
    ),
    "free_plan": _topic(
        ("free plan", "individual free", "five checks", "5 checks", "£0"),
        "Individual Free stores one CV for 30 days and provides five role checks with the online ATS report.",
        "Individual Free costs £0. It stores one CV for up to 30 days, checks up to five roles each month and provides the complete online compatibility report with recommendations.",
        ("What does Plus add?", "How long is my CV stored?", "How do I start?"),
    ),
    "plus_plan": _topic(
        ("plus plan", "individual plus", "twenty checks", "20 checks", "£4.99", "4.99"),
        "Individual Plus is a 30-day plan with 20 checks, full reports, CV drafts and cover letters.",
        "Individual Plus is currently £4.99 for 30 days. It includes up to twenty role checks, full ATS reports, an evidence-grounded CV draft and a tailored cover-letter draft for each tested role.",
        ("How are drafts protected?", "Can I download DOCX?", "How does payment work?"),
    ),
    "enterprise": _topic(
        ("enterprise", "hiring team", "recruiter", "bulk", "50 cv", "shortlist", "candidate ranking"),
        "Enterprise provides bulk comparison, mandatory-evidence review, anonymous first review and human-controlled outcomes.",
        "Enterprise Starter is for hiring teams. Upload up to fifteen CVs per batch and screen up to fifty per month against one role. It ranks document alignment and highlights mandatory evidence, but every shortlist or rejection remains a human decision.",
        ("How does bulk screening work?", "Explain anonymous review", "What does Enterprise cost?"),
    ),
    "enterprise_governance": _topic(
        ("anonymous review", "human review", "bias", "fair", "automatic reject", "protected characteristic", "decision email"),
        "Enterprise results are advisory and support anonymous review, audit access and human-controlled decisions.",
        "Use anonymous first review to hide applicant identities while checking evidence. Never reject automatically from the score: inspect the source CV and mandatory criteria first. Age and protected characteristics are not extracted for ranking.",
        ("How are candidates ranked?", "How do decision emails work?", "What is mandatory evidence?"),
    ),
    "privacy": _topic(
        ("privacy", "data", "retain", "retention", "delete cv", "secure", "storage", "gdpr"),
        "CV files are private to authorised users and retained for no longer than 30 days.",
        "MyValidCV keeps CV access tied to the authorised account and retains CV files for no longer than 30 days. Deleting a saved CV also deletes its reports. For a data-rights request, contact support@myvalidcv.com without sharing sensitive data in chat.",
        ("Does Maya remember chats?", "How do I delete my CV?", "What payment data is stored?"),
    ),
    "payments": _topic(
        ("payment", "pay", "card", "checkout", "receipt", "invoice", "activate", "refund", "cancel", "charged"),
        "Checkout uses the configured payment provider; access activates after verified payment and full card details are not stored by MyValidCV.",
        "Complete the secure hosted checkout and access updates after payment is verified. For a refund, cancellation or unexpected charge, email support@myvalidcv.com with your account email and transaction reference—never send card numbers in chat.",
        ("Where is my receipt?", "Why is payment pending?", "Compare the plans"),
    ),
    "account": _topic(
        ("login", "log in", "sign up", "register", "password", "google", "linkedin", "account"),
        "Customers can register with email and use configured Google or LinkedIn providers; password reset uses a one-time link.",
        "Create an account with email, or use Google or LinkedIn when enabled. Sign in with your username or email. If needed, request a one-time password-reset link from the login screen.",
        ("Why did social sign-in fail?", "Reset my password", "How is my account protected?"),
    ),
    "reminders": _topic(
        ("deadline", "reminder", "application date", "email reminder"),
        "Eligible individual users can save a deadline and request an email reminder, normally two days before it.",
        "Add the application deadline during validation and select the reminder option. MyValidCV can detect common deadline wording and normally schedules the email two days before the date.",
        ("How do I add a job?", "Why did my reminder not arrive?", "What does Plus include?"),
    ),
    "affiliate": _topic(
        ("affiliate", "partner", "referral", "commission", "promote myvalidcv"),
        "Creators, career professionals and organisations can apply to the owner-reviewed affiliate programme.",
        "Apply through the Affiliate Programme page. Approved partners receive a referral link and must label compensated promotion, avoid employment guarantees and never use spam or false accounts.",
        ("How do I apply?", "When is commission payable?", "What promotion is prohibited?"),
    ),
    "limitations": _topic(
        ("guarantee", "accurate", "limitation", "get a job", "interview chance", "ats acceptance"),
        "MyValidCV assesses supplied documents and cannot guarantee ATS acceptance, interviews or employment.",
        "MyValidCV improves document alignment, but employers use different systems and human processes. Results may be less reliable when a CV or advert is incomplete, image-based or outside the curated taxonomy.",
        ("How reliable is my report?", "What does the score mean?", "How can I improve it?"),
    ),
}


def select_knowledge(question, limit=4):
    """Select topics using phrase and token scoring."""
    normalized = re.sub(r"\s+", " ", (question or "").lower()).strip()
    tokens = set(re.findall(r"[a-z0-9£.]+", normalized))
    ranked = []
    priority_phrases = {
        "free_plan": ("free plan", "what about free"),
        "plus_plan": ("plus plan", "what about plus"),
        "enterprise": ("enterprise", "hiring team", "recruiter", "bulk screening"),
        "truth_gate": ("truth gate",),
        "score": ("ats report", "ats score"),
    }
    for index, (name, topic) in enumerate(KNOWLEDGE_TOPICS.items()):
        score = 0
        for keyword in topic["keywords"]:
            keyword = keyword.lower()
            if keyword in normalized:
                score += 5 if " " in keyword else 2
            elif " " not in keyword and keyword in tokens:
                score += 1
        if any(phrase in normalized for phrase in priority_phrases.get(name, ())):
            score += 10
        if score:
            ranked.append((score, index, name, topic))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    if not ranked:
        ranked = [
            (1, 0, "getting_started", KNOWLEDGE_TOPICS["getting_started"]),
            (1, len(KNOWLEDGE_TOPICS), "limitations", KNOWLEDGE_TOPICS["limitations"]),
        ]
    return [
        {"topic": name, "content": topic["content"], "answer": topic["answer"], "followups": list(topic["followups"])}
        for _score, _index, name, topic in ranked[:limit]
    ]


def primary_knowledge(question):
    return select_knowledge(question, limit=1)[0]


def knowledge_context(question):
    return "\n\n".join(f"[{item['topic']}]\n{item['content']}" for item in select_knowledge(question))
