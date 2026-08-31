/* The capture UI.
 *
 * One state object, one render pass, no framework. The reason is not minimalism: the page is used
 * one-handed while the other hand holds a garment, and the failure that matters is a screen whose
 * panels disagree -- READY in one place and a list of blocks in another -- because two fetches
 * landed out of order. So there is exactly one endpoint that returns everything, and every panel is
 * drawn from that one snapshot.
 */
'use strict';

var S = null;            // latest snapshot
var MAP = null;          // region geometry, fetched once
var GARMENT = null;
var SEL = null;          // region tapped on the map
var GHOST = false;
var CONFIRM = {};        // operator assertions staged for the next upload
var BUSY = false;

var $ = function (id) { return document.getElementById(id); };
var esc = function (s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
  });
};
function mins(sec) {
  if (sec == null) return '-';
  var m = Math.round(sec / 60);
  return m >= 60 ? (Math.floor(m / 60) + 'h ' + String(m % 60).padStart(2, '0') + 'm') : (m + ' min');
}
function showErr(msg) { var e = $('err'); e.hidden = !msg; e.textContent = msg || ''; }

function api(path, opts) {
  return fetch(path, opts).then(function (r) {
    return r.json().then(function (j) {
      if (!r.ok) throw new Error(j.error || ('HTTP ' + r.status));
      return j;
    });
  });
}

/* ------------------------------------------------------------------ tabs
 * The tab also lives in location.hash, so a screenshot run (and a reload mid-session) lands on the
 * panel it left rather than always on NOW. */
function showTab(name) {
  var found = false;
  Array.prototype.forEach.call(document.querySelectorAll('nav button'), function (x) {
    var on = x.dataset.tab === name;
    found = found || on;
    x.classList.toggle('on', on);
  });
  if (!found) return showTab('now');
  Array.prototype.forEach.call(document.querySelectorAll('main section'), function (s) {
    s.classList.toggle('on', s.id === 's-' + name);
  });
  if (location.hash !== '#' + name) history.replaceState(null, '', '#' + name);
}
Array.prototype.forEach.call(document.querySelectorAll('nav button'), function (b) {
  b.addEventListener('click', function () { showTab(b.dataset.tab); });
});
window.addEventListener('hashchange', function () {
  showTab((location.hash || '#now').slice(1));
});
showTab((location.hash || '#now').slice(1));

/* ------------------------------------------------------------------ map */
function drawMap(svg, side, target, coverage, interactive) {
  if (!MAP) return;
  svg.setAttribute('viewBox', MAP.viewbox || '0 0 400 800');
  var clipId = 'clip-' + side + '-' + (interactive ? 'big' : 'mini');
  var parts = ['<defs><clipPath id="' + clipId + '"><path d="' + esc(MAP.outlines[side] || '') +
               '"/></clipPath></defs>'];
  parts.push('<path class="outline" d="' + esc(MAP.outlines[side] || '') + '"/>');
  parts.push('<g clip-path="url(#' + clipId + ')">');
  MAP.regions.forEach(function (r) {
    if (r.side !== side || !r.d) return;
    var cls = 'region';
    var c = coverage && coverage[r.region_id];
    if (c && c.total) {
      if (c.done >= c.total) cls += ' done';
      else if (c.done > 0) cls += ' partial';
    }
    if (r.region_id === target) cls += ' target';
    if (r.region_id === SEL) cls += ' sel';
    parts.push('<path class="' + cls + '" d="' + esc(r.d) + '" data-rid="' + esc(r.region_id) +
               '"><title>' + esc(r.label) + '</title></path>');
  });
  parts.push('</g>');
  svg.innerHTML = parts.join('');
  if (interactive) {
    Array.prototype.forEach.call(svg.querySelectorAll('path[data-rid]'), function (p) {
      p.addEventListener('click', function () { SEL = p.dataset.rid; render(); });
    });
  }
}

