"""
Local block page server.

During an active focus session, blocked sites are redirected to 127.0.0.1
via the hosts file.  Two servers run in parallel:

  • port 80  — serves the block page for HTTP traffic
  • port 443 — serves the same page over TLS for HTTPS traffic

The TLS certificate is self-signed; browsers will show a "Not Private"
warning on first visit, but the user can proceed to see the block page.
"""

import os
import ssl
import tempfile
import threading
import socketserver
import http.server

_http_server   = None
_https_server  = None
_http_thread   = None
_https_thread  = None

# ── Embedded TLS certificate (self-signed, valid 10 years) ────────────────────
# Generated once; embedded so no openssl binary is needed at runtime.

_CERT_PEM = """\
-----BEGIN CERTIFICATE-----
MIIDZjCCAk6gAwIBAgIUFTlcX8ISpVid/dgnQqiPbaC7SB0wDQYJKoZIhvcNAQEL
BQAwOjELMAkGA1UEBhMCTkcxEDAOBgNVBAoMB05BQ09NRVMxGTAXBgNVBAMMEGZv
Y3VzZ3VhcmQubG9jYWwwHhcNMjYwNTI5MTIyODM5WhcNMzYwNTI2MTIyODM5WjA6
MQswCQYDVQQGEwJORzEQMA4GA1UECgwHTkFDT01FUzEZMBcGA1UEAwwQZm9jdXNn
dWFyZC5sb2NhbDCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAJaYonGv
nJrYTHsEJ8xNN3PzHVv0aJl/mZKnsKKdQ9xR8ty8JuHAjuuylW8AqkBJCVrq/PTP
xqKrg4K2Y4+8LN2KK7SuPiRYhkDyKptLd9DSgsgAN7FCmeNGyT+1mnXP/XnF5IS6
BSi7gpdCB+yV03GvriQwvjuJQg7rEsNwqvu5xsw016pHB1aV0p7k3OQG9YAgP9Ts
jqSgP3KoVCxxGqxRVTM7ZhDiDo94WtYLrUi4DByhYFFPuOMG4xg2YjLduKNFo7D+
HFJmdWcYLc/dWRXCvcJdo7MrHkEIpIk0xXV1NpRn+WwX7+KRKSJLpG/DFcR8NDB5
uIHOpsfFT5ZpjLsCAwEAAaNkMGIwHQYDVR0OBBYEFFnvdk29fdKlTU30QFhpUuCj
Hb7hMB8GA1UdIwQYMBaAFFnvdk29fdKlTU30QFhpUuCjHb7hMA8GA1UdEwEB/wQF
MAMBAf8wDwYDVR0RBAgwBocEfwAAATANBgkqhkiG9w0BAQsFAAOCAQEANcvUpGVP
KXuWIAvmph9jxAz/FC1rh+dBmIUZVRl9XyOqpcdi6zx7X1NUN3ly2eMOcoeIpEdU
BzxqgqRnIyyY2VJ+FV40xBKx9l4RHjXj931r3NFY0192rKl7ywYnUTFyix/CYV6T
DTgR0WJw9uGSKUL7tdhRCcbpVC3640cd2RMtyySmeLYIsIj9Ueev9JEPa9abZs7B
HnwkwEwHf6qH06k72n92qI4vUOjmSB+6guMzXOQvEhmjd57WsQqDzE9j+x+5bGE2
ixmVpKLZIM7qsJb/AHD1IJM/FCDGbos+0vCJosO4u4WfO9D2KTBA1g8iUbA4aqXu
B3D241WqFB1TLA==
-----END CERTIFICATE-----"""

