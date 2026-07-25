import re
import logging

from django.core.exceptions import ImproperlyConfigured

from .models import Qualification, RoleTemplate, Skill


logger = logging.getLogger(__name__)


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

PREFERRED_HINTS = (
    "advantage", "beneficial", "desirable", "ideally", "nice to have",
    "optional", "preferred", "would be useful",
)

NEGATED_MANDATORY_PATTERNS = (
    r"\bnot\s+(?:essential|required|mandatory)\b",
    r"\bno\s+(?:licen[cs]e|qualification|degree|certification)\s+(?:is\s+)?required\b",
    r"\b(?:licen[cs]e|qualification|degree|certification)\s+not\s+required\b",
)

EVIDENCE_SIGNALS = (
    "achieved", "built", "coordinated", "created", "delivered", "developed",
    "implemented", "improved", "increased", "led", "managed", "reduced",
    "resolved", "supported", "trained", "using",
)

JOB_ADVERT_SIGNALS = (
    "about the role", "candidate", "duties", "essential", "experience",
    "job", "knowledge", "must", "position", "preferred", "qualification",
    "required", "requirements", "responsibilities", "role", "skills",
)


def validate_job_description(job_description):
    """Return whether text is substantial enough to support a meaningful score."""
    text = re.sub(r"\s+", " ", (job_description or "")).strip()
    if len(text) < 120:
        return False, "The job advert is too short to produce a reliable role-match assessment."
    signal_count = sum(1 for signal in JOB_ADVERT_SIGNALS if signal in text.lower())
    if signal_count < 2:
        return False, (
            "The document does not appear to contain a complete job advert. "
            "Include the role responsibilities, skills, experience, or qualifications."
        )
    if text.lower().startswith("job advert url:"):
        return False, "The job advert page could not be read. Paste the full advert text instead."
    return True, ""


def calculate_score(cv_text, job_description, job_title=""):
    details = calculate_score_details(cv_text, job_description, job_title)
    return details["score"], details["matched"], details["missing"], details["recommendation"]