function regionInfo() {
  var box = $('regioninfo');
  if (!SEL || !MAP) { box.innerHTML = '<div class="muted">Tap a region to see its shots.</div>'; return; }
  var r = null;
  MAP.regions.forEach(function (x) { if (x.region_id === SEL) r = x; });
  if (!r) { box.innerHTML = ''; return; }
  var shots = (S && S.upcoming || []).filter(function (u) { return u.region_id === SEL; });
  var rows = shots.map(function (u) {
    return '<div class="satrow">' + (u.done ? '<span style="color:var(--ok)">&#10003;</span> '
      : '<span style="color:var(--faint)">&#9675;</span> ') + '<b>' + esc(u.shot_id) + '</b> r' +
      u.rep + ' <span class="muted">' + esc(u.state) + ' / ' + esc(u.necessity) + '</span></div>';
  }).join('');
  box.innerHTML = '<h3>' + esc(r.label) + '</h3><div class="muted">' + esc(r.region_id) +
    ' &middot; ' + esc(r.group) + ' &middot; changes by cut: ' + (r.can_change_by_cut ? 'yes' : 'no') +
    ', by wash: ' + (r.can_change_by_wash ? 'yes' : 'no') + '</div>' +
    (rows || '<div class="muted">no shots planned for this region</div>');
}

/* ------------------------------------------------------------------ framing guide
 * A drawing of what the viewfinder should contain. The framing sentence is precise and still has to
 * be turned into a picture in the operator's head before every frame; this is that picture, with
 * the board and the rule where the shot says they go. */
var GUIDES = {
  full_garment: { subject: 'M 120 30 L 200 30 L 208 90 L 196 210 L 168 210 L 160 120 L 152 210 ' +
                           'L 124 210 L 112 90 Z', board: true, note: 'whole garment inside the frame with margin; board flat in its usual corner' },
  paired_hems: { subject: 'M 60 120 L 260 120 L 260 170 L 60 170 Z', board: true,
                 note: 'both hems side by side, edges parallel to the long side of the frame' },
  leg_section_quarter: { subject: 'M 108 20 L 212 20 L 206 220 L 114 220 Z', board: true,
                         note: 'one quarter of the leg fills the frame top to bottom' },
  seam_strip: { subject: 'M 140 16 L 180 16 L 180 224 L 140 224 Z', rule: 'v',
                note: 'the seam runs the long way through the middle; rule alongside it' },
  waistband_strip: { subject: 'M 20 88 L 300 88 L 300 152 L 20 152 Z', board: true,
                     note: 'the waistband spans the frame end to end' },
  hem_10cm_strip: { subject: 'M 16 96 L 304 96 L 304 150 L 16 150 Z', rule: 'h',
                    note: 'about 10 cm of edge fills the frame; rule flat in the cloth\u2019s plane' },
  fly_full_length: { subject: 'M 132 18 L 188 18 L 188 222 L 132 222 Z', board: true,
                     note: 'the fly runs the full height of the frame' },
  label_card: { subject: 'M 70 60 L 250 60 L 250 180 L 70 180 Z', rule: 'h',
                note: 'the label fills the middle; every printed line legible without zooming' },
  grazing_horizon_line: { subject: 'M 0 150 L 320 150 L 320 158 L 0 158 Z', rule: 'h',
                          note: 'camera at surface level; the edge seen along the surface, not from above' },
  phone_screen: { subject: 'M 110 24 L 210 24 L 210 216 L 110 216 Z',
                  note: 'the phone screen fills the frame, readable' },
  full_frame: { subject: 'M 8 8 L 312 8 L 312 232 L 8 232 Z',
                note: 'the subject fills the frame edge to edge' },
};

function drawGuide(shot) {
  var wrap = $('guidewrap'), svg = $('frameguide');
  var key = shot && shot.frame_guide;
  var g = key && (GUIDES[key] || (/margin/.test(key) ? {
    subject: 'M 96 62 L 224 62 L 224 178 L 96 178 Z', margin: true, rule: 'h',
    note: 'the feature centred, with the stated margin of surrounding cloth all round',
  } : null));
  if (!g) { wrap.hidden = true; return; }
  wrap.hidden = false;
  var parts = ['<rect class="frame" x="4" y="4" width="312" height="232" rx="6"/>'];
  parts.push('<path class="subject" d="' + esc(g.subject) + '"/>');
  if (g.margin) parts.push('<rect class="margin" x="76" y="44" width="168" height="152" rx="4"/>');
  if (g.board) parts.push('<rect class="board" x="248" y="16" width="56" height="72"/>' +
                          '<text x="252" y="98">board</text>');
  if (g.rule === 'h') parts.push('<rect class="rule" x="30" y="206" width="260" height="12"/>' +
                                 '<text x="30" y="202">rule, in the same plane</text>');
  if (g.rule === 'v') parts.push('<rect class="rule" x="238" y="24" width="12" height="192"/>' +
                                 '<text x="196" y="20">rule</text>');
  svg.innerHTML = parts.join('');
  $('guidenote').textContent = g.note;
}