_KEY_PEM = """\
-----BEGIN PRIVATE KEY-----
MIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQCWmKJxr5ya2Ex7
BCfMTTdz8x1b9GiZf5mSp7CinUPcUfLcvCbhwI7rspVvAKpASQla6vz0z8aiq4OC
tmOPvCzdiiu0rj4kWIZA8iqbS3fQ0oLIADexQpnjRsk/tZp1z/15xeSEugUou4KX
QgfsldNxr64kML47iUIO6xLDcKr7ucbMNNeqRwdWldKe5NzkBvWAID/U7I6koD9y
qFQscRqsUVUzO2YQ4g6PeFrWC61IuAwcoWBRT7jjBuMYNmIy3bijRaOw/hxSZnVn
GC3P3VkVwr3CXaOzKx5BCKSJNMV1dTaUZ/lsF+/ikSkiS6RvwxXEfDQwebiBzqbH
xU+WaYy7AgMBAAECggEAA6FyaSM+t0z3qw+Slg5Wg+kckBb4XpsA7NQ2IfWAqVMg
c8nldhPaXjxT9fUiJaKdIx//MTfBJjLUXNZg2BpFSqIGI7j/roij0/UCqfPL07D/
jirTLObaJuyR9YM/Ug/NoJ3wwHJrpWu/3j2tSzrheiAuJpk2POE2Qn3QWf3hYWgz
tAqfHP+30J1P8yZpSeKZqOFq7GOUyN8g3JfdotwKhJQXQdn3NA/8Q9xC2kSXU6eS
LI9+cJ4/Gpxt/sLs710Ft1Ls1AzxU0HwEkdd5RoBgZScJZQT65clxjKPUfPY+wqw
/X6xWGNcX0SA1PZH6sWJZ5bSKjv1WNnDCZp48nQIAQKBgQDObWGvz8F1PyeQAFs0
iWECYC/W1tTI7uaNrdIBXbRHS4T+cYjE9uwr4B/FAVgiHl/zePBIozHTsBCF/Xaz
N4QvH5pjOsNmf8qszk98tcWTbSudRgfJHQWOHfZPe8y6s9xC8NWggyDAgDw8cUKc
2pM3Z6VPoMrCALE+BkojJ0tfAQKBgQC6wudiPoTKbCY6xGSlEMhfcRnrncSgC+/a
pPZeCCWYTO63Ak9MhQdUxpeo3Td/dbPUkUZRV87fOirC/Ml0SCgbR/CS78kR0hRw
a4IFR3ncaLvJ7wNNWqwloWWw/+5fMHnWcbggBqnwF6iDdjOpcAJ5E5FDA1l7O+mU
SAqjiOInuwKBgQC1C9wcfWNYOL6zHozfhAnQMppim+LeJCGTazr/tbZyvTp0ixEA
Zux2Asj6WRZ6Phe7i3t6yZ7e4dFsIwRjZLKLPfWDSDuufzA75Wpzn10c0yfodU5I
xipkHcU0qwjBSxRIpb9HWxpzm0S5YkChH1b0xfOH5idOhZruIkgNkt4ZAQKBgQCo
c7QQQSO1EOdKimndGM4ih/lBNARt91ZYeAJfvilqvblzCHpOIo8CQD366c1tAdU6
He623+SQI/798NQkNhE2yiSL5AwQLtSQseeMq3OXAkCfWx43X1l2d6UpiS6QXUEH
03qoKFqPXEd6i9r9MTKJ0sRrFVJYfSmpvXEbIBQckQKBgQCDilI/J0ht9cHbEvHD
SDSuQ0g+HfOmI35tAzpiKoDuTa6iaxRThi7TNcru5wiHVol9p6iEMw52zWSAQ79i
9empZ6Bm14qZRJk66VrtSkV2u23bFX3NKeElrAoivPQ6gvDwTXZ7ublS/lKTfVjc
Jg1QRhwXHl0SkyelKxJpHnTbhg==
-----END PRIVATE KEY-----"""


def _make_ssl_context():
    """Build an SSLContext from the embedded PEM strings."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    # ssl.SSLContext.load_cert_chain() requires file paths, so write to temp
    # files then delete them immediately after loading into the context.
    tmp_cert = tempfile.NamedTemporaryFile(suffix=".pem", delete=False)
    tmp_key  = tempfile.NamedTemporaryFile(suffix=".pem", delete=False)
    try:
        tmp_cert.write(_CERT_PEM.encode())
        tmp_cert.close()
        tmp_key.write(_KEY_PEM.encode())
        tmp_key.close()
        ctx.load_cert_chain(certfile=tmp_cert.name, keyfile=tmp_key.name)
    finally:
        for path in (tmp_cert.name, tmp_key.name):
            try:
                os.unlink(path)
            except OSError:
                pass
    return ctx


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


# ── HTTPS server (wraps each accepted socket with TLS) ────────────────────────

class _HttpsServer(socketserver.TCPServer):
    allow_reuse_address = True

    def __init__(self, addr, handler, ssl_ctx):
        self._ssl_ctx = ssl_ctx
        super().__init__(addr, handler)

    def get_request(self):
        conn, addr = self.socket.accept()
        try:
            return self._ssl_ctx.wrap_socket(conn, server_side=True), addr
        except ssl.SSLError:
            conn.close()
            raise   # caught as OSError by TCPServer._handle_request_noblock

    def handle_error(self, request, client_address):
        pass   # silence SSL handshake errors


# ── Public API ─────────────────────────────────────────────────────────────────

def start_block_server():
    """Start block-page servers on 127.0.0.1:80 (HTTP) and :443 (HTTPS)."""
    global _http_server, _https_server, _http_thread, _https_thread

    if _http_server is not None:
        return

    # HTTP server
    try:
        socketserver.TCPServer.allow_reuse_address = True
        srv = socketserver.TCPServer(("127.0.0.1", 80), _BlockHandler)
        _http_server = srv
        _http_thread = threading.Thread(target=srv.serve_forever, daemon=True)
        _http_thread.start()
    except Exception:
        pass

    # HTTPS server
    try:
        ssl_ctx = _make_ssl_context()
        srv = _HttpsServer(("127.0.0.1", 443), _BlockHandler, ssl_ctx)
        _https_server = srv
        _https_thread = threading.Thread(target=srv.serve_forever, daemon=True)
        _https_thread.start()
    except Exception:
        pass


def stop_block_server():
    """Shut down both block-page servers."""
    global _http_server, _https_server, _http_thread, _https_thread

    for attr in ("_http_server", "_https_server"):
        srv = globals()[attr]
        if srv:
            try:
                srv.shutdown()
            except Exception:
                pass
    _http_server  = None
    _https_server = None
    _http_thread  = None
    _https_thread = None
