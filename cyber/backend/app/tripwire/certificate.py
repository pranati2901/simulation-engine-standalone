"""Certificate generation — verify code + certificate data for passing students."""
from __future__ import annotations

import hashlib
import time
import uuid


def generate_certificate(session_id: str, learner_name: str, scenario_title: str,
                         composite: float, grade: str) -> dict:
    """Generate a certificate for a passing student.

    Returns certificate data with a unique verify code.
    The verify code is a short, human-readable string that can be used
    to look up the certificate later.
    """
    cert_id = uuid.uuid4().hex[:16]
    # Verify code: 3 groups of 4 alphanumeric chars (e.g., MRX-7Q42-B3KD)
    raw = hashlib.sha256(f"{session_id}:{cert_id}:{time.time()}".encode()).hexdigest()
    verify_code = f"{raw[:4].upper()}-{raw[4:8].upper()}-{raw[8:12].upper()}"

    return {
        "certificate_id": cert_id,
        "verify_code": verify_code,
        "learner_name": learner_name,
        "scenario_title": scenario_title,
        "composite_score": round(composite, 1),
        "grade": grade,
        "issued_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "session_id": session_id,
    }
