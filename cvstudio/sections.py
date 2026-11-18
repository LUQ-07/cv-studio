"""Data-entry sections: field specs per category + a Qt-free list model (add / edit / delete / move).

Everything here is FREE for all users. Only exporting with a Premium *template* is gated (see store_iap.py).
"""
from __future__ import annotations

from dataclasses import dataclass

LEVELS_SKILL = ["", "Beginner", "Intermediate", "Advanced", "Expert"]
LEVELS_LANG = ["", "Native", "Fluent", "Advanced (C1)", "Upper-intermediate (B2)", "Intermediate", "Basic"]


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    kind: str = "line"          # line | text | combo | file
    options: tuple = ()
    required: bool = False
    placeholder: str = ""


@dataclass(frozen=True)
class SectionSpec:
    key: str                    # attribute name on CVProfile
    title: str                  # tab title
    fields: tuple
    primary: str                # field used as the row title in the list
    secondary: tuple = ()       # fields shown after the title in the list


F = Field
SPECS: dict[str, SectionSpec] = {s.key: s for s in [
    SectionSpec("experience", "Experience", (
        F("role", "Role / job title", required=True), F("company", "Company"), F("location", "Location"), F("dates", "Dates", placeholder="2021 — Present"),
        F("description", "Achievements / description", "text", placeholder="Start a line with - to make a bullet point.")), "role", ("company", "dates")),
    SectionSpec("internships", "Internships", (
        F("role", "Role", required=True), F("company", "Company"), F("location", "Location"), F("dates", "Dates"), F("description", "Description", "text")), "role", ("company", "dates")),
    SectionSpec("education", "Education", (
        F("degree", "Degree / field of study", required=True), F("school", "School / university"), F("location", "Location"), F("dates", "Dates"), F("description", "Notes", "text")), "degree", ("school", "dates")),
    SectionSpec("skills", "Skills", (
        F("name", "Skill name", required=True), F("level", "Level", "combo", tuple(LEVELS_SKILL))), "name", ("level",)),
    SectionSpec("languages", "Languages", (
        F("name", "Language name", required=True), F("level", "Proficiency level", "combo", tuple(LEVELS_LANG))), "name", ("level",)),
    SectionSpec("certificates", "Certificates", (
        F("name", "Certificate name", required=True), F("issuer", "Issuing organization"), F("date", "Date"), F("url", "Credential link", placeholder="https://…"),
        F("attachment", "Optional local file (PDF / image)", "file"), F("description", "Notes", "text")), "name", ("issuer", "date")),
    SectionSpec("courses", "Courses", (
        F("name", "Course title", required=True), F("issuer", "Provider / school"), F("date", "Date / year"), F("description", "What you learned", "text")), "name", ("issuer", "date")),
    SectionSpec("projects", "Projects", (
        F("title", "Project title", required=True), F("role", "Your role"), F("technologies", "Technologies used", placeholder="Python, Qt, SQL"),
        F("url", "Project link", placeholder="https://…"), F("description", "Description", "text")), "title", ("role",)),
    SectionSpec("publications", "Publications", (
        F("title", "Title", required=True), F("organization", "Publisher / journal"), F("date", "Date"), F("url", "Link", placeholder="https://…"), F("description", "Notes", "text")), "title", ("organization", "date")),
    SectionSpec("awards", "Awards", (
        F("name", "Award title", required=True), F("issuer", "Awarded by"), F("date", "Year"), F("description", "Details", "text")), "name", ("issuer", "date")),
    SectionSpec("volunteer", "Volunteer", (
        F("role", "Role", required=True), F("organization", "Organization"), F("dates", "Dates"), F("description", "Details", "text")), "role", ("organization", "dates")),
    SectionSpec("memberships", "Memberships", (
        F("name", "Membership", required=True), F("organization", "Organization"), F("dates", "Since / dates")), "name", ("organization", "dates")),
    SectionSpec("references", "References", (
        F("name", "Reference name", required=True), F("company", "Position / company"), F("description", "Contact details", "text", placeholder="Email, phone…")), "name", ("company",)),
    SectionSpec("hobbies", "Interests", (F("name", "Interest / hobby", required=True),), "name", ()),
    SectionSpec("links", "Links", (F("label", "Label", required=True), F("url", "URL", placeholder="https://…")), "label", ("url",)),
    SectionSpec("custom_sections", "Custom sections", (F("title", "Section title", required=True), F("content", "Content", "text")), "title", ()),
]}
ORDER = list(SPECS)


class SectionModel:
    """Entries of one section. Mutates the list it is given in place, so one central dict can own all data."""

    def __init__(self, spec: SectionSpec, rows: list | None = None):
        self.spec = spec
        self.rows: list[dict] = rows if rows is not None else []

    # -- display
    def label(self, row: dict) -> str:
        main = (row.get(self.spec.primary) or "").strip() or "(untitled)"
        extra = [(row.get(k) or "").strip() for k in self.spec.secondary]
        extra = [e for e in extra if e]
        return main + ("  —  " + "  ·  ".join(extra) if extra else "")

    def labels(self) -> list[str]:
        return [self.label(r) for r in self.rows]

    # -- validation
    def clean(self, values: dict) -> dict:
        return {f.key: str(values.get(f.key, "") or "").strip() for f in self.spec.fields}

    def missing(self, values: dict) -> list[str]:
        v = self.clean(values)
        return [f.label for f in self.spec.fields if f.required and not v[f.key]]

    # -- CRUD
    def add(self, values: dict) -> int:
        if self.missing(values):
            raise ValueError("Required: " + ", ".join(self.missing(values)))
        self.rows.append(self.clean(values))
        return len(self.rows) - 1

    def update(self, index: int, values: dict) -> None:
        if not 0 <= index < len(self.rows):
            raise IndexError(index)
        if self.missing(values):
            raise ValueError("Required: " + ", ".join(self.missing(values)))
        self.rows[index] = self.clean(values)

    def delete(self, index: int) -> dict:
        return self.rows.pop(index)

    def move(self, index: int, delta: int) -> int:
        target = index + delta
        if 0 <= index < len(self.rows) and 0 <= target < len(self.rows):
            self.rows[index], self.rows[target] = self.rows[target], self.rows[index]
            return target
        return index

    def replace_all(self, rows) -> None:
        normalised = []
        for r in rows or []:
            r = {self.spec.fields[0].key: r} if isinstance(r, str) else dict(r)
            normalised.append({**{f.key: "" for f in self.spec.fields}, **r})   # keep unknown keys too
        self.rows[:] = normalised
