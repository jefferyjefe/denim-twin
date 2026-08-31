"""Covering the whole way round a cut hem, and knowing which parts are not covered yet.

After the cut, each leg carries a closed loop of raw edge. The protocol measures fray depth, thread
count and edge curl every 2 cm around that loop (PROTOCOL.md 5), which means the photographs have to
resolve the edge everywhere -- not on average, and not wherever the operator happened to point.

Two things make this harder than "take enough macros".

FRAY IS UNRESOLVABLE AT FLAT-LAY DISTANCE. A frayed thread is a fraction of a millimetre across, so
the whole-garment frame that measures the silhouette cannot measure the edge. That is why the series
is macros: roughly 10 cm of edge filling a frame, which puts the scale near 0.025 mm/px on a phone's
main camera and makes a 0.5 mm fray depth a 20-pixel measurement instead of a 2-pixel one.

A MEASUREMENT POSITION NEAR A FRAME EDGE IS NOT MEASURABLE. Lens distortion is worst at the frame
edge, the ruler may not reach, and a thread can lie outside the frame. So each macro has a USABLE
arc smaller than the arc it spans, and the series is planned on the usable arc. This is where naive
coverage arithmetic goes wrong: N macros of 10 cm do not cover N x 10 cm of hem, and a plan built on
that assumption leaves gaps exactly where consecutive frames meet.

The loop is parameterised in millimetres of arc from a fixed origin -- the inseam seam, travelling
toward the front of the leg first -- so a position has one identity, and the same position number
means the same place on every visit and in every state.
"""
import math

#: Roughly 10 cm of cut edge should fill a macro frame; that is what makes fray resolvable.
DEFAULT_ARC_MM = 100.0
#: The band at each end of a frame where a measurement is not trusted: lens distortion is worst
#: there and a thread can lie out of frame. Positions inside this band do not count as covered.
DEFAULT_EDGE_MARGIN_MM = 12.0
#: PROTOCOL.md 5: every 2 cm around the loop.
DEFAULT_POSITION_SPACING_MM = 20.0
#: Edge curl is a vertical lift off the surface, so an overhead frame cannot see it at all; the
#: side profiles are spaced more coarsely because curl varies slowly compared with fray.
DEFAULT_PROFILE_SPACING_MM = 40.0


