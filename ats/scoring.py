import re

from django.core.exceptions import ImproperlyConfigured

from .models import Qualification, RoleTemplate, Skill


BASE_SKILLS = [
    "python", "django", "sql", "postgresql", "html", "css", "javascript",
    "bootstrap", "api", "git", "github", "excel", "communication",
    "leadership", "project management", "data analysis", "customer service",
    "administration", "scheduling", "records management", "data entry",
    "reception", "office management", "document control", "compliance",
    "airport operations", "passenger service", "aviation", "boarding",
    "dentistry", "dental", "patient care", "oral health", "treatment planning",
    "radiography", "x-ray", "infection control", "clinical assessment",
    "bookkeeping", "payroll", "budgeting", "forecasting", "reconciliations",
    "vat", "recruitment", "onboarding", "crm", "lead generation",
    "warehouse", "inventory", "forklift", "safeguarding", "food safety",
]

STOP_WORDS = {
    "about", "above", "after", "again", "against", "also", "and", "any",
    "are", "because", "been", "before", "being", "below", "between", "both",
    "but", "can", "candidate", "company", "control", "could", "day", "description",
    "did", "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "here", "hers", "him", "his",
    "how", "into", "its", "job", "just", "more", "most", "must", "not",
    "now", "off", "once", "only", "other", "our", "out", "over", "own",
    "position", "requirements", "responsibilities", "role", "same", "service", "she",
    "should", "some", "such", "than", "that", "the", "their", "them", "then",
    "there", "these", "they", "this", "those", "through", "too", "under",
    "until", "very", "was", "were", "what", "when", "where", "which", "while",
    "who", "will", "with", "work", "would", "you", "your",
}

GENERIC_REQUIREMENT_TERMS = {
    "ability", "able", "applicant", "apply", "benefits", "business", "client",
    "clients", "company", "deadline", "department", "duties", "employee",
    "environment", "excellent", "expected", "full", "good", "high", "hours",
    "ideal", "join", "knowledge", "level", "minimum", "needed", "people",
    "person", "preferred", "previous", "proven", "required", "requires",
    "responsible", "salary", "successful", "support", "team", "teams",
    "using", "weekly", "within", "working",
}

MANDATORY_HINTS = (
    "essential", "required", "must", "licence", "license", "registration",
    "certification", "qualified", "degree", "mandatory",
)


