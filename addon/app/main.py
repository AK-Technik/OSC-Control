"""
ha-showcontrol Web-UI
Flask Add-on für Home Assistant
Port 7755
"""

import json
import os
import socket
import time
import threading
import queue
import glob
from datetime import datetime
from pathlib import Path

import requests
from flask import Flask, render_template, request, jsonify, Response, redirect, url_for

try:
    from pythonosc import udp_client, dispatcher, osc_server
    OSC_AVAILABLE = True
except ImportError:
    OSC_AVAILABLE = False

app = Flask(__name__)

CONFIG_PATH = os.environ.get("CONFIG_PATH", "/config/ha-showcontrol")
HA_TOKEN = os.environ.get("HA_TOKEN", "")
HA_URL = os.environ.get("HA_URL", "http://supervisor/core")

PROFILES_DIR = os.path.join(CONFIG_PATH, "profiles")
LIBRARY_DIR = os.path.join(CONFIG_PATH, "library")
DEVICES_FILE = os.path.join(CONFIG_PATH, "devices.json")

os.makedirs(PROFILES_DIR, exist_ok=True)
os.makedirs(LIBRARY_DIR, exist_ok=True)

# SSE event queue für OSC Monitor
osc_event_queue = queue.Queue(maxsize=500)

# In-memory packet counters
packet_counters = {}

# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def load_devices():
    if not os.path.exists(DEVICES_FILE):
        return []
    with open(DEVICES_FILE) as f:
        return json.load(f)

def save_devices(devices):
    with open(DEVICES_FILE, "w") as f:
        json.dump(devices, f, indent=2, ensure_ascii=False)

def load_profile(device_id):
    path = os.path.join(PROFILES_DIR, f"{device_id}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)

def save_profile(device_id, profile):
    path = os.path.join(PROFILES_DIR, f"{device_id}.json")
    with open(path, "w") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)

def list_library_profiles():
    profiles = []
    for p in glob.glob(os.path.join(LIBRARY_DIR, "*.json")):
        try:
            with open(p) as f:
                data = json.load(f)
            profiles.append({
                "filename": os.path.basename(p),
                "name": data.get("name", os.path.basename(p)),
                "device_type": data.get("device_type", "generic"),
                "entity_count": len(data.get("entities", [])),
            })
        except Exception:
            pass
    return profiles

def reload_ha_integration():
    """Ruft HA API auf um die custom integration neu zu laden."""
    if not HA_TOKEN:
        return False, "Kein HA-Token konfiguriert"
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json",
    }
    try:
        # Reload all config entries for the showcontrol domain
        r = requests.post(
            f"{HA_URL}/api/services/showcontrol/reload",
            headers=headers,
            json={},
            timeout=10,
        )
        if r.status_code == 404:
            # Fallback: restart integration via config entry reload
            # Get entry IDs first
            entries_r = requests.get(
                f"{HA_URL}/api/config/config_entries/entry",
                headers=headers, timeout=10
            )
            entries = entries_r.json() if entries_r.ok else []
            sc_entries = [e for e in entries if e.get("domain") == "showcontrol"]
            for entry in sc_entries:
                requests.post(
                    f"{HA_URL}/api/config/config_entries/entry/{entry['entry_id']}/reload",
                    headers=headers, timeout=10
                )
            r = type("R", (), {"status_code": 200})()
        if r.status_code in (200, 201):
            return True, "Integration neu geladen"
        return False, f"HA Fehler: {r.status_code}"
    except Exception as e:
        return False, str(e)

def test_connection(ip, port, device_type="generic"):
    """Testet ob ein Gerät erreichbar ist (TCP-Ping)."""
    try:
        port = int(port)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((ip, port))
        sock.close()
        if result == 0:
            return True, f"Verbunden mit {ip}:{port}"
        return False, f"Port {port} nicht erreichbar ({ip})"
    except Exception as e:
        return False, str(e)

