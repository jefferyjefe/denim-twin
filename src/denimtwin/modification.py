"""Structured modification representation (plan §4.5). Every modification is explicit parameters, never free text.
The simulator consumes this; natural language would be converted into it upstream."""
from dataclasses import dataclass, asdict, field
from typing import Optional, List
import json

@dataclass
class WashProtocol:
    cycles: int = 1
    machine: Optional[str] = None
    cycle: Optional[str] = None
    water_temperature_c: Optional[float] = None
    detergent_type: Optional[str] = None
    detergent_amount_ml: Optional[float] = None
    dryer_method: Optional[str] = None       # tumble | hang | flat
    dryer_setting: Optional[str] = None

@dataclass
class CutModification:
    kind: str = "cut"                         # only 'cut' in v1; bleach/dye/patch are banned in year one
    # cut geometry — exactly one of target_inseam_cm / inseam_fraction / cut_path must be given
    target_inseam_cm: Optional[float] = None
    inseam_fraction: Optional[float] = None   # 0 = crotch, 1 = original hem (canonical inseam coordinate)
    outer_fraction: Optional[float] = None    # for angled cuts: outseam-side fraction (None = same as inseam side)
    cut_path_canonical: Optional[List[List[float]]] = None   # polyline in canonical [0,1]^2 coordinates (front panel)
    tool: str = "fabric_shears"               # fabric_shears | rotary_cutter | scissors | box_cutter
    garment_flat: bool = True                 # cut flat (vs worn)
    legs_together: bool = False
    edge_treatment: str = "raw"               # raw | cuffed | hemmed | serged | hand_frayed
    wash: WashProtocol = field(default_factory=WashProtocol)
    seed: int = 0

    def validate(self):
        given = [x is not None for x in (self.target_inseam_cm, self.inseam_fraction, self.cut_path_canonical)]
        assert sum(given) == 1, "give exactly one of target_inseam_cm, inseam_fraction, cut_path_canonical"
        assert self.kind == "cut", "year-one modifications are cuts only (see docs/PLAN.md §14/§16)"
        assert self.edge_treatment in ("raw", "cuffed", "hemmed", "serged", "hand_frayed")
        return self

    def to_json(self): return json.dumps(asdict(self), indent=1)
    @staticmethod
    def from_json(s):
        d = json.loads(s); w = d.pop("wash", {}) or {}
        return CutModification(wash=WashProtocol(**w), **d).validate()

    def expects_fringe(self):
        """Raw/hand-frayed edges fray with washing; finished hems do not."""
        return self.edge_treatment in ("raw", "hand_frayed") and self.wash.cycles >= 1
