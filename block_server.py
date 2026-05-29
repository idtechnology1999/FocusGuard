"""
Local block page server.

During an active focus session, blocked sites are redirected to 127.0.0.1
via the hosts file. This server listens on port 80 and serves a branded
"This site is blocked" page instead of a browser error.
"""

import threading
import socketserver
import http.server

_http_server  = None
_server_thread = None

# ── Block page HTML ────────────────────────────────────────────────────────────

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Blocked by Focus Guard</title>
  <style>
    *, *::before, *::after { margin:0; padding:0; box-sizing:border-box; }

    body {
      background: #060d1a;
      font-family: 'Segoe UI', system-ui, sans-serif;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
    }

    /* Floating orbs */
    .orb {
      position: fixed;
      border-radius: 50%;
      filter: blur(80px);
      pointer-events: none;
      animation: orbFloat 8s ease-in-out infinite;
    }
    .orb1 { width:400px; height:400px; background:rgba(59,130,246,0.12); top:-100px; left:-100px; animation-delay:0s; }
    .orb2 { width:300px; height:300px; background:rgba(20,184,166,0.10); bottom:-80px; right:-80px; animation-delay:3s; }
    .orb3 { width:200px; height:200px; background:rgba(239,68,68,0.08);  top:50%; left:50%; transform:translate(-50%,-50%); animation-delay:1.5s; }
    @keyframes orbFloat {
      0%,100% { transform: translate(0,0) scale(1); }
      33%      { transform: translate(20px,-20px) scale(1.05); }
      66%      { transform: translate(-15px,15px) scale(0.97); }
    }
    .orb3 { animation-name: orbFloat3; }
    @keyframes orbFloat3 {
      0%,100% { transform: translate(-50%,-50%) scale(1); }
      50%      { transform: translate(-50%,-50%) scale(1.3); }
    }

    /* Glass card */
    .card {
      position: relative;
      background: rgba(17,29,48,0.85);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      border: 1px solid rgba(59,130,246,0.20);
      border-radius: 28px;
      padding: 52px 68px 44px;
      text-align: center;
      max-width: 600px;
      width: 93%;
      box-shadow:
        0 32px 100px rgba(0,0,0,0.7),
        inset 0 1px 0 rgba(255,255,255,0.05);
      animation: cardIn 0.6s cubic-bezier(0.34,1.56,0.64,1) both;
    }
    @keyframes cardIn {
      from { opacity:0; transform:translateY(30px) scale(0.95); }
      to   { opacity:1; transform:translateY(0)    scale(1); }
    }

    /* Rainbow top border */
    .card::before {
      content:'';
      position:absolute;
      inset:0;
      border-radius:28px;
      padding:1.5px;
      background: linear-gradient(135deg,
        #3b82f6, #14b8a6, #22c55e, #3b82f6);
      -webkit-mask: linear-gradient(#fff 0 0) content-box,
                    linear-gradient(#fff 0 0);
      -webkit-mask-composite: xor;
      mask-composite: exclude;
      background-size: 300% 300%;
      animation: borderShift 4s ease infinite;
      opacity: 0.6;
    }
    @keyframes borderShift {
      0%   { background-position: 0% 50%; }
      50%  { background-position: 100% 50%; }
      100% { background-position: 0% 50%; }
    }

    /* Shield */
    .shield-ring {
      position: relative;
      width: 110px;
      height: 110px;
      margin: 0 auto 22px;
    }
    .ring {
      position: absolute;
      inset: 0;
      border-radius: 50%;
      border: 2px solid rgba(59,130,246,0.3);
      animation: ringExpand 2.4s ease-out infinite;
    }
    .ring:nth-child(2) { animation-delay: 0.8s; }
    .ring:nth-child(3) { animation-delay: 1.6s; }
    @keyframes ringExpand {
      0%   { transform: scale(0.8); opacity: 0.8; }
      100% { transform: scale(1.6); opacity: 0; }
    }
    .shield-icon {
      position: absolute;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      background: rgba(59,130,246,0.12);
      border-radius: 50%;
      border: 1.5px solid rgba(59,130,246,0.4);
      font-size: 48px;
      animation: shieldGlow 2.5s ease-in-out infinite;
    }
    @keyframes shieldGlow {
      0%,100% { filter: drop-shadow(0 0 12px rgba(59,130,246,0.6)); }
      50%      { filter: drop-shadow(0 0 28px rgba(59,130,246,1)); }
    }

    .brand {
      font-size: 10px;
      font-weight: 800;
      letter-spacing: 5px;
      background: linear-gradient(90deg, #3b82f6, #14b8a6);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      text-transform: uppercase;
      margin-bottom: 24px;
    }

    .title {
      font-size: 30px;
      font-weight: 800;
      color: #f0f6ff;
      line-height: 1.3;
      margin-bottom: 8px;
      letter-spacing: -0.5px;
    }
    .title .highlight {
      background: linear-gradient(90deg, #ef4444, #f97316);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }

    .subtitle {
      font-size: 14px;
      color: #8ba4be;
      margin-bottom: 24px;
    }

    .site-badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      background: rgba(239,68,68,0.08);
      border: 1px solid rgba(239,68,68,0.25);
      border-radius: 50px;
      padding: 9px 24px;
      margin-bottom: 32px;
      font-family: 'Consolas','Courier New',monospace;
      font-size: 13px;
      color: #fca5a5;
      animation: badgePulse 2s ease-in-out infinite;
    }
    .site-badge::before { content:'🔗'; font-size:12px; }
    @keyframes badgePulse {
      0%,100% { box-shadow: 0 0 0 0 rgba(239,68,68,0.2); }
      50%      { box-shadow: 0 0 0 6px rgba(239,68,68,0); }
    }

    .divider {
      border: none;
      height: 1px;
      background: linear-gradient(90deg, transparent, rgba(59,130,246,0.25), transparent);
      margin: 0 0 28px;
    }

    /* Stats row */
    .stats {
      display: flex;
      justify-content: center;
      gap: 0;
      margin-bottom: 28px;
    }
    .stat {
      flex: 1;
      padding: 14px 0;
    }
    .stat:not(:last-child) {
      border-right: 1px solid rgba(59,130,246,0.15);
    }
    .stat-icon { font-size: 20px; display: block; margin-bottom: 5px; }
    .stat-label {
      font-size: 9px;
      font-weight: 700;
      letter-spacing: 2px;
      color: #3d5a7a;
      text-transform: uppercase;
      display: block;
      margin-bottom: 4px;
    }
    .stat-value {
      font-size: 12px;
      font-weight: 700;
      color: #8ba4be;
    }
    .stat-value.green { color: #22c55e; }
    .stat-value.blue  { color: #3b82f6; }

    /* Message */
    .message {
      background: rgba(59,130,246,0.05);
      border: 1px solid rgba(59,130,246,0.12);
      border-radius: 14px;
      padding: 18px 22px;
      font-size: 13.5px;
      color: #8ba4be;
      line-height: 1.8;
      margin-bottom: 20px;
    }
    .message strong { color: #e8f0fe; }

    /* Live indicator */
    .live-row {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      margin-bottom: 28px;
    }
    .live-dot {
      width: 8px; height: 8px;
      background: #22c55e;
      border-radius: 50%;
      box-shadow: 0 0 6px #22c55e;
      animation: liveBlink 1.2s ease-in-out infinite;
    }
    @keyframes liveBlink {
      0%,100% { opacity:1; transform:scale(1); }
      50%      { opacity:0.3; transform:scale(0.8); }
    }
    .live-text {
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 2.5px;
      color: #22c55e;
      text-transform: uppercase;
    }

    .footer {
      font-size: 10px;
      letter-spacing: 2.5px;
      color: #1e304f;
      text-transform: uppercase;
    }
  </style>
</head>
<body>
  <div class="orb orb1"></div>
  <div class="orb orb2"></div>
  <div class="orb orb3"></div>

  <div class="card">

    <div class="shield-ring">
      <div class="ring"></div>
      <div class="ring"></div>
      <div class="ring"></div>
      <div class="shield-icon">🛡️</div>
    </div>

    <div class="brand">NACOMES &nbsp;&bull;&nbsp; Focus Guard</div>

    <div class="title">This Site Is <span class="highlight">Blocked</span></div>
    <div class="subtitle">Access denied by your active focus session</div>

    <div class="site-badge">BLOCKED_SITE</div>

    <hr class="divider">

    <div class="stats">
      <div class="stat">
        <span class="stat-icon">🔒</span>
        <span class="stat-label">Status</span>
        <span class="stat-value green">Blocked</span>
      </div>
      <div class="stat">
        <span class="stat-icon">⏱️</span>
        <span class="stat-label">Session</span>
        <span class="stat-value blue">Active</span>
      </div>
      <div class="stat">
        <span class="stat-icon">🎯</span>
        <span class="stat-label">Mode</span>
        <span class="stat-value">Deep Focus</span>
      </div>
    </div>

    <div class="message">
      You made a commitment to <strong>stay focused</strong> — and Focus Guard is
      keeping it for you.<br>
      This website is blocked until your session timer reaches zero.<br><br>
      <strong>Step away from distractions. Your future self will thank you. 🚀</strong>
    </div>

    <div class="live-row">
      <div class="live-dot"></div>
      <div class="live-text">Focus Session Running</div>
    </div>

    <div class="footer">NACOMES &nbsp;&middot;&nbsp; The Polytechnic, Ibadan &nbsp;&middot;&nbsp; 2026</div>
  </div>
</body>
</html>"""


# ── Request handler ────────────────────────────────────────────────────────────

class _BlockHandler(http.server.BaseHTTPRequestHandler):

    def _serve(self):
        host = self.headers.get("Host", "this site").split(":")[0]
        html = _HTML.replace("BLOCKED_SITE", host)
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type",   "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control",  "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  self._serve()
    def do_POST(self): self._serve()
    def do_HEAD(self): self._serve()

    def log_message(self, *args):
        pass   # silence console output


# ── Public API ─────────────────────────────────────────────────────────────────

def start_block_server():
    """Start the local block-page server on 127.0.0.1:80."""
    global _http_server, _server_thread
    if _http_server is not None:
        return
    try:
        socketserver.TCPServer.allow_reuse_address = True
        srv = socketserver.TCPServer(("127.0.0.1", 80), _BlockHandler)
        _http_server = srv
        _server_thread = threading.Thread(target=srv.serve_forever, daemon=True)
        _server_thread.start()
    except Exception:
        pass   # port 80 busy or permission issue — silently skip


def stop_block_server():
    """Shut down the block-page server."""
    global _http_server, _server_thread
    if _http_server:
        try:
            _http_server.shutdown()
        except Exception:
            pass
        _http_server  = None
        _server_thread = None