def ping_host(ip):
    """ICMP-ähnlicher Ping via socket."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((ip, 80))
        sock.close()
        # Versuche auch OSC-Port
        return True
    except Exception:
        return False

def device_slug(name):
    return name.lower().replace(" ", "_").replace("-", "_")

def get_osc_suggestions(device_type):
    suggestions = {
        "qlcplus": [
            "/qlc/universe/1/dmx",
            "/qlc/function/run",
            "/qlc/function/stop",
            "/qlc/widget/value",
            "/qlc/channel",
        ],
        "x32": [
            "/ch/01/mix/fader",
            "/ch/01/mix/on",
            "/bus/01/mix/fader",
            "/main/st/mix/fader",
            "/dca/1/fader",
            "/dca/1/on",
        ],
        "m32": [
            "/ch/01/mix/fader",
            "/ch/01/mix/on",
            "/bus/01/mix/fader",
            "/main/st/mix/fader",
            "/dca/1/fader",
        ],
        "yamaha_ql": [
            "/mtr/recorder/transport/stop",
            "/mtr/recorder/transport/play",
            "/ch/1/fader",
            "/mix/on",
        ],
        "generic": [
            "/control/1",
            "/value",
            "/trigger",
        ],
    }
    return suggestions.get(device_type, suggestions["generic"])

def empty_profile_template(device_id, device_name, device_type):
    return {
        "name": device_name,
        "device_type": device_type,
        "version": "1.0",
        "entities": [],
    }

def get_device_status(device):
    """Schneller Online-Check."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((device["ip"], int(device["port"])))
        sock.close()
        return "online" if result == 0 else "offline"
    except Exception:
        return "offline"

# ── SSE OSC-Monitor ───────────────────────────────────────────────────────────

def push_osc_event(direction, device_name, path, value, status="ok"):
    try:
        event = {
            "ts": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "direction": direction,  # "out" or "in"
            "device": device_name,
            "path": path,
            "value": str(value),
            "status": status,
        }
        osc_event_queue.put_nowait(event)
    except queue.Full:
        pass

def osc_event_stream(device_filter=None, path_filter=None):
    while True:
        try:
            event = osc_event_queue.get(timeout=15)
            if device_filter and event["device"] != device_filter:
                continue
            if path_filter and path_filter.lower() not in event["path"].lower():
                continue
            yield f"data: {json.dumps(event)}\n\n"
        except queue.Empty:
            yield "data: {\"ping\":true}\n\n"

# ── Routes: Dashboard ──────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    devices = load_devices()
    for d in devices:
        d["status"] = get_device_status(d)
        ctr = packet_counters.get(d["id"], {"out": 0, "in": 0})
        d["packets_out"] = ctr["out"]
        d["packets_in"] = ctr["in"]
    return render_template("dashboard.html", devices=devices)

@app.route("/api/reload", methods=["POST"])
def api_reload():
    ok, msg = reload_ha_integration()
    return jsonify({"ok": ok, "message": msg})

@app.route("/api/device/<device_id>/test")
def api_test_connection(device_id):
    devices = load_devices()
    device = next((d for d in devices if d["id"] == device_id), None)
    if not device:
        return jsonify({"ok": False, "message": "Gerät nicht gefunden"})
    ok, msg = test_connection(device["ip"], device["port"], device.get("type"))
    return jsonify({"ok": ok, "message": msg})

@app.route("/api/device/<device_id>/delete", methods=["POST"])
def api_delete_device(device_id):
    devices = load_devices()
    devices = [d for d in devices if d["id"] != device_id]
    save_devices(devices)
    profile_path = os.path.join(PROFILES_DIR, f"{device_id}.json")
    if os.path.exists(profile_path):
        os.remove(profile_path)
    reload_ha_integration()
    return jsonify({"ok": True})

# ── Routes: Wizard ─────────────────────────────────────────────────────────────

@app.route("/add")
def wizard_step1():
    return render_template("wizard_step1.html")

@app.route("/add/step2")
def wizard_step2():
    device_type = request.args.get("type", "generic")
    return render_template("wizard_step2.html", device_type=device_type)

@app.route("/add/step3")
def wizard_step3():
    device_type = request.args.get("type", "generic")
    ip = request.args.get("ip", "")
    port = request.args.get("port", "")
    name = request.args.get("name", "")
    library = list_library_profiles()
    return render_template(
        "wizard_step3.html",
        device_type=device_type,
        ip=ip,
        port=port,
        name=name,
        library=library,
    )

