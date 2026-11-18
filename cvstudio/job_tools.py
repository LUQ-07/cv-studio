"""Offline job-description comparison and editable cover-letter starter."""
import re
from collections import Counter

STOPWORDS = set("""a an and are as at be by for from has have in is it its of on or our that the their this to with will you your we they into about across using use used work working team teams experience skills role candidate required preferred ability strong excellent including such plus also""".split())
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#.\-]*")


def _profile_text(profile) -> str:
    pieces = [profile.full_name, profile.headline, profile.summary]
    fields = {
        "experience": ("role", "company", "description"),
        "education": ("degree", "school", "description"),
        "skills": ("name", "level"),
        "certificates": ("name", "issuer", "description"),
        "projects": ("name", "description"),
        "languages": ("name", "level"),
        "awards": ("name", "issuer", "description"),
        "volunteer": ("role", "organization", "description"),
        "custom_sections": ("title", "content"),
    }
    for section_name, keys in fields.items():
        for entry in getattr(profile, section_name):
            pieces.extend(str(entry.get(key, "")) for key in keys)
    return " ".join(pieces).lower()


def analyze_job_match(profile, job_description: str, limit: int = 12) -> dict:
    """Compare meaningful words in the posting with text in the supplied CV.

    This deliberately reports wording overlap only; it is not an ATS simulation.
    """
    counts = Counter(token.lower().strip(".-") for token in TOKEN_RE.findall(job_description or ""))
    counts = Counter({word: count for word, count in counts.items() if len(word) >= 3 and word not in STOPWORDS and not word.isdigit()})
    cv_text = _profile_text(profile)
    ranked = sorted(counts, key=lambda word: (-counts[word], word))[:max(1, limit)]
    matched = [word for word in ranked if re.search(r"(?<![a-z0-9])"+re.escape(word)+r"(?![a-z0-9])", cv_text)]
    missing = [word for word in ranked if word not in matched]
    return {"terms_checked": ranked, "matched": matched, "missing": missing,
            "coverage": round(100*len(matched)/len(ranked)) if ranked else 0}


def draft_cover_letter(profile, role: str, company: str, hiring_manager: str = "", why_role: str = "", contribution: str = "") -> str:
    role = (role or "[job title]").strip()
    company = (company or "[company]").strip()
    greeting = (hiring_manager or "Hiring Team").strip()
    name = (profile.full_name or "[Your name]").strip()
    paragraphs = [f"Dear {greeting},", f"I am applying for the {role} position at {company}. {profile.headline or 'My background and skills are relevant to this opportunity.'}"]
    if profile.summary:
        paragraphs.append(profile.summary.strip())
    if profile.experience:
        item = profile.experience[0]
        role_text = item.get("role", "").strip()
        company_text = item.get("company", "").strip()
        detail = item.get("description", "").strip()
        source = " at ".join(x for x in (role_text, company_text) if x)
        if source and detail:
            paragraphs.append(f"In my recent work as {source}, {detail}")
    if why_role.strip():
        paragraphs.append(why_role.strip())
    else:
        paragraphs.append("[Add a specific reason this role or organization interests you.] ")
    if contribution.strip():
        paragraphs.append(contribution.strip())
    else:
        paragraphs.append("[Add one relevant contribution you can support with an example.] ")
    paragraphs.extend(["Thank you for considering my application. I would welcome the opportunity to discuss how my experience could support your team.", f"Sincerely,\n{name}"])
    return "\n\n".join(paragraphs)
