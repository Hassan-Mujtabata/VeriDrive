import os, io, tarfile, threading, webbrowser, requests
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

API_KEY  = os.getenv("RETELL_API_KEY")
AGENT_ID = os.getenv("RETELL_AGENT_ID")
OUTFILE  = "transcript.txt"
HERE     = os.path.dirname(os.path.abspath(__file__))
BUNDLE   = os.path.join(HERE, "sdk_bundle.js")

app = Flask(__name__)
CORS(app)

# ── Helpers ──────────────────────────────────────────────────────────────────

def append(line: str):
    with open(OUTFILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def fetch_umd(package: str, version: str, umd_path: str) -> bytes:
    """Download npm tarball and extract one UMD file from it."""
    url = f"https://registry.npmjs.org/{package}/-/{package}-{version}.tgz"
    print(f"  [~] Downloading {package}@{version}...")
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    with tarfile.open(fileobj=io.BytesIO(resp.content), mode="r:gz") as tar:
        member = tar.extractfile(umd_path)
        if member is None:
            raise FileNotFoundError(f"{umd_path} not found in {package} tarball")
        return member.read()

def build_bundle():
    """Download all deps and concatenate into sdk_bundle.js."""
    print("[~] Building SDK bundle (first run only — may take ~30s)...")
    ee3    = fetch_umd("eventemitter3",      "5.0.4",  "package/dist/eventemitter3.umd.min.js")
    lk     = fetch_umd("livekit-client",    "2.19.0", "package/dist/livekit-client.umd.js")
    retell = fetch_umd("retell-client-js-sdk", "2.0.7", "package/dist/index.umd.js")

    with open(BUNDLE, "wb") as f:
        f.write(ee3)
        f.write(b"\nwindow.eventemitter3 = window.EventEmitter3;\n")
        f.write(lk)
        f.write(b"\nwindow.livekitClient = window.LivekitClient;\n")
        f.write(retell)
    print(f"[✓] SDK bundle ready ({os.path.getsize(BUNDLE)//1024} KB)")

# ── HTML ──────────────────────────────────────────────────────────────────────

HTML = """<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Retell Debug</title>
  <style>
    body { font-family: Arial, sans-serif; padding: 20px; background: #1a1a1a; color: #eee; }
    h3   { color: #3E6AEF; }
    button {
      padding: 10px 18px; margin-right: 8px;
      font-size: 16px; border: none; border-radius: 6px;
      cursor: pointer; font-weight: bold;
    }
    #start { background: #3E6AEF; color: #fff; }
    #start:disabled { background: #444; color: #888; cursor: not-allowed; }
    #stop  { background: #da3633; color: #fff; }
    #stop:disabled { background: #444; color: #888; cursor: not-allowed; }
    #log {
      white-space: pre-wrap; border: 2px solid #333;
      padding: 10px; margin-top: 12px; height: 420px;
      overflow: auto; background: #111; color: #0f0;
      font-family: monospace; font-size: 13px; border-radius: 6px;
    }
  </style>
</head>
<body>
  <h3>🎙️ Retell Debug Page</h3>
  <button id="start">Start (mic)</button>
  <button id="stop" disabled>Stop</button>
  <div id="log"></div>

  <script src="/sdk.js"></script>
  <script>
    const FLASK_URL = "http://127.0.0.1:5000";
    const logEl = document.getElementById("log");

    function log(s) {
      const ts = new Date().toLocaleTimeString();
      logEl.textContent += "[" + ts + "] " + s + "\\n";
      logEl.scrollTop = logEl.scrollHeight;
      console.log(s);
    }

    log("Page loaded.");
    log("typeof retellClientJsSdk = " + typeof retellClientJsSdk);
    log("typeof RetellWebClient   = " + (typeof retellClientJsSdk !== 'undefined'
        ? typeof retellClientJsSdk.RetellWebClient : 'n/a'));

    let client = null;
    let currentCallId = "";
    let latestTranscript = [];

    async function saveFullTranscript() {
      // Deduplicate: only keep last content per consecutive role block
      const lines = [];
      for (const t of latestTranscript) {
        const last = lines[lines.length - 1];
        if (last && last.role === t.role) {
          lines[lines.length - 1] = t; // replace with latest
        } else {
          lines.push(t);
        }
      }
      for (const t of lines) {
        try {
          await fetch(FLASK_URL + "/transcript", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ role: t.role, text: t.content, callId: currentCallId }),
          });
        } catch(e) { log("Save failed: " + e.message); }
      }
    }

    document.getElementById("start").onclick = async () => {
      log("▶ Start clicked — fetching access token...");
      document.getElementById("start").disabled = true;

      let accessToken = "";
      try {
        const resp = await fetch(FLASK_URL + "/create-call");
        const data = await resp.json();
        if (data.error) {
          log("❌ Server error: " + data.error);
          document.getElementById("start").disabled = false;
          return;
        }
        accessToken   = data.accessToken;
        currentCallId = data.callId;
        log("✅ Got access token. Call ID: " + currentCallId);
      } catch(e) {
        log("❌ Could not reach server: " + e.message);
        document.getElementById("start").disabled = false;
        return;
      }

      try {
        client = new retellClientJsSdk.RetellWebClient();
        log("✅ RetellWebClient created.");
      } catch(e) {
        log("❌ Failed to create RetellWebClient: " + e.message);
        document.getElementById("start").disabled = false;
        return;
      }

      client.on("call_started", () => {
        log("✅ call_started");
        document.getElementById("stop").disabled = false;
      });

      client.on("call_ended", async () => {
        log("call_ended — saving transcript...");
        await saveFullTranscript();
        log("✅ Transcript saved to transcript.txt");
        document.getElementById("start").disabled = false;
        document.getElementById("stop").disabled  = true;
        latestTranscript = [];
        currentCallId = "";
      });

      client.on("error", (e) => {
        log("❌ error: " + JSON.stringify(e));
        document.getElementById("start").disabled = false;
        document.getElementById("stop").disabled  = true;
      });

      client.on("update", (update) => {
        if (update && update.transcript) {
          latestTranscript = update.transcript;
          const last = update.transcript[update.transcript.length - 1];
          if (last) log(last.role + ": " + last.content);
        }
      });

      client.on("agent_stop_talking", () => log("agent_stop_talking"));
      client.on("agent_start_talking", () => log("agent_start_talking"));



      log("▶ Calling startCall()...");
      try {
        await client.startCall({ accessToken });
        log("✅ startCall() resolved.");
      } catch(e) {
        log("❌ startCall() error: " + (e && e.message ? e.message : JSON.stringify(e)));
        document.getElementById("start").disabled = false;
      }
    };

    document.getElementById("stop").onclick = () => {
      log("⏹ Stop clicked.");
      if (client) client.stopCall();
    };

    log("✅ Ready — click Start.");
  </script>
</body>
</html>"""

# ── Flask routes ──────────────────────────────────────────────────────────────

@app.get("/")
def index():
    return Response(HTML, mimetype="text/html")

@app.get("/sdk.js")
def sdk_js():
    with open(BUNDLE, "rb") as f:
        return Response(f.read(), mimetype="application/javascript")

@app.get("/create-call")
def create_call():
    if not API_KEY or not AGENT_ID:
        return jsonify({"error": "Missing RETELL_API_KEY or RETELL_AGENT_ID in .env"}), 500
    resp = requests.post(
        "https://api.retellai.com/v2/create-web-call",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={"agent_id": AGENT_ID},
    )
    if resp.status_code != 201:
        return jsonify({"error": f"Retell API error {resp.status_code}: {resp.text}"}), 500
    data = resp.json()
    append(f"\n=== New call {data['call_id']} @ {datetime.now().isoformat(timespec='seconds')} ===")
    return jsonify({"accessToken": data["access_token"], "callId": data["call_id"]})

@app.post("/transcript")
def transcript():
    data    = request.get_json(force=True) or {}
    role    = data.get("role", "unknown")
    text    = (data.get("text") or "").strip()
    call_id = data.get("callId", "")
    if not text:
        return jsonify({"ok": True})
    ts     = datetime.now().isoformat(timespec="seconds")
    prefix = f"[{ts}]"
    if call_id:
        prefix += f" [{call_id}]"
    append(f"{prefix} {role.upper()}: {text}")
    return jsonify({"ok": True})

# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"[✓] API_KEY  : {'loaded' if API_KEY  else '❌ MISSING'}")
    print(f"[✓] AGENT_ID : {'loaded' if AGENT_ID else '❌ MISSING'}")

    if not os.path.exists(BUNDLE):
        build_bundle()
    else:
        print(f"[✓] SDK bundle already exists ({os.path.getsize(BUNDLE)//1024} KB)")

    print("[~] Starting server and opening browser...")
    threading.Timer(1.2, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(host="127.0.0.1", port=5000, debug=False)
