"""Model projection of Cua's canonical MCP result, shared by both providers."""
from __future__ import annotations

import json


def result_dict(raw):
    return dict(raw) if isinstance(raw, dict) else raw.model_dump(exclude_none=True)


def structured_result(raw):
    value = result_dict(raw).get("structuredContent")
    return value if isinstance(value, dict) else {}


def project_result(raw, tool, arguments):
    result = result_dict(raw)
    data = structured_result(result)
    # Put routing/status before a potentially enormous tree, so offloading does
    # not hide the snapshot id or turn a delivery receipt into apparent success.
    summary = {key: value for key, value in data.items() if key not in {"elements", "tree_markdown"}}
    hints = []
    postcondition_satisfied = (data.get("host_verification") or {}).get("status") == "satisfied"
    if (data.get("verified") is False or data.get("effect") == "unverifiable") and not postcondition_satisfied:
        hints.append("DELIVERY ONLY: the driver has not verified the intended UI change. Do not report task success from this receipt. Use _verify on window actions or verify_state; do not replay input automatically.")
    if data.get("elements_complete") is False or data.get("degraded"):
        hints.append("PARTIAL ACCESSIBILITY EVIDENCE: an empty query cannot prove absence. A sparse Chromium/Electron tree may not be activated. Observe again or use screenshot/CDP when available; foreground activation requires authorization.")
    if isinstance(data.get("elements"), list):
        hints.append("Use the element_token below, or snapshot_id with the ORIGINAL element_index. Query results are not renumbered. Use query/max_elements/max_depth for discovery; include_screenshot:false for tree-only refresh, include_accessibility_tree:false for image-only observation.")
    code = data.get("code")
    if code == "session_ended" or (result.get("isError") and any(
        "this session has ended" in str(block.get("text", "")) for block in result.get("content", []) if isinstance(block, dict)
    )):
        hints.append("This call uses the named session " + json.dumps(arguments["session"]) + "; explicitly start_session with that label before retrying." if arguments.get("session") else
                     "This call uses the transport's IMPLICIT session. Call start_session({}) WITHOUT a session label. Starting a named session does not revive list_apps/list_windows or other implicit calls. No input has been retried.")
    if code == "background_unavailable":
        hints.append("This is an upstream platform capability refusal. Chromium background clicks do not imply background key/scroll support. Use semantic actions or an authorized CDP channel when suitable; ask for foreground permission before changing delivery_mode. Do not repeat the same refused input.")
    if code == "browser_consent_required":
        hints.append("User setup: Execution panel > Computer Use > MCP > Allow access to signed-in browser profiles, then Save. This adds --grant existing-profile to the selected MCP runtime; registration approval may be required again. The grant does not create a DevTools endpoint. Native requires an embedding authorization host; never bypass with unrestricted mode.")
    verification = data.get("host_verification")
    if verification:
        hints.append("POSTCONDITION: " + str(verification.get("status", "unknown")) + ". Evidence covers only the supplied predicates. Unsatisfied/unknown is not success; observe before choosing another action. No input retry or foreground fallback was performed.")
        hints.append("VISUAL CONSISTENCY NOT CHECKED: driver/UIA state and rendered pixels can lag independently. For critical displayed values inspect a fresh screenshot alongside these predicates. include_screenshot supplies evidence but does not compare/OCR pixels. If they disagree, keep the result uncertain and observe again; do not resend input.")
    if tool == "replay_trajectory":
        hints.append("REPLAY DELIVERY COUNTS ONLY: succeeded counts dispatched calls, not verified business outcomes. Observe fresh state before claiming the replay achieved its goal.")
    if tool == "browser_prepare" and (arguments.get("profile") or {}).get("mode") == "isolated_new":
        hints.append("PROFILE ISOLATION ONLY: a separate profile/process is not proof of anonymous identity. OS or browser policy can automatically sign in. Observe the account state; do not claim existing account data is absent from profile isolation alone.")
    mapping = data.get("coordinate_mapping")
    if mapping:
        hints.append("FIXED DRIVER COORDINATES: max_dimension resized only this preview. Convert preview coordinates using coordinate_mapping. Native recording evidence images may have different dimensions; they are not the action's coordinate reference. Do not reuse coordinates after window size/config changes.")
    sections = ["Cua structured result: " + json.dumps(summary, ensure_ascii=False, separators=(",", ":"))] if summary else []
    sections.extend(hints)
    elements = data.get("elements")
    if isinstance(elements, list):
        # Keep every field/token and original index; do not permanently discard
        # controls to fit the preview. The normal tool-result offloader handles it.
        sections.append("Addressable elements (JSON lines):\n" + "\n".join(
            json.dumps(element, ensure_ascii=False, separators=(",", ":")) for element in elements))
    tree = data.get("tree_markdown")
    blocks = []
    for block in result.get("content", []) or []:
        block = block if isinstance(block, dict) else block.model_dump(exclude_none=True)
        if isinstance(elements, list) and tree and block.get("type") == "text" and tree in block.get("text", ""):
            # The driver's markdown duplicates the structured element list but
            # omits tokens. Retain unrelated text (capture errors etc.).
            remaining = block["text"].replace(tree, "").strip()
            if remaining:
                blocks.append({"type": "text", "text": remaining})
        elif (tool in {"click", "double_click", "right_click", "drag", "scroll", "type_text", "press_key", "hotkey", "set_window_frame"}
              and data.get("effect") == "unverifiable" and block.get("type") == "text"):
            blocks.append({**block, "text": "UNVERIFIED DRIVER RECEIPT (dispatch does not prove the stated UI effect): " + block.get("text", "").lstrip("✅ ")})
        else:
            blocks.append(block)
    return {**result, "content": ([{"type": "text", "text": "\n".join(sections)}] if sections else []) + blocks}


def image_source(tool, arguments, data=None):
    target = arguments.get("target") or {}
    scope = target.get("kind", arguments.get("scope", "window"))
    value = {"kind": "computer_use", "tool": tool,
            "coordinateSpace": "zoom_screenshot" if tool == "zoom" else
            "browser_screenshot" if tool.startswith("browser_") or tool == "get_browser_state" else
            "desktop_screenshot" if tool == "get_desktop_state" or scope == "desktop" else "window_screenshot"}
    if (data or {}).get("coordinate_mapping"):
        value["coordinateMapping"] = data["coordinate_mapping"]
    return value