/* ------------------------------------------------------------------ NOW */
function renderNow() {
  var n = S.next;
  var b = $('banner');
  if (!n) {
    b.className = 'banner b-PASS';
    b.innerHTML = 'ALL FRAMES CAPTURED<small>check the GATE tab</small>';
    $('shotid').textContent = '-';
    return;
  }
  var res = n.last_result;
  if (res) {
    b.className = 'banner b-' + res;
    var word = { PASS: 'PASS', RETAKE_REQUIRED: 'RETAKE', UNAVAILABLE_CHECK: 'UNAVAILABLE',
                 HUMAN_VERIFICATION_REQUIRED: 'HUMAN CHECK' }[res] || res;
    b.innerHTML = word + '<small>' + esc(n.shot_id) + ' repeat ' + n.rep + '</small>';
  } else {
    b.className = 'banner b-UNAVAILABLE_CHECK';
    b.innerHTML = 'NOT YET CAPTURED<small>' + esc(n.shot_id) + ' repeat ' + n.rep + ' of ' + n.rep_of + '</small>';
  }

  $('shotid').textContent = n.shot_id;
  var nec = $('necessity');
  nec.textContent = n.necessity; nec.className = 'pill p-' + n.necessity;
  $('repbadge').textContent = 'repeat ' + n.rep + ' / ' + n.rep_of;
  $('statebadge').textContent = n.state;

  $('f-side').textContent = { front: 'FRONT up', back: 'BACK up', left_profile: 'left side profile',
    right_profile: 'right side profile', edge: 'edge on', 'n/a': 'any' }[n.garment_side] || n.garment_side;
  $('f-region').textContent = (n.region ? n.region.label + ' (' + n.region_id + ')' : n.region_id);
  $('f-camera').textContent = n.camera_angle.replace(/_/g, ' ') + ' · ' + n.lens +
    ' lens · height group ' + (n.camera_height_group || '-');
  $('f-position').textContent = n.camera_position || '—';
  $('f-framing').textContent = n.framing;
  $('f-guide').textContent = n.frame_guide ? n.frame_guide.replace(/_/g, ' ') : '—';
  drawGuide(n);
  $('f-scale').textContent = n.scale_reference.replace(/_/g, ' ') +
    (n.scale_placement ? ' — ' + n.scale_placement : '');
  var q = n.quality || {};
  var qbits = [];
  if (q.max_mm_per_px) qbits.push('≤ ' + q.max_mm_per_px + ' mm/px');
  if (q.min_subject_px) qbits.push((q.subject_px_meaning || 'subject') + ' ≥ ' + q.min_subject_px + ' px');
  if (q.min_board_corners) qbits.push('≥ ' + q.min_board_corners + ' board corners');
  if (q.max_scale_range_ratio) qbits.push('tilt ≤ ' + Math.round((q.max_scale_range_ratio - 1) * 100) + '%');
  if (q.min_long_edge_px) qbits.push('≥ ' + q.min_long_edge_px + ' px long edge');
  $('f-quality').textContent = qbits.join(' · ') || 'defaults';
  var mc = n.matched_captured || [];
  $('f-matched').innerHTML = mc.length ? mc.map(function (m) {
    return '<span class="pill ' + (m.captured ? 'p-ok' : 'p-required') + '">' +
      (m.captured ? '✓ ' : '○ ') + esc(m.shot_id) + '</span>';
  }).join(' ') : '—';
  $('f-time').textContent = (n.est_seconds || 0) + ' s for this frame';
  $('f-why').textContent = n.purpose;

  var h = [];
  if (n.needs_relay_before) h.push('LIFT the garment clear of the surface, shake it out, and lay it out again before this frame. This repeat measures what changes when it is re-laid, so re-shooting the same lay records nothing.');
  if (n.needs_camera_reposition_before) h.push('Take the phone OFF the mount and remount it before this frame.');
  if (n.needs_second_person) h.push('This frame needs a second person.');
  $('handling').hidden = !h.length;
  $('handling').innerHTML = h.map(function (x) { return esc(x); }).join('<br><br>');

  // A rig or label frame has no place on a drawing of a pair of jeans. Highlighting nothing while
  // showing the whole map lights up every region as "not started", which reads as an instruction to
  // photograph the entire garment. Say what the frame is of instead.
  var target = MAP && MAP.regions.filter(function (r) { return r.region_id === n.region_id; })[0];
  var onGarment = !!(target && target.d);
  var maps = document.querySelector('#nextcard .maps');
  var norig = document.getElementById('norigmap');
  if (!onGarment) {
    if (maps) maps.style.display = 'none';
    if (!norig) {
      norig = document.createElement('div');
      norig.id = 'norigmap'; norig.className = 'norigmap';
      if (maps && maps.parentNode) maps.parentNode.insertBefore(norig, maps);
    }
    norig.style.display = '';
    norig.textContent = 'This frame is of ' + ((target && target.label) || n.region_id) +
      ' — it is not a view of the garment, so there is nothing to highlight on the map.';
  } else {
    if (maps) maps.style.display = '';
    if (norig) norig.style.display = 'none';
    drawMap($('mini-front'), 'front', n.region_id, S.by_region, false);
    drawMap($('mini-back'), 'back', n.region_id, S.by_region, false);
  }

  // ghost overlay availability
  var gb = $('b-ghost');
  gb.disabled = !S.ghost;
  gb.textContent = S.ghost ? ('ghost overlay: ' + (GHOST ? 'ON' : 'off')) : 'no earlier frame';
  gb.classList.toggle('on', GHOST && !!S.ghost);
  $('ghostnote').hidden = !(GHOST && S.ghost);
  var pg = $('pv-ghost');
  if (GHOST && S.ghost) { pg.src = S.ghost.url; pg.hidden = false; } else { pg.hidden = true; }

  ['ruler', 'side', 'region', 'relay'].forEach(function (k) {
    var key = { ruler: 'ruler_visible', side: 'side_confirmed', region: 'region_confirmed',
                relay: 'relay_confirmed' }[k];
    $('b-' + k).classList.toggle('on', !!CONFIRM[key]);
  });

  var t = $('checks');
  t.innerHTML = (n.last_checks || []).map(function (c) {
    return '<tr><td class="k">' + esc(c.check_id) + '</td><td class="o o-' + c.outcome + '">' +
      esc(c.outcome.replace('_REQUIRED', '').replace('_CHECK', '')) + '</td><td>' + esc(c.detail) +
      (c.outcome !== 'PASS' && c.fix ? '<div class="fix">' + esc(c.fix) + '</div>' : '') +
      '</td></tr>';
  }).join('');

  $('p-done').textContent = S.n_done;
  $('p-total').textContent = S.n_total;
  $('p-eta').textContent = mins(S.seconds_remaining) + ' left';
  $('p-bar').style.width = (S.n_total ? (100 * S.n_done / S.n_total) : 0) + '%';
  var notes = [];
  if (S.assumed_present && S.assumed_present.length) {
    notes.push(S.assumed_present.length + ' feature question(s) unanswered and assumed PRESENT, so their shots are planned.');
  }
  if (S.log_problems && S.log_problems.length) {
    notes.push('The capture log reports ' + S.log_problems.length + ' integrity problem(s).');
  }
  $('p-note').textContent = notes.join(' ');
}

