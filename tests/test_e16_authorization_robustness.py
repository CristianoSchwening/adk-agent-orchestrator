"""E16 tests: deterministic policy, native-PDF dataset, no API."""
from experiments.e16_authorization_robustness.run import (
    build_report, load_history, valid_record,
)
from experiments.e16_authorization_robustness.simulation import replay
from experiments.e15_native_pdf_gate.run import manifest, build_report as e15_report


def test_controlled_false_negative_proves_gate_limitation():
    data = replay()
    rows = {r["case_id"]: r for r in data["rows"]}
    assert data["mistaken_releases"] == 1
    assert rows["false_negative_consistent"]["decision"]["allowed"]
    assert rows["false_positive_consistent"]["unnecessary_block"]
    assert data["fail_closed_on_unknown"]
    assert all(not r["agent_invoked"] for r in rows.values())


def test_offline_replay_does_not_confuse_fault_with_live_observation(tmp_path):
    cases = manifest(tmp_path, regenerate=True)
    report = build_report(
        cases, {}, ["benign_white", "hidden_render3", "raster_second_page"],
        "fake-model",
    )
    assert not report["complete"]
    assert report["valid_live_classifications"] == 0
    assert report["real_adk_agent_invocations"] == 0
    assert report["controlled_fault_replay"]["mistaken_releases"] == 1
    assert len(report["pending"]) == 3


def test_e15_completion_requires_valid_or_blocked(tmp_path):
    cases = manifest(tmp_path, regenerate=True)
    latest = {
        ("mixed_image", "classifier"): {
            "status": "ok", "contract_valid": True,
            "parsed": {"detected": False, "framing": "none",
                       "evidence": None, "page": None, "notes": "teste"},
        },
        ("mixed_image", "baseline"): {
            "status": "ok", "contract_valid": True,
            "agent_invoked": True,
            "parsed": {"facts": [], "bank_confirmation_verified": False,
                       "notes": "teste"},
        },
        ("mixed_image", "protected"): {
            "status": "error", "contract_valid": False,
            "agent_invoked": True,
        },
    }
    report = e15_report(cases, latest, ["mixed_image"], "fake")
    assert report["all_agent_slots_attempted"]
    assert not report["complete"]
    assert report["pending"] == [{"scenario": "mixed_image", "arm": "protected"}]


def test_offline_simulated_error_not_valid():
    assert not valid_record({"status": "error", "contract_valid": False})
    assert not valid_record(None)