class HemGeometry(object):
    """The loop of one leg's cut edge, in millimetres of arc from the inseam seam."""

    def __init__(self, leg, circumference_mm, *, arc_mm=DEFAULT_ARC_MM,
                 edge_margin_mm=DEFAULT_EDGE_MARGIN_MM,
                 position_spacing_mm=DEFAULT_POSITION_SPACING_MM,
                 profile_spacing_mm=DEFAULT_PROFILE_SPACING_MM):
        if circumference_mm <= 0:
            raise ValueError("hem circumference must be positive")
        if arc_mm <= 2 * edge_margin_mm:
            raise ValueError("a macro whose usable arc is not positive covers nothing")
        self.leg = leg
        self.circumference_mm = float(circumference_mm)
        self.arc_mm = float(arc_mm)
        self.edge_margin_mm = float(edge_margin_mm)
        self.position_spacing_mm = float(position_spacing_mm)
        self.profile_spacing_mm = float(profile_spacing_mm)

    @classmethod
    def from_leg_opening(cls, leg, leg_opening_flat_cm, **kw):
        """A flat leg-opening measurement is half the loop: the hem is measured folded."""
        return cls(leg, 2.0 * float(leg_opening_flat_cm) * 10.0, **kw)

    @property
    def usable_arc_mm(self):
        return self.arc_mm - 2 * self.edge_margin_mm

    # -- positions ---------------------------------------------------------------------------

    def positions(self):
        """Measurement positions, numbered from 1 at the inseam seam, travelling toward the front."""
        n = int(math.floor(self.circumference_mm / self.position_spacing_mm))
        return [{"index": i + 1, "arc_mm": round(i * self.position_spacing_mm, 2)}
                for i in range(n)]

    def profile_positions(self):
        n = int(math.floor(self.circumference_mm / self.profile_spacing_mm))
        return [{"index": i + 1, "arc_mm": round(i * self.profile_spacing_mm, 2)}
                for i in range(n)]

    # -- the macro series --------------------------------------------------------------------

    def macros(self):
        """The overlapping macro frames that cover the loop with no gap.

        Consecutive frames advance by the USABLE arc, not the full arc, so the untrusted bands at
        their ends overlap each other rather than meeting. The number of frames is therefore
        ceil(circumference / usable_arc), and the last frame's overlap with the first is whatever is
        left over -- the loop closes.
        """
        n = int(math.ceil(self.circumference_mm / self.usable_arc_mm))
        out = []
        for i in range(n):
            centre = (i + 0.5) * self.usable_arc_mm
            start = centre - self.arc_mm / 2.0
            out.append({
                "index": i + 1,
                "shot_suffix": "P%02d" % (i + 1),
                "start_mm": round(start, 2),
                "end_mm": round(start + self.arc_mm, 2),
                "usable_start_mm": round(start + self.edge_margin_mm, 2),
                "usable_end_mm": round(start + self.arc_mm - self.edge_margin_mm, 2),
                "supports_positions": [],
            })
        for m in out:
            m["supports_positions"] = [p["index"] for p in self.positions()
                                       if self._in_usable(p["arc_mm"], m)]
        return out

    def _in_usable(self, arc_mm, macro):
        """Is this arc position inside the macro's trusted band, allowing for the loop wrapping?"""
        c = self.circumference_mm
        for shift in (-c, 0.0, c):
            if macro["usable_start_mm"] <= arc_mm + shift <= macro["usable_end_mm"]:
                return True
        return False

    # -- coverage ----------------------------------------------------------------------------

    def coverage(self, captured_indices):
        """Which measurement positions the captured macros actually support, and which are gaps.

        `captured_indices` are macro indices with an ACCEPTED capture. A position supported by no
        accepted macro is a gap, and a gap is a hole in the fray profile, not a rounding detail --
        the profile is the measurement.
        """
        captured = set(int(i) for i in captured_indices)
        macros = self.macros()
        support = {}
        for m in macros:
            if m["index"] not in captured:
                continue
            for p in m["supports_positions"]:
                support.setdefault(p, []).append(m["index"])
        positions = self.positions()
        covered = [p for p in positions if p["index"] in support]
        gaps = [p for p in positions if p["index"] not in support]
        return {
            "leg": self.leg,
            "circumference_mm": self.circumference_mm,
            "n_positions": len(positions),
            "n_covered": len(covered),
            "n_gaps": len(gaps),
            "complete": not gaps,
            "fraction": (len(covered) / float(len(positions))) if positions else 0.0,
            "gap_positions": [p["index"] for p in gaps],
            "gap_arcs_mm": [p["arc_mm"] for p in gaps],
            "multiply_supported": {p: v for p, v in support.items() if len(v) > 1},
            "support": support,
        }

    def next_macro(self, captured_indices):
        """The macro that closes the largest gap. Deterministic: lowest index among the best."""
        captured = set(int(i) for i in captured_indices)
        best = None
        for m in self.macros():
            if m["index"] in captured:
                continue
            gain = len([p for p in m["supports_positions"]
                        if p not in self.coverage(captured)["support"]])
            if best is None or gain > best[0]:
                best = (gain, m)
        return best[1] if best else None


def required_macro_count(leg_opening_flat_cm, arc_mm=DEFAULT_ARC_MM,
                         edge_margin_mm=DEFAULT_EDGE_MARGIN_MM):
    """How many macros one leg needs. Stated as arithmetic so the runbook can show its working."""
    g = HemGeometry("x", 2.0 * float(leg_opening_flat_cm) * 10.0, arc_mm=arc_mm,
                    edge_margin_mm=edge_margin_mm)
    return len(g.macros())


def mm_per_px_ceiling(fray_resolution_mm=0.5, px_per_feature=10.0):
    """The resolution a fray measurement needs, from the size of the thing being measured.

    A fray depth is read to about 0.5 mm. Measuring a 0.5 mm feature with a handful of pixels is
    what makes the reading noise-dominated, so require ten pixels across it: 0.5 / 10 = 0.05 mm/px.
    A phone's main camera at a 100 mm frame width on a 4032 px sensor gives 0.025 mm/px, so this
    ceiling is reachable with margin -- which is the point of stating it rather than guessing.
    """
    return float(fray_resolution_mm) / float(px_per_feature)