/* ------------------------------------------------------------------ DASH */
function renderDash() {
  var order = (MAP && MAP.states || []).slice().sort(function (a, c) { return a.order - c.order; });
  $('d-states').innerHTML = order.map(function (st) {
    var s = S.by_state[st.state];
    if (!s) return '';
    var reqPct = s.required ? Math.round(100 * s.required_done / s.required) : 100;
    var allPct = s.total ? Math.round(100 * s.done / s.total) : 0;
    return '<div class="srow"><div><b>' + esc(st.label || st.state) + '</b> ' +
      '<span>' + s.required_done + '/' + s.required + ' required, ' + s.done + '/' + s.total +
      ' incl. optional</span></div><div class="muted">' + reqPct + '%</div></div>' +
      '<div class="bar req"><i style="width:' + reqPct + '%"></i></div>' +
      '<div class="bar"><i style="width:' + allPct + '%"></i></div>';
  }).join('');

  var qc = S.qa_counts || {};
  $('d-qa').innerHTML = ['PASS', 'RETAKE_REQUIRED', 'UNAVAILABLE_CHECK', 'HUMAN_VERIFICATION_REQUIRED']
    .map(function (k) {
      return '<div><div class="big o-' + k + '">' + (qc[k] || 0) + '</div><div class="muted">' +
        esc(k.replace(/_/g, ' ').toLowerCase()) + '</div></div>';
    }).join('');

  var m = S.matched || [];
  var done = m.filter(function (x) { return x.status === 'complete'; }).length;
  $('d-matched').innerHTML = '<div class="srow"><div><b>' + done + '</b> <span>of ' + m.length +
    ' before/after pairs complete</span></div></div><div class="bar"><i style="width:' +
    (m.length ? Math.round(100 * done / m.length) : 0) + '%"></i></div>' +
    '<div class="muted" style="margin:6px 0">' + (S.companion_pairs || 0) +
    ' same-state companion links (framed alike, not a before/after pair)' +
    ((S.unmatched_changing_regions || []).length
      ? ' &middot; <span style="color:var(--warn)">' + S.unmatched_changing_regions.length +
        ' region(s) change with washing and have no later-state frame: ' +
        esc(S.unmatched_changing_regions.slice(0, 6).join(', ')) + '</span>'
      : ' &middot; every region that survives the cut and changes with washing has a later frame') +
    '</div>' +
    m.filter(function (x) { return x.status !== 'complete'; }).slice(0, 25).map(function (x) {
      return '<div class="satrow"><b>' + esc(x.earlier) + '</b> → ' + esc(x.later) +
        ' <span class="muted">' + esc(x.status.replace(/_/g, ' ')) + '</span></div>';
    }).join('');

  var req = S.measurements_required || {};
  $('d-meas').innerHTML = Object.keys(req).sort().map(function (k) {
    var v = S.measurements[k];
    var ok = v && v.in_tolerance;
    return '<div class="satrow">' + (v ? (ok ? '<span style="color:var(--ok)">✓</span> '
      : '<span style="color:var(--bad)">✗</span> ') : '<span style="color:var(--faint)">○</span> ') +
      '<b>' + esc(k) + '</b> ' + (v ? ('<span class="muted">' + v.readings.join(' / ') + ' → ' +
      (Math.round(v.mean * 100) / 100) + '</span>') : '<span class="muted">needs ' + req[k] +
      ' independent reading(s)</span>') + '</div>';
  }).join('');

  var wp = S.wash_planned, wa = S.wash_actual, wd = S.wash_deviations || [];
  $('d-wash').innerHTML = !wp ? '<div class="muted">no wash planned yet</div>'
    : ('<div class="satrow"><b>planned</b> <span class="muted">' + esc(JSON.stringify(wp).slice(0, 200)) + '</span></div>' +
       (wa ? '<div class="satrow"><b>actual</b> <span class="muted">' + esc(JSON.stringify(wa).slice(0, 200)) + '</span></div>' : '<div class="muted">not run yet</div>') +
       (wd.length ? '<div class="warnbox" style="margin-top:8px">' + wd.length + ' deviation(s): ' +
        wd.map(function (d) { return esc(d.field) + ' ' + esc(d.planned) + '→' + esc(d.actual); }).join(', ') +
        '<br>Planned settings are kept; actual never replaces them.</div>' : ''));

  var dv = S.deviations || [];
  $('d-dev').innerHTML = dv.length ? dv.map(function (d) {
    return '<div class="satrow"><b>' + esc(d.kind || 'deviation') + '</b> ' + esc(JSON.stringify(d).slice(0, 180)) + '</div>';
  }).join('') : '<div class="muted">none recorded</div>';

  var br = S.by_region || {};
  var keys = Object.keys(br).sort();
  var full = keys.filter(function (k) { return br[k].done >= br[k].total; }).length;
  $('d-regions').innerHTML = '<div class="srow"><div><b>' + full + '</b> <span>of ' + keys.length +
    ' regions fully covered</span></div></div><div class="bar"><i style="width:' +
    (keys.length ? Math.round(100 * full / keys.length) : 0) + '%"></i></div>' +
    keys.filter(function (k) { return br[k].done < br[k].total; }).slice(0, 40).map(function (k) {
      return '<div class="satrow"><b>' + esc(k) + '</b> <span class="muted">' + br[k].done + '/' +
        br[k].total + '</span></div>';
    }).join('');
}

