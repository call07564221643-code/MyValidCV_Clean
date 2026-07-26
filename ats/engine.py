"""Document extraction and structural CV validation.

ATS scoring lives in ``ats.scoring``. Keeping file handling here prevents
optional local packages from silently changing production scoring behaviour.
"""

import re
from typing import Tuple

import pypdf
from docx import Document


class CVExtractionError(Exception):
    """Raised when an uploaded document cannot be converted to text."""


class ATSEngine:
    """Extract supported uploads and reject documents that are not usable CVs."""

    def extract_text_from_upload(self, uploaded_file) -> str:
        """Extract text from a Django uploaded file without writing it to disk."""
        file_name = uploaded_file.name.lower()
        try:
            if file_name.endswith(".pdf"):
                reader = pypdf.PdfReader(uploaded_file)
                return "\n".join((page.extract_text() or "") for page in reader.pages)

            if file_name.endswith(".docx"):
                document = Document(uploaded_file)
                return "\n".join(paragraph.text for paragraph in document.paragraphs)

            if file_name.endswith(".txt"):
                raw = uploaded_file.read()
                try:
                    return raw.decode("utf-8")
                except UnicodeDecodeError:
                    return raw.decode("latin-1")

            raise CVExtractionError(f"Unsupported file format: {file_name}")
        except CVExtractionError:
            raise
        except Exception as exc:
            raise CVExtractionError(f"Failed to extract text: {exc}") from exc

    def validate_cv_text(self, text: str) -> Tuple[bool, str]:
        """Return whether extracted text has the minimum structure of a usable CV."""
        text = (text or "").strip()
        text_lower = text.lower()
        text_lines = [line.strip() for line in text.splitlines() if line.strip()]
        words = re.findall(r"[a-zA-Z][a-zA-Z'+-]*", text)

        if len(text) < 450 or len(words) < 80:
            return False, (
                "The uploaded document is too short to be a usable CV. Upload a complete CV "
                "with contact details, skills, experience, and education."
            )

        alpha_chars = sum(1 for char in text if char.isalpha())
        if alpha_chars / max(len(text), 1) < 0.45:
            return False, (
                "The document text could not be read clearly. Upload a text-based PDF, DOCX, "
                "or TXT CV rather than a scanned image."
            )

        contact_patterns = [
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            r"(\+?\d[\d\s().-]{7,}\d)",
            r"linkedin\.com/in/",
        ]
        if not any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in contact_patterns):
            return False, (
                "The document does not include clear contact details. Add an email address, "
                "phone number, or LinkedIn profile to the CV."
            )

        section_groups = {
            "profile": ["profile", "summary", "objective", "personal statement"],
            "skills": ["skills", "core skills", "technical skills", "competencies"],
            "experience": ["experience", "employment", "work history", "career history", "projects"],
            "education": [
                "education", "qualification", "qualifications", "certification",
                "certifications", "training",
            ],
        }
        matched_sections = [
            section
            for section, keywords in section_groups.items()
            if any(keyword in text_lower for keyword in keywords)
        ]
        if len(matched_sections) < 2:
            return False, (
                "This does not look like a structured CV. Include at least two sections such as "
                "Profile, Skills, Experience, Education, or Projects."
            )

        cv_keywords = [
            "managed", "led", "developed", "delivered", "supported", "created",
            "implemented", "improved", "coordinated", "analysed", "analyzed",
            "reported", "trained", "customer", "team", "system", "project",
            "responsible", "achievement", "skills", "experience", "education",
        ]
        if sum(keyword in text_lower for keyword in cv_keywords) < 3:
            return False, (
                "The document is missing normal CV evidence keywords. Add responsibilities, "
                "achievements, skills, and work or project evidence."
            )

        job_ad_markers = [
            "apply now", "job type", "salary", "benefits",
            "responsibilities include", "the successful candidate",
        ]
        if (
            any(marker in text_lower for marker in job_ad_markers)
            and "education" not in text_lower
            and "employment" not in text_lower
        ):
            return False, (
                "This looks more like a job advert than a CV. Upload your CV, then paste or "
                "attach the job advert separately."
            )

        if len(text_lines) < 8:
            return False, (
                "CV structure appears incomplete. Use separate lines or headings for contact, "
                "profile, skills, experience, and education."
            )

        return True, "Valid CV"


ats_engine = ATSEngine()
