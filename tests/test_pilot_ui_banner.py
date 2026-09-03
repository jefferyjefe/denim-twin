"""The readiness banner must never be green for a verdict that was not just read back.

The GATE banner is the last thing an operator looks at before an irreversible cut, and it is drawn
from a snapshot the app holds in a variable. Three ways that variable stopped matching the log, all
of which left READY TO CUT on screen:

  * two /api/state responses in flight at once are applied in ARRIVAL order, and the endpoint
    re-hashes every photograph the gate reads -- so a finished garment answers a second later than
    a fresh one asked for afterwards, and repaints the screen for a garment the operator left;
  * a failed read kept the last good snapshot, so a phone off the network showed the last green;
  * nothing re-reads the log, so opening the GATE tab showed whatever was true when the app last
    happened to fetch.

This drives the real ui/app.js in node against a stub of the API. `node` is required; without it the
front door that is actually used on cut day has no test at all, which is how this got in.
"""
import json
import os
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src" / "denimtwin" / "pilot" / "ui" / "app.js"

# `next: None` is the cut-day shape: every frame captured, and what is left is the confirmations.
READY = {"garment_id": "DENIM_9001", "spec_version": "t", "spec_hash": "h", "storage": "/tmp",
         "setup_frozen": True, "setup_hash": "s", "next": None, "by_state": {}, "by_region": {},
         "pending_claims": [{"shot_id": "BEFORE.WHOLE.FRONT.FLAT", "rep": 1,
                             "code": "H0123456789",
                             "claim": "confirmed_the backdrop is empty",
                             "detail": "the backdrop is empty"}],
         "n_pending_claims": 1,
         "session_claims": [{"claim": "legs_cut_separately", "code": "H9876543210",
                             "detail": "the legs were cut one at a time", "recorded": False,
                             "value": None, "needs_measurements": False}],
         "gate": {"ready": True, "blocks": [], "satisfied": [{"condition": "c", "what": "w"}]}}
NOT_READY = {"garment_id": "DENIM_9002", "spec_version": "t", "spec_hash": "h", "storage": "/tmp",
             "setup_frozen": True, "setup_hash": "s", "next": None, "by_state": {}, "by_region": {},
             "gate": {"ready": False, "blocks": [{"condition": "captures.required_complete",
                                                  "what": "nothing photographed", "fix": "shoot"}],
                      "satisfied": []}}
MAP = {"viewbox": "0 0 400 800", "outlines": {"front": "", "back": ""}, "regions": [],
       "states": [], "left_right_convention": ""}

