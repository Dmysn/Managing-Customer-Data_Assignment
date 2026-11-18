"""Locate (or download) the pinned Studio North lab release that produced the baseline report.

The dashboard never regenerates data. It reuses the released CSVs, canonical SQL
and model code from exactly the same commit as the baseline report.
"""
from __future__ import annotations

import io
import sys
import urllib.request
import zipfile
from pathlib import Path

LAB_REPOSITORY = "https://github.com/longxiutian/customer-economics-lab"
LAB_COMMIT = "4848f4b75628bde8a43858bb54ca7c09de603f61"
# The baseline report was produced from 0e40ce3cd0b788a3914ca4eb9f90d58ae1b62903, which is no
# longer downloadable after the upstream history was rewritten. Its data/*.csv, data_manifest.json,
# sql/00_sources.sql, sql/01_views.sql, cohort_lab/model.py, analysis.py and data.py are
# byte-identical to LAB_COMMIT (verified by SHA-256), so the replay uses the same inputs and model.
BASELINE_REPORT_COMMIT = "0e40ce3cd0b788a3914ca4eb9f90d58ae1b62903"
ARCHIVE_URL = f"https://codeload.github.com/longxiutian/customer-economics-lab/zip/{LAB_COMMIT}"


def ensure_lab(project_root: Path, lab_dir: str | None = None) -> Path:
    """Return a lab checkout at LAB_COMMIT and make `cohort_lab` importable."""
    if lab_dir:
        path = Path(lab_dir).resolve()
    else:
        cache = project_root / ".lab"
        path = cache / f"customer-economics-lab-{LAB_COMMIT}"
        if not path.exists():
            cache.mkdir(parents=True, exist_ok=True)
            print(f"Downloading lab release {LAB_COMMIT[:12]} from GitHub ...", flush=True)
            with urllib.request.urlopen(ARCHIVE_URL, timeout=120) as response:
                payload = response.read()
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                archive.extractall(cache)
    for required in ("cohort_lab/model.py", "cohort_lab/analysis.py", "sql/01_views.sql", "data/data_manifest.json"):
        if not (path / required).exists():
            raise FileNotFoundError(f"{path} is not a Studio North lab checkout (missing {required})")
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
    return path
