from aether.workbench_prompt import WORKBENCH_ARCHITECT_SYSTEM_PROMPT


def test_architect_prompt_requires_exact_fact_inventory():
    text = WORKBENCH_ARCHITECT_SYSTEM_PROMPT
    assert "Inventory every named fact" in text
    assert "Emit named directories separately" in text
    assert "Count typed/formatted/cardinality facts" in text
    assert "cannot hide a stated child field" in text


def test_architect_prompt_final_audit_binds_generated_and_behavioral_proof():
    text = WORKBENCH_ARCHITECT_SYSTEM_PROMPT
    assert "direct source and independent current-interface comparison" in text
    assert "fresh public-interface probe in Solver and Verifier guidance" in text
    assert "behavioral for a fresh public-interface operation and observed response" in text
    assert "Shape or liveness cannot prove behavior" in text
    assert '"proof_obligation": "exact_state"' in text
    assert "Align obligation and route" in text
    assert "Never pair the last with exact_contract" in text
    assert "set contrast plus contrast_owner" in text
