from src.contract_gate import ContractGateReport


def test_contract_gate_requires_all_evidence():
    assert ContractGateReport(True, True, True).passed
    report = ContractGateReport(False, True, True)
    assert report.status == "blocked"
    assert report.failed_gates == ("schema",)


def test_privacy_or_pricing_failure_blocks_even_with_verified_schema():
    assert ContractGateReport(True, False, True).failed_gates == ("privacy",)
    assert ContractGateReport(True, True, False).failed_gates == ("pricing",)