@app.route("/api/test-connection", methods=["POST"])
def api_test_connection_wizard():
    data = request.json
    ok, msg = test_connection(data.get("ip", ""), data.get("port", 8000))
    return jsonify({"ok": ok, "message": msg})

@app.route("/api/add-device", methods=["POST"])
def api_add_device():
    data = request.json
    devices = load_devices()
    device_id = device_slug(data["name"]) + "_" + str(int(time.time()))[-4:]
    
    device = {
        "id": device_id,
        "name": data["name"],
        "type": data["device_type"],
        "ip": data["ip"],
        "port": int(data["port"]),
        "created": datetime.now().isoformat(),
    }
    devices.append(device)
    save_devices(devices)

    # Profil anlegen
    if data.get("library_profile"):
        lib_path = os.path.join(LIBRARY_DIR, data["library_profile"])
        if os.path.exists(lib_path):
            with open(lib_path) as f:
                profile = json.load(f)
            profile["name"] = data["name"]
        else:
            profile = empty_profile_template(device_id, data["name"], data["device_type"])
    else:
        profile = empty_profile_template(device_id, data["name"], data["device_type"])

    save_profile(device_id, profile)
    ok, msg = reload_ha_integration()
    return jsonify({"ok": True, "device_id": device_id, "reload": msg})

# ── Routes: Profil-Editor ──────────────────────────────────────────────────────

@app.route("/device/<device_id>/profile")
def profile_editor(device_id):
    devices = load_devices()
    device = next((d for d in devices if d["id"] == device_id), None)
    if not device:
        return redirect(url_for("dashboard"))
    profile = load_profile(device_id) or empty_profile_template(device_id, device["name"], device.get("type", "generic"))
    suggestions = get_osc_suggestions(device.get("type", "generic"))
    return render_template(
        "profile_editor.html",
        device=device,
        profile=profile,
        suggestions=suggestions,
    )

@app.route("/api/device/<device_id>/profile", methods=["GET"])
def api_get_profile(device_id):
    profile = load_profile(device_id)
    if not profile:
        return jsonify({"entities": []})
    return jsonify(profile)

@app.route("/api/device/<device_id>/profile", methods=["POST"])
def api_save_profile(device_id):
    profile = request.json
    save_profile(device_id, profile)
    ok, msg = reload_ha_integration()
    return jsonify({"ok": True, "reload": msg})

@app.route("/api/device/<device_id>/entity/add", methods=["POST"])
def api_add_entity(device_id):
    data = request.json
    profile = load_profile(device_id) or {"entities": []}
    entity_id = data.get("name", "").lower().replace(" ", "_") + "_" + str(int(time.time()))[-4:]
    entity = {
        "id": entity_id,
        "name": data["name"],
        "type": data["type"],
        "osc_path": data["osc_path"],
    }
    if data["type"] == "number":
        entity["min"] = data.get("min", 0)
        entity["max"] = data.get("max", 255)
    elif data["type"] == "switch":
        entity["on_value"] = data.get("on_value", 1)
        entity["off_value"] = data.get("off_value", 0)
    profile.setdefault("entities", []).append(entity)
    save_profile(device_id, profile)
    ok, msg = reload_ha_integration()
    return jsonify({"ok": True, "entity": entity, "reload": msg})

@app.route("/api/device/<device_id>/entity/<entity_id>/delete", methods=["POST"])
def api_delete_entity(device_id, entity_id):
    profile = load_profile(device_id)
    if not profile:
        return jsonify({"ok": False})
    profile["entities"] = [e for e in profile.get("entities", []) if e["id"] != entity_id]
    save_profile(device_id, profile)
    reload_ha_integration()
    return jsonify({"ok": True})

# ── Routes: OSC-Monitor ────────────────────────────────────────────────────────

@app.route("/monitor")
def osc_monitor():
    devices = load_devices()
    return render_template("osc_monitor.html", devices=devices)

