"""
Synthetic public dataset generator for the Automated Member Data Migration
and QA System.

Generates a fully fictional member dataset that exercises every cleaning,
validation, and duplicate-handling rule in the pipeline. None of the names
or numbers below are derived from any real record.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import DEFAULT_SAMPLE_INPUT

# Fully fictional English/Nepali name pairs, independently invented for
# demonstration purposes only.
_FICTIONAL_PEOPLE = [
    ("Aashish Thapa", "आशीष थापा", "Male"),
    ("Bimala Gurung", "बिमला गुरुङ", "Female"),
    ("Chandra Bahadur Rai", "चन्द्र बहादुर राई", "Male"),
    ("Devika Sharma", "देविका शर्मा", "Female"),
    ("Ekraj Basnet", "एकराज बस्नेत", "Male"),
    ("Fulmaya Tamang", "फूलमाया तामाङ", "Female"),
    ("Gopal Adhikari", "गोपाल अधिकारी", "Male"),
    ("Hema Kumari Chhetri", "हेमा कुमारी क्षेत्री", "Female"),
    ("Ishwor Poudel", "ईश्वर पौडेल", "Male"),
    ("Januka Magar", "जानुका मगर", "Female"),
    ("Kalpana Lama", "कल्पना लामा", "Female"),
    ("Laxman Oli", "लक्ष्मण ओली", "Male"),
    ("Manju Khadka", "मन्जु खड्का", "Female"),
    ("Narayan Bhattarai", "नारायण भट्टराई", "Male"),
    ("Oshin Karki", "ओशिन कार्की", "Female"),
    ("Prakash Neupane", "प्रकाश न्यौपाने", "Male"),
    ("Quinta Shrestha", "क्विन्टा श्रेष्ठ", "Female"),
    ("Rabin Ghimire", "रबिन घिमिरे", "Male"),
    ("Sabita Pandey", "सबिता पाण्डे", "Female"),
    ("Tek Bahadur Bista", "टेक बहादुर बिष्ट", "Male"),
]


def build_synthetic_records() -> list:
    """Build a list of synthetic member dicts covering many data-quality scenarios."""
    records = []
    member_no = 100

    # 1. Clean valid baseline records (covers most of _FICTIONAL_PEOPLE)
    for name, nepali, gender in _FICTIONAL_PEOPLE:
        member_no += 1
        records.append(
            {"Member No.": member_no, "Members Name": name, "NEPALI NAME": nepali, "Gender": gender}
        )

    # 2. Extra whitespace in name fields
    member_no += 1
    records.append(
        {
            "Member No.": member_no,
            "Members Name": "  Sunita   Poudel ",
            "NEPALI NAME": "  सुनिता   पौडेल ",
            "Gender": "female",
        }
    )

    # 3. Missing optional Nepali name
    member_no += 1
    records.append(
        {"Member No.": member_no, "Members Name": "Bikash Rana", "NEPALI NAME": None, "Gender": "Male"}
    )

    # 4. Missing gender
    member_no += 1
    records.append(
        {"Member No.": member_no, "Members Name": "Kabita Thapa", "NEPALI NAME": "कविता थापा", "Gender": None}
    )

    # 5. Different valid gender formats
    member_no += 1
    records.append({"Member No.": member_no, "Members Name": "Suraj Nepal", "NEPALI NAME": "सुरज नेपाल", "Gender": "M"})
    member_no += 1
    records.append({"Member No.": member_no, "Members Name": "Anita Rai", "NEPALI NAME": "अनिता राई", "Gender": "F"})
    member_no += 1
    records.append({"Member No.": member_no, "Members Name": "Dipesh Koirala", "NEPALI NAME": "दिपेश कोइराला", "Gender": "MALE"})

    # 6. Unsupported gender value
    member_no += 1
    records.append(
        {"Member No.": member_no, "Members Name": "Ramesh Basnet", "NEPALI NAME": "रमेश बस्नेत", "Gender": "Other"}
    )

    # 7. Exact duplicate pair (identical member number, name, nepali name, gender)
    member_no += 1
    dup_no = member_no
    records.append(
        {"Member No.": dup_no, "Members Name": "Nirmala Gautam", "NEPALI NAME": "निर्मला गौतम", "Gender": "Female"}
    )
    records.append(
        {"Member No.": dup_no, "Members Name": "Nirmala Gautam", "NEPALI NAME": "निर्मला गौतम", "Gender": "Female"}
    )

    # 8. Same member number, same normalized name, different completeness (one missing nepali/gender)
    member_no += 1
    same_no = member_no
    records.append(
        {"Member No.": same_no, "Members Name": "Bishnu Adhikari", "NEPALI NAME": "बिष्णु अधिकारी", "Gender": "Male"}
    )
    records.append(
        {"Member No.": same_no, "Members Name": "bishnu   adhikari", "NEPALI NAME": None, "Gender": None}
    )

    # 9. Same member number, conflicting names -> manual review
    member_no += 1
    conflict_no = member_no
    records.append(
        {"Member No.": conflict_no, "Members Name": "Ganga Bahadur K.C.", "NEPALI NAME": "गंगा बहादुर केसी", "Gender": "Male"}
    )
    records.append(
        {"Member No.": conflict_no, "Members Name": "Sarita Devkota", "NEPALI NAME": "सरिता देवकोटा", "Gender": "Female"}
    )

    # 10. Missing member number
    records.append(
        {"Member No.": None, "Members Name": "Unnamed Member One", "NEPALI NAME": None, "Gender": "Male"}
    )

    # 11. Invalid (non-numeric) member number
    records.append(
        {"Member No.": "ABC123", "Members Name": "Unnamed Member Two", "NEPALI NAME": None, "Gender": "Female"}
    )

    # 12. Fractional (invalid) member number
    records.append(
        {"Member No.": 245.5, "Members Name": "Unnamed Member Three", "NEPALI NAME": None, "Gender": "Male"}
    )

    # 13. Missing member name
    member_no += 1
    records.append(
        {"Member No.": member_no, "Members Name": None, "NEPALI NAME": "नामविहीन सदस्य", "Gender": "Female"}
    )

    # 14. Leading-zero text-style member number
    records.append(
        {"Member No.": "0099", "Members Name": "Purna Bahadur Thapa", "NEPALI NAME": "पूर्ण बहादुर थापा", "Gender": "Male"}
    )

    return records


def generate_sample_workbook(output_path: Path = DEFAULT_SAMPLE_INPUT) -> Path:
    """Generate the synthetic demonstration workbook and save it to disk."""
    records = build_synthetic_records()
    df = pd.DataFrame(records)
    # Introduce an irregularly spaced/punctuated header to mirror real-world
    # source-file inconsistencies, matching the tolerant header-matching logic.
    df = df.rename(
        columns={
            "Member No.": " Member No# ",
            "Members Name": " Members Name",
            "NEPALI NAME": "NEPALI NAME ",
            "Gender": "Gender",
        }
    )
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(output_path, index=False, engine="openpyxl", sheet_name="synthetic member data")
    return output_path
