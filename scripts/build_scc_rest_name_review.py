#!/usr/bin/env python3
"""Build a review CSV of SCC name candidates for the rest of the attendance book.

This script focuses on pages 16-72 by default and OCRs only the left name
column to improve extraction quality.
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGES_DIR = ROOT / "data" / "staging" / "scc_ocr" / "pages"
DEFAULT_OUT = ROOT / "data" / "staging" / "scc_ocr" / "scc_rest_name_review_pages16_72.csv"

PAGE_RE = re.compile(r"page-(\d+)\.png$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract SCC name candidates for manual review")
    parser.add_argument("--pages-dir", default=str(PAGES_DIR), help="Directory containing page-XX.png files")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output CSV path")
    parser.add_argument("--start-page", type=int, default=16, help="First page number to process")
    parser.add_argument("--end-page", type=int, default=72, help="Last page number to process")
    parser.add_argument("--crop-width-pct", type=int, default=24, help="Percent width for name-column crop")
    return parser.parse_args()


def clean_ocr_name(s: str) -> str:
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    # Keep letters, spaces, apostrophes, periods, hyphens, ampersands.
    s = re.sub(r"[^A-Za-z .&'\-]", "", s)
    s = re.sub(r"\s+", " ", s).strip(" .,-")
    return s


def looks_like_name(s: str) -> bool:
    if len(s) < 5:
        return False
    if len(s) > 50:
        return False
    if sum(ch.isalpha() for ch in s) < 4:
        return False
    low = s.lower()
    blocked = (
        "names",
        "time of",
        "freshmen",
        "sophomores",
        "juniors",
        "seniors",
        "bachelors",
        "masters",
        "dismiss",
        "honorary",
        "distinction",
    )
    if any(b in low for b in blocked):
        return False
    # Avoid lines that are mostly repeated initials/noise.
    words = s.split()
    if len(words) == 1 and len(words[0]) <= 2:
        return False
    return True


def score_name_candidate(s: str) -> int:
    score = 0
    tokens = [t for t in s.split() if t]
    if 2 <= len(tokens) <= 5:
        score += 2
    elif len(tokens) == 1:
        score -= 1

    alpha_ratio = sum(ch.isalpha() for ch in s) / max(len(s), 1)
    if alpha_ratio >= 0.82:
        score += 2
    elif alpha_ratio >= 0.70:
        score += 1
    else:
        score -= 1

    title_like = 0
    for t in tokens:
        plain = re.sub(r"[^A-Za-z]", "", t)
        if not plain:
            continue
        if plain[0].isupper() and plain[1:].islower():
            title_like += 1
    if title_like >= 2:
        score += 2
    elif title_like == 1:
        score += 1

    if any(len(t) == 1 for t in tokens):
        score -= 1

    low = s.lower()
    if any(k in low for k in ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec", "time", "fresh", "soph", "junior", "senior", "dismiss")):
        score -= 3

    return score


def confidence_from_score(score: int) -> str:
    if score >= 5:
        return "high"
    if score >= 3:
        return "medium"
    return "low"


def ocr_name_column(image_path: Path, crop_width_pct: int) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        cropped = tmp / "cropped.png"

        magick_cmd = [
            "magick",
            str(image_path),
            "-colorspace",
            "Gray",
            "-deskew",
            "40%",
            "-contrast-stretch",
            "1%x1%",
            "-sharpen",
            "0x1.1",
            "-crop",
            f"{crop_width_pct}%x100%+0+0",
            "+repage",
            str(cropped),
        ]
        subprocess.run(magick_cmd, check=True, capture_output=True, text=True)

        tesseract_cmd = [
            "tesseract",
            str(cropped),
            "stdout",
            "-l",
            "eng",
            "--psm",
            "6",
        ]
        result = subprocess.run(tesseract_cmd, check=True, capture_output=True, text=True)
        return result.stdout


def iter_page_files(pages_dir: Path, start_page: int, end_page: int) -> list[tuple[int, Path]]:
    out: list[tuple[int, Path]] = []
    for p in sorted(pages_dir.glob("page-*.png")):
        m = PAGE_RE.search(p.name)
        if not m:
            continue
        page_no = int(m.group(1))
        if start_page <= page_no <= end_page:
            out.append((page_no, p))
    return out


def main() -> None:
    args = parse_args()
    pages_dir = Path(args.pages_dir)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    processed_pages = 0
    failed_pages = 0

    for page_no, image_path in iter_page_files(pages_dir, args.start_page, args.end_page):
        try:
            text = ocr_name_column(image_path, args.crop_width_pct)
            processed_pages += 1
        except Exception:
            failed_pages += 1
            continue

        for line_idx, raw_line in enumerate(text.splitlines(), start=1):
            cleaned = clean_ocr_name(raw_line)
            if not looks_like_name(cleaned):
                continue

            score = score_name_candidate(cleaned)
            confidence = confidence_from_score(score)
            if confidence == "low":
                continue

            rows.append(
                {
                    "source_file": image_path.name,
                    "page_number": page_no,
                    "line_number": line_idx,
                    "raw_name_ocr": raw_line.strip(),
                    "candidate_name": cleaned,
                    "candidate_confidence": confidence,
                    "review_status": "needs_review",
                    "reviewed_full_name": "",
                    "reviewed_start_year": "",
                    "reviewed_end_year": "",
                    "reviewer_notes": "",
                }
            )

    fieldnames = [
        "source_file",
        "page_number",
        "line_number",
        "raw_name_ocr",
        "candidate_name",
        "candidate_confidence",
        "review_status",
        "reviewed_full_name",
        "reviewed_start_year",
        "reviewed_end_year",
        "reviewer_notes",
    ]

    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"Wrote: {out_path}")
    print(f"Pages processed: {processed_pages}")
    print(f"Pages failed: {failed_pages}")
    print(f"Candidate rows: {len(rows)}")


if __name__ == "__main__":
    main()
