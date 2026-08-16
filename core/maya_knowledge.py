"""Curated, auditable service knowledge for Maya.

Maya is grounded from this source at request time. It does not train on chats or
silently retain customer messages.
"""

import re


KNOWLEDGE_TOPICS = {
    "service": {
        "keywords": ("myvalidcv", "how", "work", "start", "service", "platform", "upload"),
        "content": (
            "MyValidCV helps a user compare one CV with one specific job advert. "
            "The journey is Upload CV -> Add Job -> Validate -> Improve -> Apply. "
            "It supports PDF, DOCX and TXT documents up to 5 MB. A result is guidance "
            "for improving an application, not a promise of an interview or job."
        ),
    },
    "ats_v2": {
        "keywords": (
            "ats", "score", "match", "result", "evidence", "truth gate", "requirement",
            "keyword", "confidence", "readability",
        ),
        "content": (
            "ATS v2 reports a CV-to-role evidence match, not hiring probability. It validates "
            "the job advert and measures skills, requirements, evidence and readability. It "
            "separates mandatory, required, preferred and responsibility requirements. The "
            "Truth Gate labels evidence as verified in the CV, keyword-only, candidate "
            "confirmation required, or proof/training/licence required. Users can record "
            "whether they have an item, are training, or do not have it. Red or unsupported "
            "claims must not be copied into application documents."
        ),
    },
    "documents": {
        "keywords": ("cv", "resume", "rewrite", "draft", "cover letter", "download", "summary"),
        "content": (
            "The report can suggest focused CV wording grounded in the uploaded CV. Green means "
            "evidence was found; yellow means stronger presentation that still needs checking; "
            "unsupported red claims are excluded from generated CV content. Plus can include "
            "downloadable CV and cover-letter drafts. The user must verify names, dates, figures, "
            "qualifications and every factual statement before sending."
        ),
    },
    "plans": {
        "keywords": ("plan", "price", "pricing", "free", "plus", "enterprise", "allowance", "limit"),
        "content": (
            "Free includes 5 individual analyses and one retained CV. Plus includes 20 analyses, "
            "job URL/file input, generated CV and cover-letter drafts, and deadline alerts. "
            "Enterprise includes up to 50 bulk CV scans and advisory comparison reports, but does "
            "not include generated candidate CVs or cover letters. The live Plans page and the "
            "customer's active subscription are authoritative for price and entitlement."
        ),
    },
    "enterprise": {
        "keywords": ("enterprise", "bulk", "candidate", "recruit", "rank", "shortlist", "hire"),
        "content": (
            "Enterprise compares multiple CV documents with one role. Rankings are advisory, tied "
            "scores receive equal rank, and every result requires human review. The score must not "
            "be used as an automatic hiring or rejection decision. Recruiters should independently "
            "verify qualifications, licences, experience and fair-hiring obligations."
        ),
    },
    "privacy": {
        "keywords": ("privacy", "data", "retain", "delete", "secure", "security", "store"),
        "content": (
            "CV files are private to their owner and retained for the configured retention period, "
            "normally 30 days. Users can delete saved CVs and related results. Maya must not ask for "
            "passwords, full payment-card details, government identifiers or unnecessary sensitive "
            "personal information. Account-specific privacy requests go to support@myvalidcv.com."
        ),
    },
    "payments": {
        "keywords": ("payment", "pay", "card", "stripe", "receipt", "invoice", "refund", "cancel"),
        "content": (
            "Checkout is handled by the configured payment provider and access is activated only "
            "after verified payment. MyValidCV does not directly store full card details. Receipts "
            "are available only for confirmed paid transactions. Refunds and cancellations depend "
            "on the published terms, usage and timing; Maya cannot approve them. Account-specific "
            "billing questions go to support@myvalidcv.com."
        ),
    },
    "deadlines": {
        "keywords": ("deadline", "reminder", "email", "application date"),
        "content": (
            "Eligible individual plans can save a job deadline and request a reminder. Reminders "
            "depend on correct email configuration and the scheduled reminder command running."
        ),
    },
    "limitations": {
        "keywords": ("guarantee", "chance", "interview", "job", "accurate", "limitation"),
        "content": (
            "MyValidCV cannot guarantee ATS acceptance, an interview, a shortlist or employment. "
            "Employer systems and decisions vary. The service assesses supplied documents and may "
            "have lower confidence when a CV or advert is incomplete, image-based or outside the "
            "curated role taxonomy."
        ),
    },
}


def select_knowledge(question, limit=4):
    """Select the most relevant curated topics using deterministic term scoring."""
    normalized = re.sub(r"\s+", " ", (question or "").lower())
    ranked = []
    for name, topic in KNOWLEDGE_TOPICS.items():
        score = sum(2 if " " in keyword else 1 for keyword in topic["keywords"] if keyword in normalized)
        if score:
            ranked.append((score, name, topic["content"]))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    if not ranked:
        ranked = [
            (1, "service", KNOWLEDGE_TOPICS["service"]["content"]),
            (1, "limitations", KNOWLEDGE_TOPICS["limitations"]["content"]),
        ]
    return [{"topic": name, "content": content} for _score, name, content in ranked[:limit]]


def knowledge_context(question):
    selected = select_knowledge(question)
    return "\n\n".join(f"[{item['topic']}]\n{item['content']}" for item in selected)