HARNESS = r"""
import fs from 'node:fs'; import vm from 'node:vm'; import net from 'node:net';
const APP = process.env.APP, LIVE = 'http://127.0.0.1:' + process.env.PORT;
let DEAD = null, NET = 'up';
const realFetch = globalThis.fetch;
class El {
  constructor(id, tag){ this.id=id||''; this.tagName=tag||'div'; this.dataset={}; this.style={};
    this._cls=new Set(); this._text=''; this._html=''; this.hidden=false; this.disabled=false;
    this.value=''; this._ev={}; this.attrs={}; this.parentNode={insertBefore(){}}; }
  get className(){ return Array.from(this._cls).join(' '); }
  set className(v){ this._cls=new Set(String(v).split(/\s+/).filter(Boolean)); }
  get classList(){ const s=this._cls; return {add:(c)=>s.add(c), remove:(c)=>s.delete(c),
    contains:(c)=>s.has(c), toggle:(c,f)=>{const on=f===undefined?!s.has(c):!!f;
      if(on)s.add(c); else s.delete(c); return on;}}; }
  get textContent(){ return this._text; }
  set textContent(v){ this._text=String(v); this._html=''; }
  get innerHTML(){ return this._html; }
  set innerHTML(v){ this._html=String(v); this._text=String(v).replace(/<[^>]*>/g,' ')
    .replace(/\s+/g,' ').trim(); }
  setAttribute(k,v){ this.attrs[k]=v; } getAttribute(k){ return this.attrs[k]; }
  addEventListener(t,f){ (this._ev[t]=this._ev[t]||[]).push(f); }
  dispatch(t,ev){ (this._ev[t]||[]).forEach((f)=>f.call(this, ev||{target:this})); }
  querySelectorAll(){ return []; } querySelector(){ return null; } appendChild(c){ return c; }
}
const els=new Map(); const el=(id,tag)=>{ if(!els.has(id)) els.set(id,new El(id,tag)); return els.get(id); };
const NAV=['now','map','dash','hem','gate'].map((t)=>{const b=new El('nav-'+t,'button'); b.dataset.tab=t; return b;});
const SECTIONS=['s-now','s-map','s-dash','s-hem','s-gate'].map((i)=>el(i,'section'));
globalThis.document={ getElementById:(id)=>el(id),
  querySelectorAll:(s)=> s==='nav button'?NAV : s==='main section'?SECTIONS : [],
  querySelector:(s)=> s==='#nextcard .maps'?el('__maps'):null,
  createElement:(t)=>new El('',t), addEventListener(){} };
const store=new Map([['pilot_operator','harness']]);
globalThis.localStorage={ getItem:(k)=>store.has(k)?store.get(k):null, setItem:(k,v)=>store.set(k,String(v)) };
globalThis.location={hash:''};
globalThis.history={ replaceState:(_a,_b,h)=>{ globalThis.location.hash=h; } };
globalThis.window={ prompt:()=>'harness', alert(){}, addEventListener(){} };
globalThis.alert=()=>{}; globalThis.FormData=class{ append(){} };
globalThis.fetch=(path,opts)=>realFetch((NET==='up'?LIVE:DEAD)+path, opts);
const sleep=(n)=>new Promise((r)=>setTimeout(r,n));
async function waitFor(fn,limit=10000){ const end=Date.now()+limit;
  while(Date.now()<end){ if(fn()) return true; await sleep(5);} return false; }
const bannerText=()=>el('gatebanner').textContent;
const bannerClass=()=>el('gatebanner').className;
async function main(){
  const s=net.createServer(); await new Promise((r)=>s.listen(0,'127.0.0.1',r));
  DEAD='http://127.0.0.1:'+s.address().port; await new Promise((r)=>s.close(r));
  const out={};
  vm.runInThisContext(fs.readFileSync(APP,'utf8'),{filename:APP});

  // 1. the stalled READY garment is still in flight when the operator picks the other one
  await waitFor(()=>globalThis.GARMENT);
  const sel=el('garment'); sel.value='DENIM_9002'; sel.dispatch('change',{target:sel});
  await waitFor(()=>globalThis.S && globalThis.S.garment_id==='DENIM_9002');
  await realFetch(LIVE+'/control/release');          // the slow garment answers now
  await sleep(1200);
  out.race_applied_garment = globalThis.S && globalThis.S.garment_id;
  out.race_text = bannerText(); out.race_class = bannerClass();

  // 2. positive control: the app must be able to show green at all
  sel.value='DENIM_9001'; sel.dispatch('change',{target:sel});
  await waitFor(()=>globalThis.S && globalThis.S.garment_id==='DENIM_9001');
  await sleep(50);
  out.ready_text = bannerText(); out.ready_class = bannerClass();
  // Cut day: every frame captured, and the confirmations are the only thing left to do. renderNow()
  // returns early in exactly that state, and the claim cards were rendered after that return.
  out.claims_hidden = !!el('claimscard').hidden;
  out.claims_html = String(el('claimlist')._html || '');
  out.session_hidden = !!el('sessionclaimscard').hidden;

  // 3. the phone is off the network and the read fails, with green on screen
  NET='down'; await globalThis.refresh();
  out.after_failed_read_text = bannerText(); out.after_failed_read_class = bannerClass();

  // back on the network, green again, so step 4 starts from green too
  NET='up'; await globalThis.refresh();
  out.recovered_text = bannerText(); out.recovered_class = bannerClass();

  // 4. the log changes underneath it, and the operator opens the GATE tab to check
  await realFetch(LIVE+'/control/flip');
  NAV.filter((b)=>b.dataset.tab==='gate')[0].dispatch('click');
  await sleep(600);
  out.after_gate_tab_text = bannerText(); out.after_gate_tab_class = bannerClass();
  console.log('__RESULT__' + JSON.stringify(out));
  process.exit(0);            // app.js starts a wall-clock interval that would hold the loop
}
main().catch((e)=>{ console.error(e); process.exit(1); });
"""