@app.route("/api/osc/stream")
def osc_stream():
    device_filter = request.args.get("device") or None
    path_filter = request.args.get("path") or None
    return Response(
        osc_event_stream(device_filter, path_filter),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

@app.route("/api/osc/send", methods=["POST"])
def api_osc_send():
    if not OSC_AVAILABLE:
        return jsonify({"ok": False, "message": "python-osc nicht installiert"})
    data = request.json
    device_id = data.get("device_id")
    devices = load_devices()
    device = next((d for d in devices if d["id"] == device_id), None)
    if not device:
        return jsonify({"ok": False, "message": "Gerät nicht gefunden"})
    try:
        client = udp_client.SimpleUDPClient(device["ip"], int(device["port"]))
        value = data.get("value", 0)
        try:
            value = float(value)
        except (ValueError, TypeError):
            pass
        client.send_message(data["path"], value)
        push_osc_event("out", device["name"], data["path"], value, "ok")
        ctr = packet_counters.setdefault(device_id, {"out": 0, "in": 0})
        ctr["out"] += 1
        return jsonify({"ok": True})
    except Exception as e:
        push_osc_event("out", device["name"], data["path"], data.get("value"), "error")
        return jsonify({"ok": False, "message": str(e)})

# ── Routes: Diagnose ───────────────────────────────────────────────────────────

@app.route("/diagnose")
def diagnose():
    devices = load_devices()
    return render_template("diagnose.html", devices=devices)

@app.route("/api/diagnose/<device_id>")
def api_diagnose(device_id):
    devices = load_devices()
    device = next((d for d in devices if d["id"] == device_id), None)
    if not device:
        return jsonify({"ok": False})

    # TCP-Verbindungstest mit Zeitmessung
    start = time.time()
    ok, msg = test_connection(device["ip"], device["port"])
    latency = round((time.time() - start) * 1000, 1)

    ctr = packet_counters.get(device_id, {"out": 0, "in": 0})

    return jsonify({
        "ok": ok,
        "message": msg,
        "latency_ms": latency if ok else None,
        "ip": device["ip"],
        "port": device["port"],
        "packets_out": ctr["out"],
        "packets_in": ctr["in"],
        "timestamp": datetime.now().isoformat(),
    })

# ── Start ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Beispiel-Library-Profile anlegen wenn leer
    _qlc_lib = os.path.join(LIBRARY_DIR, "qlcplus_standard.json")
    if not os.path.exists(_qlc_lib):
        with open(_qlc_lib, "w") as f:
            json.dump({
                "name": "QLC+ Standard",
                "device_type": "qlcplus",
                "version": "1.0",
                "entities": [
                    {"id": "master_fader", "name": "Master Fader", "type": "number",
                     "osc_path": "/qlc/universe/1/dmx", "min": 0, "max": 255},
                    {"id": "function_run", "name": "Szene starten", "type": "button",
                     "osc_path": "/qlc/function/run"},
                    {"id": "function_stop", "name": "Szene stoppen", "type": "button",
                     "osc_path": "/qlc/function/stop"},
                ],
            }, f, indent=2)

    _x32_lib = os.path.join(LIBRARY_DIR, "x32_standard.json")
    if not os.path.exists(_x32_lib):
        with open(_x32_lib, "w") as f:
            json.dump({
                "name": "Behringer X32 Standard",
                "device_type": "x32",
                "version": "1.0",
                "entities": [
                    {"id": "main_fader", "name": "Main Fader", "type": "number",
                     "osc_path": "/main/st/mix/fader", "min": 0.0, "max": 1.0},
                    {"id": "ch01_fader", "name": "Kanal 1 Fader", "type": "number",
                     "osc_path": "/ch/01/mix/fader", "min": 0.0, "max": 1.0},
                    {"id": "ch01_mute", "name": "Kanal 1 Mute", "type": "switch",
                     "osc_path": "/ch/01/mix/on", "on_value": 1, "off_value": 0},
                    {"id": "dca1_fader", "name": "DCA 1 Fader", "type": "number",
                     "osc_path": "/dca/1/fader", "min": 0.0, "max": 1.0},
                ],
            }, f, indent=2)

    app.run(host="0.0.0.0", port=7755, debug=False, threaded=True)