def calculate_score(cv_text, job_description, job_title=""):
    cv_lower = (cv_text or "").lower()
    job_lower = (job_description or "").lower()
    taxonomy = load_taxonomy(job_lower, job_title)

    known_terms = _unique_keep_order(BASE_SKILLS + taxonomy["skills"])
    jd_skills = _extract_known_terms(job_lower, known_terms)
    cv_skills = _extract_known_terms(cv_lower, known_terms)
    matched_skills = [skill for skill in jd_skills if _term_in_text(skill, cv_lower)]
    missing_skills = [skill for skill in jd_skills if skill not in matched_skills]

    title_terms = _extract_title_terms(job_title)
    requirement_terms = _extract_requirement_terms(job_lower, job_title, known_terms)
    required_taxonomy_terms = taxonomy["required_skills"] + taxonomy["required_qualifications"]
    requirement_terms = _unique_keep_order(requirement_terms + required_taxonomy_terms)

    matched_requirements = [term for term in requirement_terms if _term_in_text(term, cv_lower)]
    missing_requirements = [term for term in requirement_terms if not _term_in_text(term, cv_lower)]
    matched_title_terms = [term for term in title_terms if _term_in_text(term, cv_lower)]
    jd_keywords = _extract_relevant_keywords(job_lower)
    cv_keywords = _extract_relevant_keywords(cv_lower)
    matched_keywords = [term for term in jd_keywords if term in cv_keywords]
    missing_keywords = [term for term in jd_keywords if term not in cv_keywords]
    missing_mandatory = [
        term for term in taxonomy["mandatory_terms"]
        if not _term_in_text(term, cv_lower)
    ]

    skills_score = _ratio_score(matched_skills, jd_skills)
    requirement_score = _ratio_score(matched_requirements, requirement_terms)
    title_score = _ratio_score(matched_title_terms, title_terms)
    keyword_score = _ratio_score(matched_keywords, jd_keywords[:12])
    mandatory_score = 100 if not taxonomy["mandatory_terms"] else _ratio_score(
        [term for term in taxonomy["mandatory_terms"] if _term_in_text(term, cv_lower)],
        taxonomy["mandatory_terms"],
    )

    if not jd_skills and requirement_terms:
        skills_score = requirement_score
    if not title_terms:
        title_score = min(70, requirement_score)

    score = int(
        (skills_score * 0.22)
        + (requirement_score * 0.32)
        + (title_score * 0.14)
        + (keyword_score * 0.20)
        + (mandatory_score * 0.12)
    )
    score = max(0, min(100, score))

    if missing_mandatory:
        score = min(score, 49)
    elif requirement_terms and requirement_score < 20 and title_score < 35:
        score = min(score, 45)
    elif requirement_terms and requirement_score < 40:
        score = min(score, 59)
    elif missing_requirements and len(missing_requirements) >= max(3, len(requirement_terms) // 2):
        score = min(score, 74)

    matched = _unique_keep_order(matched_title_terms + matched_requirements + matched_skills + matched_keywords[:4])
    missing = _unique_keep_order(missing_mandatory + missing_requirements[:8] + missing_skills[:6] + missing_keywords[:4])

    if missing_mandatory:
        recommendation = (
            "Mandatory requirement gap. Recruiters are likely to screen this CV out unless the missing licence, "
            "qualification, or essential evidence is genuinely added."
        )
    elif requirement_terms and requirement_score < 20 and title_score < 35:
        recommendation = (
            "High role mismatch. The CV may be well written, but recruiters are unlikely to see enough evidence "
            "for this specific role. Add truthful role-specific experience before applying."
        )
    elif score >= 80:
        recommendation = "Strong role fit. Keep the top third focused on the matched requirements and measurable evidence."
    elif score >= 55:
        recommendation = (
            "Partial role fit. Improve the CV by moving matched evidence higher and adding truthful proof for the missing requirements."
        )
    else:
        recommendation = (
            "Weak match for this job. The CV needs clearer role-specific skills, keywords, and evidence before applying."
        )

    return score, matched, missing, recommendation


def load_taxonomy(job_text, job_title=""):
    empty = {
        "skills": [],
        "required_skills": [],
        "required_qualifications": [],
        "mandatory_terms": [],
    }
    try:
        skills = []
        for skill in Skill.objects.all():
            skills.extend(skill.terms())

        qualifications = list(Qualification.objects.all())
        role = find_best_role_template(job_text, job_title)
        if not role:
            mandatory = _detect_mandatory_qualifications(job_text, qualifications)
            return {**empty, "skills": _unique_keep_order(skills), "mandatory_terms": mandatory}

        required_skills = [
            req.skill.normalized_name
            for req in role.skill_requirements.select_related("skill")
            if req.importance == "required"
        ]
        required_qualifications = [
            req.qualification.normalized_name
            for req in role.qualification_requirements.select_related("qualification")
            if req.importance == "required"
        ]
        mandatory = _unique_keep_order(required_qualifications + _detect_mandatory_qualifications(job_text, qualifications))
        return {
            "skills": _unique_keep_order(skills),
            "required_skills": _unique_keep_order(required_skills),
            "required_qualifications": _unique_keep_order(required_qualifications),
            "mandatory_terms": mandatory,
        }
    except (ImproperlyConfigured, Exception):
        return empty


def find_best_role_template(job_text, job_title=""):
    source = f"{job_title} {job_text}".lower()
    best_role = None
    best_score = 0
    for role in RoleTemplate.objects.select_related("job_family").all():
        score = 0
        for term in role.terms():
            if _term_in_text(term, source):
                score += 4 if term == role.normalized_title else 2
        family_name = role.job_family.name.lower()
        if _term_in_text(family_name, source):
            score += 1
        if score > best_score:
            best_role = role
            best_score = score
    return best_role if best_score >= 2 else None


def _detect_mandatory_qualifications(job_text, qualifications):
    mandatory = []
    sentences = re.split(r"[\n.;]+", job_text.lower())
    for qualification in qualifications:
        terms = qualification.terms()
        for sentence in sentences:
            if any(_term_in_text(term, sentence) for term in terms) and (
                qualification.is_license or any(hint in sentence for hint in MANDATORY_HINTS)
            ):
                mandatory.append(qualification.normalized_name)
                break
    return _unique_keep_order(mandatory)


def _extract_known_terms(text, terms):
    found = []
    for term in terms:
        if _term_in_text(term, text):
            found.append(term)
    return _unique_keep_order(found)


def _extract_title_terms(job_title):
    return _unique_keep_order(_important_words(job_title or "")[:6])


def _extract_requirement_terms(job_text, job_title="", known_terms=None):
    terms = []
    known_terms = known_terms or BASE_SKILLS
    terms.extend(_extract_title_terms(job_title))
    terms.extend(_extract_known_terms(job_text, known_terms))

    requirement_lines = []
    for line in re.split(r"[\n.;:]+", job_text):
        if re.search(r"\b(require|required|responsib|duties|skills|experience|qualification|essential|must|knowledge|ability|licen[cs]e|certif)\b", line):
            requirement_lines.append(line)
    source_text = " ".join(requirement_lines) if requirement_lines else job_text

    terms.extend(_important_words(source_text))
    terms.extend(_extract_relevant_keywords(job_text, limit=18))
    return _unique_keep_order(terms)[:32]


def _extract_relevant_keywords(text, limit=20):
    words = _important_words(text)
    counts = {}
    for word in words:
        if word in GENERIC_REQUIREMENT_TERMS:
            continue
        counts[word] = counts.get(word, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [word for word, _count in ranked[:limit]]


def _important_words(text):
    words = re.findall(r"\b[a-z][a-z0-9+#.-]{2,}\b", (text or "").lower())
    return [
        word.strip(".-")
        for word in words
        if word not in STOP_WORDS
        and word not in GENERIC_REQUIREMENT_TERMS
        and len(word.strip(".-")) >= 4
    ]


def _term_in_text(term, text):
    return re.search(r"\b" + re.escape(term.lower()) + r"\b", text) is not None


def _ratio_score(matched, required):
    if not required:
        return 0
    return min(100, int((len(matched) / len(required)) * 100))


def _unique_keep_order(items):
    seen = set()
    unique = []
    for item in items:
        normalized = str(item).strip().lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique
