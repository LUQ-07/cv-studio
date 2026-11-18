"""Simple serializable data structures for CV profiles."""
from dataclasses import dataclass, field, asdict
from typing import Any
import uuid


def new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class CVProfile:
    id: str = field(default_factory=new_id)
    title: str = "My CV"
    full_name: str = ""
    headline: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    address: str = ""
    photo_path: str = ""
    summary: str = ""
    experience: list[dict[str, Any]] = field(default_factory=list)
    education: list[dict[str, Any]] = field(default_factory=list)
    skills: list[dict[str, Any]] = field(default_factory=list)
    certificates: list[dict[str, Any]] = field(default_factory=list)
    languages: list[dict[str, Any]] = field(default_factory=list)
    projects: list[dict[str, Any]] = field(default_factory=list)
    links: list[dict[str, Any]] = field(default_factory=list)
    awards: list[dict[str, Any]] = field(default_factory=list)
    volunteer: list[dict[str, Any]] = field(default_factory=list)
    courses: list[dict[str, Any]] = field(default_factory=list)
    publications: list[dict[str, Any]] = field(default_factory=list)
    internships: list[dict[str, Any]] = field(default_factory=list)
    memberships: list[dict[str, Any]] = field(default_factory=list)
    references: list[dict[str, Any]] = field(default_factory=list)
    hobbies: list[dict[str, Any]] = field(default_factory=list)
    custom_sections: list[dict[str, Any]] = field(default_factory=list)
    hidden_sections: list[str] = field(default_factory=list)   # section keys not exported
    section_order: list[str] = field(default_factory=list)     # user's order for the wide column
    template_id: str = "modern_summit"
    template_chosen: bool = False       # True once the user pressed USE THIS TEMPLATE (drives the gallery highlight)
    accent_color: str = "#5B63E6"
    font_size: int = 10
    show_photo: bool = True
    page_size: str = "A4"
    target_role: str = ""
    target_company: str = ""
    hiring_manager: str = ""
    job_description: str = ""
    why_role: str = ""
    relevant_contribution: str = ""
    cover_letter_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CVProfile":
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in data.items() if k in allowed})


def sample_profile() -> CVProfile:
    return CVProfile(
        title="Alex Morgan — Product Designer",
        full_name="Alex Morgan",
        headline="Product Designer | UX Research & Design Systems",
        email="alex.morgan@example.com",
        phone="+1 555 010 2040",
        location="Toronto, Canada",
        summary=("Product designer with 5+ years of experience turning complex workflows into "
                 "clear, accessible digital products. I partner closely with research, engineering, "
                 "and product teams to ship thoughtful experiences."),
        experience=[
            {"role":"Senior Product Designer", "company":"Northstar Labs", "location":"Toronto, Canada", "dates":"2022 — Present", "description":"Led discovery and design for a customer onboarding redesign, improving activation by 18%. Built a shared component library used by four product teams."},
            {"role":"Product Designer", "company":"Brightside Studio", "location":"Remote", "dates":"2019 — 2022", "description":"Designed responsive web experiences for early-stage teams. Facilitated usability sessions and translated findings into clear product improvements."}
        ],
        education=[{"degree":"B.Des. Interaction Design", "school":"Toronto Metropolitan University", "location":"Toronto", "dates":"2015 — 2019", "description":"Graduated with distinction."}],
        skills=[{"name":"Figma", "level":"Advanced"},{"name":"Prototyping", "level":"Advanced"},{"name":"Usability research", "level":"Intermediate"},{"name":"Design systems", "level":"Advanced"}],
        certificates=[{"name":"Accessibility for Designers", "issuer":"Interaction Design Foundation", "date":"2023", "url":""}],
        languages=[{"name":"English", "level":"Native"},{"name":"French", "level":"Professional"}],
        projects=[{"name":"OpenCity Service Map", "dates":"2023", "description":"A volunteer project mapping accessible community services.", "url":"https://example.com/opencity"}],
        links=[{"label":"Portfolio", "url":"https://example.com/alex"},{"label":"LinkedIn", "url":"https://linkedin.com/in/example"}],
        template_id="modern_summit",
    )
