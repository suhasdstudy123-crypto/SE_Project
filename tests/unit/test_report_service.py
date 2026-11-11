"""Unit tests for the report service CSV helpers (SRS-F-023, Issue #23)."""

import csv
import io

import pytest

from src.services import report_service


@pytest.mark.parametrize(
    "value, expected",
    [
        ("=SUM(A1:A2)", "'=SUM(A1:A2)"),
        ("+91 98765", "'+91 98765"),
        ("-5", "'-5"),
        ("@cmd", "'@cmd"),
        ("Asha Rao", "Asha Rao"),
        (None, ""),
        (91.0, 91.0),
        (-5, -5),
    ],
)
def test_safe_cell_escapes_only_formula_text(value, expected):
    """Text that Excel would run as a formula gets a leading quote; numbers stay numbers."""
    assert report_service.safe_cell(value) == expected


def test_to_csv_has_bom_header_and_escaped_rows():
    """CSV text starts with a UTF-8 BOM (Excel), then the header, then safe rows."""
    text = report_service.to_csv(["SRN", "Name"], [["PES1", "=1+1"], ["PES2", None]])
    assert text.startswith("﻿")
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    assert rows == [["SRN", "Name"], ["PES1", "'=1+1"], ["PES2", ""]]
