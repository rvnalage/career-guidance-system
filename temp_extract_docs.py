import glob
import os
import re
import zipfile
import xml.etree.ElementTree as ET

BASE = r"e:\documents\rahul_sorted\mtech_documents\mtech_final_year_project\one_note_extract"
OUT = os.path.join(BASE, "_doc_extract.txt")

PATTERNS = [
    "Agentic Artificial Intelligence for Personalized Career Guidance.docx",
    "System Architecture.docx",
    "Chapter 3*Proposed System.docx",
    "Chapter 4*Proposed Methodology*System Design.docx",
    "Tools and Technologies.docx",
    "Implementation Plan.docx",
    "Weekwise plan.docx",
]

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def resolve(pattern: str) -> str:
    matches = glob.glob(os.path.join(BASE, pattern))
    return matches[0] if matches else ""


def extract_docx(path: str) -> list[str]:
    with zipfile.ZipFile(path, "r") as zf:
        xml_bytes = zf.read("word/document.xml")
    root = ET.fromstring(xml_bytes)
    body = root.find("w:body", NS)
    lines: list[str] = []
    if body is None:
        return lines

    for child in body:
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            txt = "".join(t.text for t in child.findall(".//w:t", NS) if t.text)
            txt = clean(txt)
            if txt:
                lines.append(txt)
        elif tag == "tbl":
            rows: list[str] = []
            for tr in child.findall(".//w:tr", NS):
                cells: list[str] = []
                for tc in tr.findall("w:tc", NS):
                    ctext = "".join(t.text for t in tc.findall(".//w:t", NS) if t.text)
                    ctext = clean(ctext)
                    cells.append(ctext)
                if any(cells):
                    rows.append(" | ".join(cells))
            if rows:
                lines.append("[TABLE]")
                lines.extend(rows)
                lines.append("[/TABLE]")
    return lines


with open(OUT, "w", encoding="utf-8") as out:
    for p in PATTERNS:
        path = resolve(p)
        out.write("=" * 100 + "\n")
        out.write(f"FILE: {path or p}\n")
        out.write("=" * 100 + "\n")
        if not path:
            out.write("[ERROR] File not found\n\n")
            continue
        try:
            lines = extract_docx(path)
            if not lines:
                out.write("[WARN] No text extracted\n")
            else:
                for line in lines:
                    out.write(line + "\n")
            out.write(f"[META] extracted_lines={len(lines)}\n")
        except Exception as exc:
            out.write(f"[ERROR] {exc}\n")
        out.write("\n")

print(OUT)
