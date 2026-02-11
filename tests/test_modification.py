import sys, os; sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import pytest
from denimtwin.modification import CutModification, WashProtocol
def test_roundtrip_and_validation():
    m = CutModification(inseam_fraction=0.35, edge_treatment="raw", wash=WashProtocol(cycles=1, dryer_method="tumble")).validate()
    assert CutModification.from_json(m.to_json()) == m and m.expects_fringe()
    assert not CutModification(inseam_fraction=0.3, edge_treatment="cuffed").validate().expects_fringe()
    with pytest.raises(AssertionError): CutModification().validate()
    with pytest.raises(AssertionError): CutModification(inseam_fraction=0.3, target_inseam_cm=20).validate()
    with pytest.raises(AssertionError): CutModification(kind="bleach", inseam_fraction=0.3).validate()
