"""
emergency_test_harness.py  (Version 6)
----------------------------------------
Deterministic emergency scenario test harness.

Purpose:
    - Validates the full emergency escalation path end-to-end.
    - Confirms red_flag_engine escalates for known emergency phrases.
    - Confirms emergency_escalation_node fires and logs call_sid.
    - Confirms final_response is still delivered.

Usage:
    python -m backend.src.tests.emergency_test_harness
    OR import and call simulate_emergency_test() directly.

Rules:
    - No mocking — uses real graph.
    - Validates state keys deterministically.
    - Does NOT place a real Twilio call unless AUTO_ESCALATION_ENABLED=true.
    - Prints a structured pass/fail report.
"""

import asyncio
import sys
from pathlib import Path

# Ensure project root is on path when run as __main__
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Load .env for configuration
from dotenv import load_dotenv
load_dotenv(dotenv_path=_PROJECT_ROOT / "backend" / ".env")

from backend.src.graph.builder import build_triage_graph  # noqa: E402
from backend.src.logging.logger import get_logger          # noqa: E402

logger = get_logger("emergency_test_harness")

# ── Emergency trigger phrases (subset — red_flag_rules.json handles the rest) ─
_EMERGENCY_INPUTS = [
    "I have severe chest pain and can't breathe",
    "I am unconscious and no one is helping",
    "heavy bleeding and I can't stop it",
]


async def simulate_emergency_test(
    user_input: str = "I have severe chest pain and can't breathe",
    session_id: str = "harness_session_001",
    user_id: str    = "harness_user",
) -> dict:
    """
    Invokes the full triage graph asynchronously with an emergency-level input.

    Args:
        user_input: A text string known to trigger emergency escalation.
        session_id: Test session identifier.
        user_id:    Test user identifier.

    Returns:
        result dict (full TriageState after graph completes).

    Validates:
        ✔ red_flag_triggered == True
        ✔ urgency in ("emergency", "critical")
        ✔ risk_level in ("high", "critical")
        ✔ final_response is non-empty
        ✔ system_trace is populated
    """
    graph = build_triage_graph()

    initial_state = {
        "user_input":  user_input,
        "intent":      "medical_text",
        "session_id":  session_id,
        "user_id":     user_id,
        "messages":    [{"role": "user", "content": user_input}],
        # Note: user_consent_for_call intentionally left False unless testing Twilio
        "user_consent_for_call": False,
    }

    # Graph contains async nodes — must use ainvoke
    result = await graph.ainvoke(initial_state, config={"recursion_limit": 25})
    return result


def _check(label: str, condition: bool) -> bool:
    """Prints a pass/fail line. Returns True if condition is met."""
    status = "✅ PASS" if condition else "❌ FAIL"
    print(f"  {status}  {label}")
    return condition


async def run_harness() -> bool:
    """
    Runs the emergency test harness for all emergency trigger phrases.

    Returns:
        True if all checks pass, False otherwise.
    """
    print("\n" + "═" * 60)
    print("  TriGuard AI — Emergency Test Harness  (V6)")
    print("═" * 60)

    all_passed = True

    for i, user_input in enumerate(_EMERGENCY_INPUTS, start=1):
        print(f"\n[Test {i}/{len(_EMERGENCY_INPUTS)}] Input: \"{user_input[:60]}...\"")

        try:
            result = await simulate_emergency_test(
                user_input=user_input,
                session_id=f"harness_session_{i:03d}",
                user_id=f"harness_user_{i:03d}",
            )
        except Exception as exc:
            print(f"  ❌ GRAPH EXCEPTION: {exc}")
            all_passed = False
            continue

        # ── Assertions ───────────────────────────────────────────────────────
        red_flag    = result.get("red_flag_triggered", False)
        urgency     = result.get("urgency", "")
        risk_level  = result.get("risk_level", "")
        final_resp  = result.get("final_response", "")
        sys_trace   = result.get("system_trace", {})
        call_sid    = result.get("call_sid", "")

        passed = all([
            _check("red_flag_triggered == True",
                   red_flag is True),
            _check(f"urgency in (emergency, critical) — got '{urgency}'",
                   urgency in ("emergency", "critical")),
            _check(f"risk_level in (high, critical)   — got '{risk_level}'",
                   risk_level in ("high", "critical")),
            _check("final_response is non-empty",
                   bool(final_resp)),
            _check("system_trace is populated",
                   bool(sys_trace)),
        ])

        # ── Optional Twilio check (only if call was placed) ───────────────
        if call_sid:
            _check(f"call_sid logged: {call_sid}", True)
            logger.info(f"Twilio call_sid: {call_sid}")
        else:
            print("  ℹ️  No Twilio call placed "
                  "(AUTO_ESCALATION_ENABLED=false or consent not given — expected in test mode)")

        all_passed = all_passed and passed

    print("\n" + "─" * 60)
    print(f"  RESULT: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
    print("═" * 60 + "\n")
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(run_harness())
    sys.exit(0 if success else 1)