/* ------------------------------------------------------------------ HEM */
function hemRing(h) {
  if (!h.available) {
    return '<div class="card"><h3>' + esc(h.leg) + ' leg</h3><div class="warnbox">' + esc(h.why) + '</div></div>';
  }
  var R = 96, cx = 130, cy = 130, n = h.n_positions;
  var covered = {};
  Object.keys(h.support || {}).forEach(function (k) { covered[k] = true; });
  var dots = [];
  for (var i = 1; i <= n; i++) {
    var a = (i - 1) / n * Math.PI * 2 - Math.PI / 2;
    var x = cx + R * Math.cos(a), y = cy + R * Math.sin(a);
    dots.push('<circle class="' + (covered[i] ? 'pos-covered' : 'pos-gap') + '" cx="' +
      x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="5"><title>position ' + i + '</title></circle>');
  }
  return '<div class="card"><h3>' + esc(h.leg) + ' leg &mdash; ' + h.n_covered + '/' + h.n_positions +
    ' positions covered</h3>' +
    '<svg class="hemring" viewBox="0 0 260 260" width="230"><circle cx="' + cx + '" cy="' + cy +
    '" r="' + R + '" fill="none" stroke="#2a3441" stroke-width="10"/>' + dots.join('') +
    '<text x="' + cx + '" y="' + (cy - 4) + '" text-anchor="middle" fill="#8b98a5" font-size="13">' +
    Math.round(h.fraction * 100) + '%</text>' +
    '<text x="' + cx + '" y="' + (cy + 14) + '" text-anchor="middle" fill="#5a6673" font-size="10">inseam seam at top</text>' +
    '</svg>' +
    (h.complete ? '<div class="satrow" style="color:var(--ok)">complete &mdash; no gaps</div>'
      : '<div class="warnbox">gap at position(s) ' + (h.gap_positions || []).slice(0, 20).join(', ') +
        (h.next_macro ? '<br>next macro <b>' + esc(h.next_macro.shot_suffix) + '</b> covers arc ' +
          Math.round(h.next_macro.usable_start_mm) + '–' + Math.round(h.next_macro.usable_end_mm) + ' mm' : '') +
        '</div>') +
    '<div class="muted">circumference ' + Math.round(h.circumference_mm) + ' mm, ' +
    (h.macros || []).length + ' macros, ' +
    Object.keys(h.multiply_supported || {}).length + ' positions covered by more than one macro</div></div>';
}
function renderHem() { $('hemwrap').innerHTML = (S.hems || []).map(hemRing).join(''); }

/* ------------------------------------------------------------------ GATE */
function renderGate() {
  var g = S.gate || { ready: false, blocks: [], satisfied: [] };
  var b = $('gatebanner');
  b.className = 'banner ' + (g.ready ? 'b-PASS' : 'b-RETAKE_REQUIRED');
  b.innerHTML = g.ready ? 'READY TO CUT<small>every required photograph, measurement, calibration reading, hash and human verification is present and valid</small>'
    : 'NOT READY TO CUT<small>' + g.blocks.length + ' condition(s) blocking</small>';
  $('g-blocks').innerHTML = g.blocks.length ? g.blocks.map(function (x) {
    return '<div class="block"><div class="c">' + esc(x.condition) + '</div><div class="w">' +
      esc(x.what) + '</div>' + (x.fix ? '<div class="f">→ ' + esc(x.fix) + '</div>' : '') + '</div>';
  }).join('') : '<div class="muted">nothing blocking</div>';
  $('g-sat').innerHTML = (g.satisfied || []).map(function (x) {
    return '<div class="satrow"><b>' + esc(x.condition) + '</b> ' + esc(x.what) + '</div>';
  }).join('') || '<div class="muted">none yet</div>';
}

/* ------------------------------------------------------------------ render */
function render() {
  if (!S) return;
  $('specv').textContent = S.spec_version + ' · ' + S.spec_hash;
  $('setuph').textContent = S.setup_frozen ? S.setup_hash : 'NOT FROZEN';
  $('storage').textContent = S.storage;
  renderNow();
  if (MAP) {
    drawMap($('big-front'), 'front', S.next && S.next.region_id, S.by_region, true);
    drawMap($('big-back'), 'back', S.next && S.next.region_id, S.by_region, true);
    $('lrnote').textContent = MAP.left_right_convention || '';
    regionInfo();
  }
  renderDash(); renderHem(); renderGate();
}

function refresh() {
  if (!GARMENT) return Promise.resolve();
  return api('/api/state/' + GARMENT).then(function (j) {
    S = j; showErr(''); render();
  }).catch(function (e) { showErr(e.message); });
}

/* ------------------------------------------------------------------ actions */
$('file').addEventListener('change', function (ev) {
  var f = ev.target.files && ev.target.files[0];
  if (!f || !S || !S.next || BUSY) return;
  BUSY = true;
  var lbl = $('camlabel');
  lbl.textContent = 'CHECKING…'; lbl.classList.add('busy');
  var fd = new FormData();
  fd.append('file', f, f.name || 'capture.jpg');
  fd.append('garment', GARMENT);
  fd.append('shot_id', S.next.shot_id);
  fd.append('rep', String(S.next.rep));
  fd.append('confirm', Object.keys(CONFIRM).filter(function (k) { return CONFIRM[k]; }).join(','));
  fd.append('operator', localStorage.getItem('pilot_operator') || '');
  fetch('/api/upload', { method: 'POST', body: fd })
    .then(function (r) { return r.json(); })
    .then(function (j) {
      if (j.error) throw new Error(j.error);
      $('preview').hidden = false;
      $('pv-main').src = j.url + '&_=' + Date.now();
      CONFIRM = {};
      return refresh();
    })
    .catch(function (e) { showErr(e.message); })
    .then(function () {
      BUSY = false;
      lbl.textContent = 'TAKE THIS PHOTOGRAPH'; lbl.classList.remove('busy');
      ev.target.value = '';
    });
});

[['b-ruler', 'ruler_visible'], ['b-side', 'side_confirmed'], ['b-region', 'region_confirmed'],
 ['b-relay', 'relay_confirmed']].forEach(function (p) {
  $(p[0]).addEventListener('click', function () {
    CONFIRM[p[1]] = !CONFIRM[p[1]];
    $(p[0]).classList.toggle('on', !!CONFIRM[p[1]]);
  });
});
$('b-ghost').addEventListener('click', function () { GHOST = !GHOST; render(); });
$('b-skip').addEventListener('click', function () {
  if (!S || !S.next) return;
  var i = (S.upcoming || []).findIndex(function (u) {
    return u.shot_id === S.next.shot_id && u.rep === S.next.rep;
  });
  var nxt = (S.upcoming || []).slice(i + 1).find(function (u) { return !u.done; });
  if (nxt) { alert('Next un-captured frame is ' + nxt.shot_id + ' r' + nxt.rep +
                   '. The order is chosen to minimise handling; skipping costs time later.'); }
});

$('garment').addEventListener('change', function (e) {
  GARMENT = e.target.value;
  localStorage.setItem('pilot_garment', GARMENT);
  refresh();
});

/* ------------------------------------------------------------------ boot */
api('/api/map').then(function (j) { MAP = j; render(); }).catch(function (e) { showErr(e.message); });
api('/api/garments').then(function (j) {
  var sel = $('garment');
  sel.innerHTML = j.garments.map(function (g) { return '<option>' + esc(g) + '</option>'; }).join('');
  // The server was started for a particular garment when `serve GARMENT` named one; that beats
  // whatever this browser looked at last, because the operator just typed it.
  var want = j.default_garment || localStorage.getItem('pilot_garment');
  GARMENT = (want && j.garments.indexOf(want) >= 0) ? want : j.garments[0];
  if (GARMENT) { sel.value = GARMENT; refresh(); }
  else showErr('No garments yet. Run `tools/pilot.py new` first.');
}).catch(function (e) { showErr(e.message); });

setInterval(function () {
  var d = new Date();
  $('clock').textContent = String(d.getHours()).padStart(2, '0') + ':' +
    String(d.getMinutes()).padStart(2, '0');
}, 1000);