class _Stub(BaseHTTPRequestHandler):
    release = threading.Event()
    flipped = False

    def log_message(self, *a):
        pass

    def _json(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/control/release":
            _Stub.release.set(); return self._json({"ok": True})
        if p == "/control/flip":
            _Stub.flipped = True; return self._json({"ok": True})
        if p == "/api/map":
            return self._json(MAP)
        if p == "/api/garments":
            return self._json({"garments": ["DENIM_9001", "DENIM_9002"],
                               "default_garment": "DENIM_9001"})
        if p == "/api/state/DENIM_9001":
            # the real endpoint re-hashes every photograph the gate reads, so the finished
            # garment is the slow one. That is the whole race.
            _Stub.release.wait(20)
            g = dict(READY)
            if _Stub.flipped:
                g = dict(READY, gate={"ready": False, "satisfied": [],
                                      "blocks": [{"condition": "cut.confirmations",
                                                  "what": "a confirmation was refused",
                                                  "fix": "resolve it"}]})
            return self._json(g)
        if p == "/api/state/DENIM_9002":
            return self._json(NOT_READY)
        return self._json({"error": "no route"})


@pytest.mark.needs("node")
def test_gate_banner_is_never_green_for_a_verdict_it_did_not_just_read(tmp_path):
    _Stub.release.clear(); _Stub.flipped = False
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Stub)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    harness = tmp_path / "harness.mjs"
    harness.write_text(HARNESS)
    try:
        r = subprocess.run(["node", str(harness)], text=True, capture_output=True, timeout=180,
                           env=dict(os.environ, APP=str(APP),
                                    PORT=str(httpd.server_address[1])))
    finally:
        httpd.shutdown(); httpd.server_close()
    assert "__RESULT__" in r.stdout, "the UI harness did not finish:\n%s\n%s" % (r.stdout, r.stderr)
    out = json.loads(r.stdout.split("__RESULT__", 1)[1].splitlines()[0])

    # The positive control: the banner CAN go green, so the assertions below are not vacuous.
    assert out["ready_text"].startswith("READY TO CUT")
    assert "b-PASS" in out["ready_class"]

    def green(k):
        return "b-PASS" in out[k + "_class"] or out[k + "_text"].startswith("READY TO CUT")

    # 1. the late answer for the garment the operator LEFT must not repaint the screen
    assert out["race_applied_garment"] == "DENIM_9002", (
        "a stale /api/state response overwrote the snapshot: the screen is showing %s while the "
        "picker is on DENIM_9002" % out["race_applied_garment"])
    assert not green("race"), (
        "READY TO CUT is on screen for a garment that is not selected: %r" % out["race_text"])

    # 2. a read that failed is not a pass
    assert not green("after_failed_read"), (
        "the banner kept its last green after the read failed: %r" % out["after_failed_read_text"])

    # the network came back, so the banner is green again and the next assertion is not vacuous
    assert green("recovered")

    # 3. opening the gate tab must re-read the log rather than show the last thing fetched
    assert not green("after_gate_tab"), (
        "the gate says READY after the log said otherwise; opening the tab read nothing: %r"
        % out["after_gate_tab_text"])


    # -- the claim cards on cut day ---------------------------------------------------------
    assert out["claims_hidden"] is False, (
        "every frame is captured and one confirmation is outstanding, and the claims card is "
        "hidden. renderNow() returns early in exactly that state -- 'ALL FRAMES CAPTURED' -- and "
        "the claim cards were rendered after that return, so the phone dropped them at the moment "
        "they are the only thing left to do. It is the only door that shows the photograph a "
        "claim is about.")
    assert "BEFORE.WHOLE.FRONT.FLAT" in out["claims_html"], out["claims_html"][:300]
    assert "the backdrop is empty" in out["claims_html"], out["claims_html"][:300]
    assert out["session_hidden"] is False, (
        "the cut-day session claims card is hidden too, for the same reason")
