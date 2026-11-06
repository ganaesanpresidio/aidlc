"""Run the units on your machine with the mock backend (no AWS).

  uv run aidlc-e2e serve policy [port]     policy unit on http://127.0.0.1:8101
  uv run aidlc-e2e serve submit [port]     submit unit on http://127.0.0.1:8102 (policy runs inside it)
  uv run aidlc-e2e demo                    one full journey, printed step by step
"""

from __future__ import annotations

import hashlib
import sys

from aidlc_e2e.config import PROJECT_ROOT


def _paths() -> None:
    for sub in ("src", "libs"):
        p = str(PROJECT_ROOT / sub)
        if p not in sys.path:
            sys.path.insert(0, p)


def serve(unit: str, port: int | None = None) -> None:
    _paths()
    from aidlc_common.backend import Backend, current_backend

    if current_backend() is not Backend.MOCK:
        sys.exit("The local server runs only with AIDLC_BACKEND=mock (it trusts dev headers instead of a JWT).")
    if unit == "policy":
        from policy.factory import build_service, seed_example_rules
        from policy.server import serve as make

        service = build_service(Backend.MOCK)
        seed_example_rules(service)
        server = make(service, port=port or 8101)
        hint = ("Headers: X-Dev-User: me  (add X-Dev-Groups: finance-admin to publish)  "
                "or X-Dev-Internal: submit  for evaluate and route")
    elif unit == "submit":
        from submit.factory import build_mock_stack
        from submit.server import serve as make

        server = make(build_mock_stack(), port=port or 8102)
        hint = ("Headers: X-Dev-User: me, X-Dev-Grade: G1.  Dev routes: POST /dev/uploads/{claimId}/{receiptId}, "
                "POST /dev/jobs/sweep, POST /dev/jobs/expire")
    else:
        sys.exit("usage: aidlc-e2e serve policy|submit [port]")
    print(f"{unit} unit (MOCK backend) on http://127.0.0.1:{server.server_address[1]}\n{hint}\nCtrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


def demo() -> None:
    _paths()
    from submit.factory import build_mock_stack
    from submit.service import Caller

    st = build_mock_stack()
    me = Caller("emp-asha", "G1")
    svc = st.service
    step = lambda msg: print(f"\n== {msg}")
    show = lambda **kw: print("   ", ", ".join(f"{k}={v}" for k, v in kw.items()))

    step("Employee starts a claim and adds two lines")
    cid = svc.create_claim(me)["claimId"]
    today = st.clock.today().isoformat()
    lunch = svc.add_line(me, cid, {"expenseDate": today, "category": "Meals", "amount": 1200, "description": "team lunch"})
    cab = svc.add_line(me, cid, {"expenseDate": today, "category": "Travel", "amount": 800, "description": "cab"})
    show(claim=cid, lines=2, total_inr=2000)

    step("Submit without a receipt: blocked (the 1,000 rupee rule)")
    try:
        svc.submit(me, cid, "demo-key-0001")
    except Exception as exc:
        show(status=exc.status, code=exc.code, line=exc.details[0]["lineId"][-6:], message=exc.details[0]["message"])

    step("Attach a PNG receipt (upload, malware scan, store)")
    png = b"\x89PNG\r\n\x1a\n" + b"demo-receipt" * 10
    slot = svc.request_receipt_upload(me, cid, lunch["lineId"], {"mimeType": "image/png", "sizeBytes": len(png),
                                                                  "sha256": hashlib.sha256(png).hexdigest()})
    st.objects.post(slot["fields"], png, "image/png")
    svc.handle_upload_event(cid, slot["receiptId"])
    show(scan=svc.handle_scan_result(cid, slot["receiptId"]))

    step("Try an infected file (the EICAR test string)")
    bad = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
    slot2 = svc.request_receipt_upload(me, cid, cab["lineId"], {"mimeType": "image/png", "sizeBytes": len(bad),
                                                                 "sha256": hashlib.sha256(bad).hexdigest()})
    st.objects.post(slot2["fields"], bad, "image/png")
    svc.handle_upload_event(cid, slot2["receiptId"])
    show(scan=svc.handle_scan_result(cid, slot2["receiptId"]),
         stored_anywhere=bool(st.objects.buckets["quarantine"] or len(st.objects.buckets["receipts"]) > 1))

    step("Submit now (the cab line is under 1,000, so it needs no receipt)")
    out = svc.submit(me, cid, "demo-key-0001")
    show(status=out["status"], reference=out["claimRef"], total_inr=out["totalInr"])
    again = svc.submit(me, cid, "demo-key-0001")
    show(same_key_again=again["claimRef"], events=len(st.bus.of("ClaimSubmitted")))

    step("Policy routes it for approval (what the approve unit will ask)")
    ev = st.bus.of("ClaimSubmitted")[0]["payload"]
    routed = st.policy_service.route({
        "claimRef": out["claimRef"], "submitter": ev["submitterId"], "grade": ev["gradeOfSubmitter"],
        "totalInr": ev["totalInr"], "requiresException": ev["requiresException"],
        "roleHolders": {"LINE_MANAGER": {"id": "mgr-ravi", "grade": "G2"}}})
    show(tier=routed["tier"], chain=[c["approver"] for c in routed["chain"]])

    step("Audit trail")
    for a in st.bus.of("Audit"):
        p = a["payload"]
        show(action=p["action"], actor=p["actor"], outcome=p["outcome"])
    print("\nDone. Nothing touched AWS.")