def calculate_score_details(cv_text, job_description, job_title=""):
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
    evidence_map = _build_evidence_map(
        cv_text,
        requirement_terms,
        taxonomy["mandatory_terms"],
        taxonomy["required_qualifications"],
        job_lower,
    )
    evidenced = [item for item in evidence_map if item["status"] == "verified"]
    mentioned = [item for item in evidence_map if item["status"] == "mentioned"]
    evidence_score = min(
        100,
        int(((len(evidenced) + (len(mentioned) * 0.45)) / max(len(evidence_map), 1)) * 100),
    )
    format_score, format_checks = _calculate_format_score(cv_text)

    if not jd_skills and requirement_terms:
        skills_score = requirement_score
    if not title_terms:
        title_score = min(70, requirement_score)

    score = int(
        (skills_score * 0.22)
        + (requirement_score * 0.27)
        + (title_score * 0.14)
        + (keyword_score * 0.12)
        + (mandatory_score * 0.12)
        + (evidence_score * 0.08)
        + (format_score * 0.05)
    )
    score = max(0, min(100, score))

    if missing_mandatory:
        score = min(score, 49)
    elif requirement_terms and requirement_score < 20 and title_score < 35:
        score = min(score, 45)
    elif len(requirement_terms) >= 5 and evidence_score < 20:
        score = min(score, 59)
    elif len(requirement_terms) >= 5 and evidence_score < 40:
        score = min(score, 74)
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
    elif len(requirement_terms) >= 5 and evidence_score < 20:
        recommendation = (
            "Keyword alignment is present, but the CV does not demonstrate enough of the requirements. "
            "Add truthful examples, outcomes, qualifications, or project evidence before relying on the match."
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

    requirement_groups = _classify_requirements(job_lower, requirement_terms, taxonomy["mandatory_terms"])
    confidence_score, confidence_label, confidence_reasons = _calculate_confidence(
        cv_text,
        job_description,
        requirement_terms,
        evidence_map,
        taxonomy.get("detected_role", ""),
    )

    return {
        "score": score,
        "matched": matched,
        "missing": missing,
        "recommendation": recommendation,
        "taxonomy": {
            "detected_role": taxonomy.get("detected_role", ""),
            "detected_family": taxonomy.get("detected_family", ""),
            "required_skills": taxonomy["required_skills"],
            "required_qualifications": taxonomy["required_qualifications"],
            "mandatory_terms": taxonomy["mandatory_terms"],
            "missing_mandatory": missing_mandatory,
            "matched_required": [
                term for term in taxonomy["required_skills"] + taxonomy["required_qualifications"]
                if _term_in_text(term, cv_lower)
            ],
        },
        "score_components": {
            "skills": skills_score,
            "requirements": requirement_score,
            "title": title_score,
            "keywords": keyword_score,
            "mandatory": mandatory_score,
            "evidence": evidence_score,
            "format": format_score,
        },
        "requirement_groups": requirement_groups,
        "evidence_map": evidence_map,
        "format_checks": format_checks,
        "confidence": {
            "score": confidence_score,
            "label": confidence_label,
            "reasons": confidence_reasons,
        },
        "model_version": "2.0",
    }


def load_taxonomy(job_text, job_title=""):
    empty = {
        "skills": [],
        "required_skills": [],
        "required_qualifications": [],
        "mandatory_terms": [],
        "detected_role": "",
        "detected_family": "",
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
            "detected_role": role.title,
            "detected_family": role.job_family.name,
        }
    except ImproperlyConfigured:
        return empty
    except Exception:
        logger.exception("ATS taxonomy lookup failed; using advert-led scoring.")
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
            is_negated = any(re.search(pattern, sentence) for pattern in NEGATED_MANDATORY_PATTERNS)
            is_preferred = any(hint in sentence for hint in PREFERRED_HINTS)
            if any(_term_in_text(term, sentence) for term in terms) and not is_negated and not is_preferred and (
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


def _sentences(text):
    return [
        re.sub(r"\s+", " ", part).strip(" -•\t")
        for part in re.split(r"[\n\r]+|(?<=[.!?;])\s+", text or "")
        if re.sub(r"\s+", " ", part).strip()
    ]


def _classify_requirements(job_text, terms, mandatory_terms):
    groups = {"mandatory": [], "required": [], "preferred": [], "responsibilities": []}
    mandatory_set = set(mandatory_terms)
    for term in terms:
        matching = [sentence for sentence in _sentences(job_text) if _term_in_text(term, sentence.lower())]
        context = matching[0] if matching else ""
        lower = context.lower()
        if term in mandatory_set or (
            any(hint in lower for hint in MANDATORY_HINTS)
            and not any(hint in lower for hint in PREFERRED_HINTS)
            and not any(re.search(pattern, lower) for pattern in NEGATED_MANDATORY_PATTERNS)
        ):
            group = "mandatory"
        elif any(hint in lower for hint in PREFERRED_HINTS):
            group = "preferred"
        elif any(word in lower for word in ("responsib", "duties", "will ", "day-to-day")):
            group = "responsibilities"
        else:
            group = "required"
        groups[group].append({"term": term, "context": context[:240]})
    return groups


def _build_evidence_map(cv_text, requirements, mandatory_terms, qualification_terms, job_text):
    cv_sentences = _sentences(cv_text)
    mandatory_set = set(mandatory_terms)
    qualification_set = set(qualification_terms)
    classified = _classify_requirements(job_text, requirements, mandatory_terms)
    type_by_term = {
        item["term"]: group
        for group, items in classified.items()
        for item in items
    }
    evidence = []
    for term in requirements:
        passages = [sentence for sentence in cv_sentences if _term_in_text(term, sentence.lower())]
        passage = passages[0][:300] if passages else ""
        lower = passage.lower()
        has_action = any(signal in lower for signal in EVIDENCE_SIGNALS)
        has_measure = bool(re.search(r"\b\d+(?:\.\d+)?%?\b|£|\$", passage))
        if passage and (has_action or has_measure or term in qualification_set):
            status = "verified"
            strength = "measurable" if has_measure else "demonstrated"
            action = "Safe to retain after checking the wording against your experience."
        elif passage:
            status = "mentioned"
            strength = "keyword only"
            action = "Add a truthful example showing where and how you used this."
        elif term in mandatory_set or term in qualification_set:
            status = "proof_required"
            strength = "not evidenced"
            action = "Do not add this claim without the required qualification, licence, training, or proof."
        else:
            status = "confirmation_required"
            strength = "not evidenced"
            action = "Confirm that you genuinely have this experience before adding it."
        evidence.append({
            "term": term,
            "requirement_type": type_by_term.get(term, "required"),
            "status": status,
            "strength": strength,
            "passage": passage,
            "action": action,
        })
    return evidence


def _calculate_format_score(cv_text):
    text = cv_text or ""
    lower = text.lower()
    checks = {
        "contact_details": bool(
            re.search(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", lower)
            or re.search(r"\+?\d[\d\s().-]{7,}\d", text)
        ),
        "profile_section": any(term in lower for term in ("profile", "summary", "objective")),
        "skills_section": "skills" in lower or "competencies" in lower,
        "experience_section": any(term in lower for term in ("experience", "employment", "work history")),
        "education_section": any(term in lower for term in ("education", "qualification", "certification")),
        "readable_length": 450 <= len(text) <= 15000,
        "achievement_evidence": bool(re.search(r"\b\d+(?:\.\d+)?%?\b|£|\$", text)),
    }
    score = int((sum(checks.values()) / len(checks)) * 100)
    return score, checks


def _calculate_confidence(cv_text, job_text, requirements, evidence_map, detected_role):
    score = 0
    reasons = []
    if len(cv_text or "") >= 700:
        score += 25
    elif len(cv_text or "") >= 350:
        score += 15
        reasons.append("The CV contains only moderate extractable detail.")
    else:
        score += 5
        reasons.append("The CV contains limited extractable text.")
    if len(job_text or "") >= 500:
        score += 25
    elif len(job_text or "") >= 250:
        score += 15
        reasons.append("The job advert contains only moderate detail.")
    else:
        score += 5
        reasons.append("The job advert is relatively short.")
    requirement_points = min(20, len(requirements) * 4)
    score += requirement_points
    if len(requirements) < 5:
        reasons.append("Few distinct job requirements were detected.")
    if detected_role:
        score += 15
    else:
        reasons.append("No curated role template matched this advert.")
    evidence_items = list(evidence_map or [])
    evidenced_items = sum(bool(item.get("passage")) for item in evidence_items)
    evidence_coverage = evidenced_items / len(evidence_items) if evidence_items else 0
    score += round(evidence_coverage * 15)
    if evidence_coverage < 0.5:
        reasons.append("Little requirement-level evidence was located in the CV.")
    label = "High" if score >= 85 and detected_role else "Medium" if score >= 55 else "Low"
    return score, label, reasons or ["The documents contain sufficient detail for this assessment."]
