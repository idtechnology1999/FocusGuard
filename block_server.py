"""
Local block page server.

During an active focus session, blocked sites are redirected to 127.0.0.1
via the hosts file.  Two servers run in parallel:

  • port 80  — serves the block page for HTTP traffic
  • port 443 — serves the same page over TLS for HTTPS traffic

TLS architecture:
  _CERT_PEM / _KEY_PEM  — CA certificate (installed into Windows Trusted Root
                           store by installer.py so browsers trust our CA).
  _LEAF_CERT_PEM / _LEAF_KEY_PEM — leaf certificate signed by the CA, with
                           SANs covering every predefined blocked domain.
                           This is what the HTTPS server presents to browsers.
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

# Exported: installer.py imports _CERT_PEM to add the CA to Windows Trusted Root store.
_CERT_PEM = """\
-----BEGIN CERTIFICATE-----
MIIDYTCCAkmgAwIBAgIULeX9FIkeF8Rj3a/1yGXccuXDJkUwDQYJKoZIhvcNAQEL
BQAwODELMAkGA1UEBhMCTkcxEDAOBgNVBAoMB05BQ09NRVMxFzAVBgNVBAMMDkZv
Y3VzIEd1YXJkIENBMB4XDTI2MDUyOTEzMTYzNloXDTM2MDUyNjEzMTYzNlowODEL
MAkGA1UEBhMCTkcxEDAOBgNVBAoMB05BQ09NRVMxFzAVBgNVBAMMDkZvY3VzIEd1
YXJkIENBMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAxHs4WvrrdnKT
lOPWt89Ywa6W+yRYV+bSng3gQpCEhWMDiq8+AM/0aqjYvlwcnojnLKc7ivJZL5Nd
KPxODzSDadZ+xBaOMQ0gmQFYqNwXTpW6VtsaCAVnvhGeROZT/REFdbS3unh3Olxp
psXR486idKgrWavJpG5BBxKyxdU5xEBaFWAB/zNcREIJv8TJZORa7IEpjk8uS0bT
om+HUu5X/zrWjf/pv3UkjOXaKiRKu8hOq+rmj2Uzn1un0YEYi8JGsgxvMVcd34Qh
EzM7I21jrrxjnU7F1y9O/KLVr5nb6hXH+pfmgtGgCEPFF+Udg76G9TowcQhgmPcu
YLUFCLJ2JwIDAQABo2MwYTAPBgNVHRMBAf8EBTADAQH/MA4GA1UdDwEB/wQEAwIB
BjAdBgNVHQ4EFgQUMUdbl9Y3q91aRE332sO70dUuBNMwHwYDVR0jBBgwFoAUMUdb
l9Y3q91aRE332sO70dUuBNMwDQYJKoZIhvcNAQELBQADggEBACKAsPXgEf8KMrDX
quiRDxCv+xQG1QMKWDAB9DDyPbUc3ajpDZxvvmclXPThEzOLKsmzNTJVNBNBILED
Bvy96gvaW0z+3zCS2oeBE8Nk+yiv4SzsCjzdBg5G1LgE0H4fd58UP/MfaCLfQqns
QqWJT9hPpbLfuho6XbXX2BXianow1eXQXCE6neD5N6ir2KOCO/BBxQXbXAsIAWcx
RzUc7ge/wG9mn8OiK649JIlzBfkYp4qnEj5Dq3RRXEWzAJO219FLoDnYMwvVuK8M
koOXKLa7EAIR6O0M4B4OmewJ8YGkGOaLGpkugDnKCn2cLzZUuwTf1s2RyL688I4j
f3kg7s0=
-----END CERTIFICATE-----
"""

# CA private key — kept here to allow future leaf cert regeneration if needed.
_KEY_PEM = """\
-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDEezha+ut2cpOU
49a3z1jBrpb7JFhX5tKeDeBCkISFYwOKrz4Az/RqqNi+XByeiOcspzuK8lkvk10o
/E4PNINp1n7EFo4xDSCZAVio3BdOlbpW2xoIBWe+EZ5E5lP9EQV1tLe6eHc6XGmm
xdHjzqJ0qCtZq8mkbkEHErLF1TnEQFoVYAH/M1xEQgm/xMlk5FrsgSmOTy5LRtOi
b4dS7lf/OtaN/+m/dSSM5doqJEq7yE6r6uaPZTOfW6fRgRiLwkayDG8xVx3fhCET
MzsjbWOuvGOdTsXXL078otWvmdvqFcf6l+aC0aAIQ8UX5R2Dvob1OjBxCGCY9y5g
tQUIsnYnAgMBAAECggEAVPX/aYAFH4PuAzz+VR9I/v9y9AhEV0ZNnuDbL410cIVf
O7IJeqpxw0ld5/rGuVrzs+Bgo/Wl0SfE6fsn+fU4OiTxTfN+6wEFLoRhhSsevPGL
0REPUZacxJizupFqkgyxMrPBmtWKoObjHKV/3CU3JICvtifNmte+MMPKIDfSseRr
JvHV3oEQYoFu4gcQ15ddGsRsBXHOGAjVMFMZzFHlrQo+JPBRDdeZPEpL0TYI2uKs
lI/B+unbM2+9AeSsbIbfSusmddF9BVh5wJFZpj3YQYeeI9JnUJyRrhWr75y+3Q6V
XoupMdhMLvjuUzVwPneufR5XSVDbwrQfb7FLxekqyQKBgQD0IG8/nfHtzlz0JWzv
Wi4ZwCh+WYmvWdrt4zl9wC/O8hDBEf2279OsXHrsgMObpZU7e82EmFVvtpQGUmzc
6pZh3k18rPk+gzOJTfkYlb8pymL7M9TCneaGVOxQ0TmsLndrasz58L/0PafzNLmS
MBrKnOIZ8bdvMEVoC+XjLhPTAwKBgQDOCZBkSLZTaLwWP8htoAGrO/XjtjkQwQed
XDOR9P7IFCFD/LaraBwwT4iDFsiYdWO+QMKsK0twgB5NmxFSP2Pr0ik5D1H8Yv6/
ooKuUsAr0s6u/udVqcnVZT3LmSn9giutduVnUnNlI1pFK+adWXCUWLvsHYSx9jIv
OtTKwqCVDQKBgQDdMRYbWgx+H2Bxhgdxxw/GHSmTcaUi0BNhP2Qz4BJxOzqa9KYh
PqNXpGNsLi8Ns7XHM6E+5pdipNbx83TXpWWkPzuOH1ulnFLxsUhlUijmwI12dbvs
qgzY4dFMWIYcz+070oTuYYhK0CKAZeFN53Ae7I6gWzaM8/uvDji44mLr6QKBgBZe
TXHFvx2hEkJsHEtigqvfb5uQLfPWsQfxeZvP+FUqck4aQo6rV9wa1lw8/fwnSnPe
PgRJEwCcuC1+t0uxnBx/DYCnXCRFbxjJAN0CGODpGw0+mUjgjQwA2MugzkE6f5lu
fgtQlTyWsPcvg/LzQdipJYXF0qErdFlSTsXQiXSFAoGALpSp8Arzl7S8KntxYjYQ
7QTG2r+oLUzxap1Wym3cFmnWmwYv83+0g0LUHugl91r/AOmPCl3HAmL98761v+Wb
A+KwajT1z9uqBBI9hDjgyrOKwbf0p8ICDgnNt9G+tK2vSLKvV25/+GivESu26iwQ
XjXf2r7ZAgl/2B38rPnUOX8=
-----END PRIVATE KEY-----
"""


_LEAF_CERT_PEM = """\
-----BEGIN CERTIFICATE-----
MIILHDCCCgSgAwIBAgIUI0J1s6bMIi1ixG7xylD9MbYjNlowDQYJKoZIhvcNAQEL
BQAwODELMAkGA1UEBhMCTkcxEDAOBgNVBAoMB05BQ09NRVMxFzAVBgNVBAMMDkZv
Y3VzIEd1YXJkIENBMB4XDTI2MDUyOTEzMTYzNloXDTM2MDUyNjEzMTYzNlowQDEL
MAkGA1UEBhMCTkcxEDAOBgNVBAoMB05BQ09NRVMxHzAdBgNVBAMMFkZvY3VzIEd1
YXJkIEJsb2NrIFBhZ2UwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQDC
3Czq4HnC5o8HCKmPrMzVTRejh5J7MH8n/Uvq18Iceu7MiI+iGyDlkG2xwN30miCr
WZBqTbpH2f0ux1jf1AhYalnsDU9ZaaJX4Vs9x5g5cRfVxn7yYzIjCr5nH48XHsC7
Zi9fY6fH1PLUOvu4xK47yyWQ+r2G+rhU4kB79YORHTW33NY/r15MoaZSqJTB4eJj
qO9rIsOMBcs/Uz9QtcVAVL1TVUoLIJG3JQx1FezKg0x2uzbEFh1XRgRkyPEhJLWL
IDdYWlSkhD7LdRYLtOs4Ftg4TI4wWbmyL4HTMBvGxxutXqfbaNoo0lFb48ILfC9/
41eUb0J4NwGp42nctE7PAgMBAAGjgggUMIIIEDCCB5kGA1UdEQEB/wSCB40wggeJ
ggt5b3V0dWJlLmNvbYIPd3d3LnlvdXR1YmUuY29tggxmYWNlYm9vay5jb22CEHd3
dy5mYWNlYm9vay5jb22CDWluc3RhZ3JhbS5jb22CEXd3dy5pbnN0YWdyYW0uY29t
ggt0d2l0dGVyLmNvbYIPd3d3LnR3aXR0ZXIuY29tggV4LmNvbYIJd3d3LnguY29t
ggp0aWt0b2suY29tgg53d3cudGlrdG9rLmNvbYIMc25hcGNoYXQuY29tghB3d3cu
c25hcGNoYXQuY29tgg1waW50ZXJlc3QuY29tghF3d3cucGludGVyZXN0LmNvbYIM
bGlua2VkaW4uY29tghB3d3cubGlua2VkaW4uY29tggp0dW1ibHIuY29tgg53d3cu
dHVtYmxyLmNvbYIKcmVkZGl0LmNvbYIOd3d3LnJlZGRpdC5jb22CC3RocmVhZHMu
bmV0gg93d3cudGhyZWFkcy5uZXSCDW1lc3Nlbmdlci5jb22CEXd3dy5tZXNzZW5n
ZXIuY29tggtuZXRmbGl4LmNvbYIPd3d3Lm5ldGZsaXguY29tggl0d2l0Y2gudHaC
DXd3dy50d2l0Y2gudHaCCGh1bHUuY29tggx3d3cuaHVsdS5jb22CD2RhaWx5bW90
aW9uLmNvbYITd3d3LmRhaWx5bW90aW9uLmNvbYIJdmltZW8uY29tgg13d3cudmlt
ZW8uY29tgg5wcmltZXZpZGVvLmNvbYISd3d3LnByaW1ldmlkZW8uY29tgg5kaXNu
ZXlwbHVzLmNvbYISd3d3LmRpc25leXBsdXMuY29tggdtYXguY29tggt3d3cubWF4
LmNvbYIPY3J1bmNoeXJvbGwuY29tghN3d3cuY3J1bmNoeXJvbGwuY29tggpyb2Js
b3guY29tgg53d3cucm9ibG94LmNvbYISc3RlYW1jb21tdW5pdHkuY29tghZ3d3cu
c3RlYW1jb21tdW5pdHkuY29tghZzdG9yZS5zdGVhbXBvd2VyZWQuY29tgg1lcGlj
Z2FtZXMuY29tghF3d3cuZXBpY2dhbWVzLmNvbYIMbWluaWNsaXAuY29tghB3d3cu
bWluaWNsaXAuY29tgg5rb25ncmVnYXRlLmNvbYISd3d3LmtvbmdyZWdhdGUuY29t
gghwb2tpLmNvbYIMd3d3LnBva2kuY29tggxnYW1lc3BvdC5jb22CEHd3dy5nYW1l
c3BvdC5jb22CB2lnbi5jb22CC3d3dy5pZ24uY29tggdjbm4uY29tggt3d3cuY25u
LmNvbYIHYmJjLmNvbYILd3d3LmJiYy5jb22CC255dGltZXMuY29tgg93d3cubnl0
aW1lcy5jb22CC2ZveG5ld3MuY29tgg93d3cuZm94bmV3cy5jb22CCW1zbmJjLmNv
bYINd3d3Lm1zbmJjLmNvbYIMaHVmZnBvc3QuY29tghB3d3cuaHVmZnBvc3QuY29t
gg90aGVndWFyZGlhbi5jb22CE3d3dy50aGVndWFyZGlhbi5jb22CDGJ1enpmZWVk
LmNvbYIQd3d3LmJ1enpmZWVkLmNvbYISd2FzaGluZ3RvbnBvc3QuY29tghZ3d3cu
d2FzaGluZ3RvbnBvc3QuY29tggphbWF6b24uY29tgg53d3cuYW1hem9uLmNvbYII
ZWJheS5jb22CDHd3dy5lYmF5LmNvbYIOYWxpZXhwcmVzcy5jb22CEnd3dy5hbGll
eHByZXNzLmNvbYIIZXRzeS5jb22CDHd3dy5ldHN5LmNvbYILd2FsbWFydC5jb22C
D3d3dy53YWxtYXJ0LmNvbYIKdGFyZ2V0LmNvbYIOd3d3LnRhcmdldC5jb22CCXNo
ZWluLmNvbYINd3d3LnNoZWluLmNvbYIId2lzaC5jb22CDHd3dy53aXNoLmNvbYIL
c3BvdGlmeS5jb22CD3d3dy5zcG90aWZ5LmNvbYIQb3Blbi5zcG90aWZ5LmNvbYIP
bXVzaWMuYXBwbGUuY29tgg5zb3VuZGNsb3VkLmNvbYISd3d3LnNvdW5kY2xvdWQu
Y29tggpkZWV6ZXIuY29tgg53d3cuZGVlemVyLmNvbYILcGFuZG9yYS5jb22CD3d3
dy5wYW5kb3JhLmNvbYIJdGlkYWwuY29tgg13d3cudGlkYWwuY29tggtkaXNjb3Jk
LmNvbYIPd3d3LmRpc2NvcmQuY29tgglzbGFjay5jb22CDXd3dy5zbGFjay5jb22C
DWFwcC5zbGFjay5jb22CCXNreXBlLmNvbYINd3d3LnNreXBlLmNvbYITdGVhbXMu
bWljcm9zb2Z0LmNvbYIQd2ViLndoYXRzYXBwLmNvbYIQd2ViLnRlbGVncmFtLm9y
Z4ILcG9ybmh1Yi5jb22CD3d3dy5wb3JuaHViLmNvbYILeHZpZGVvcy5jb22CD3d3
dy54dmlkZW9zLmNvbYIIeG54eC5jb22CDHd3dy54bnh4LmNvbYILcmVkdHViZS5j
b22CD3d3dy5yZWR0dWJlLmNvbYIMb25seWZhbnMuY29tghB3d3cub25seWZhbnMu
Y29thwR/AAABMA4GA1UdDwEB/wQEAwIFoDATBgNVHSUEDDAKBggrBgEFBQcDATAM
BgNVHRMBAf8EAjAAMB0GA1UdDgQWBBRmYXBZqFgKxoVTBwujhr3w93kpODAfBgNV
HSMEGDAWgBQxR1uX1jer3VpETffaw7vR1S4E0zANBgkqhkiG9w0BAQsFAAOCAQEA
INI0i4Zr3uGJr45wOtwjVYiJcjJXJvQL9zvHJCMG8ROQAJqNKei3HVBihc6Q+jtV
ykea09/p3dghe8IK9CGE2H5lrmmczCUndVj4nuByzPdVcI4w8m32DlAu4xmNNh5b
UhW3qhL3dLj0/7WXBEwDUGvTtqrzJR72JGcBw60cOgz0tCCaUg4NPmvUEuWRLCsJ
qdqI+911Ett/XaT+vDAMCCIwQLY39KgnUM5a3CxUV8Z+xtl4c5PtFC6BqMbA+FG+
QeZVguWhy6+hGb6PSPzCkE775rEhTquJ7TZ3TDX8vgnpvV5dtZMKCiwLv0mHO1n/
9K+9ezoPQwfyjNrV9wv1SA==
-----END CERTIFICATE-----
"""

_LEAF_KEY_PEM = """\
-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDC3Czq4HnC5o8H
CKmPrMzVTRejh5J7MH8n/Uvq18Iceu7MiI+iGyDlkG2xwN30miCrWZBqTbpH2f0u
x1jf1AhYalnsDU9ZaaJX4Vs9x5g5cRfVxn7yYzIjCr5nH48XHsC7Zi9fY6fH1PLU
Ovu4xK47yyWQ+r2G+rhU4kB79YORHTW33NY/r15MoaZSqJTB4eJjqO9rIsOMBcs/
Uz9QtcVAVL1TVUoLIJG3JQx1FezKg0x2uzbEFh1XRgRkyPEhJLWLIDdYWlSkhD7L
dRYLtOs4Ftg4TI4wWbmyL4HTMBvGxxutXqfbaNoo0lFb48ILfC9/41eUb0J4NwGp
42nctE7PAgMBAAECggEAQZhXoIuHQZZWcHI4ji6H14f3nKt/ImwNaftJCpmt9ONn
LsALxfCm7tBjNNKthPE7bSMdy8M1oYlewtgFcXeRhZ3rflxuqTU3mqi4i7/8XN3W
vbZvto2w633q4ZEMnKZUD+GSseQ8rzbetZXTdfvzgRpeH4NguKb+1UhCl9fqfbcG
n5Tfx8/ectR9LlUKUO6Kj6piVzGqRWEyrv56Y2ajSX3UAmpKPzF+fD7DcI+3HWYF
qbXEsiYu8Y1s8MApEu/hD2yXM2ZzIgSWeUzn533GZLmyYrjWLC3g7HitYEoHVqHU
PixsRgHtMIJ/vWCCPC3bkHnBHPQbQNMjj+FriavsXQKBgQDjpybU+Zlmsd9e0Jmo
BqPDCIFZo7/QCZ/z8R3rRZLTuldnvWWoDT1udHaKUMwCx0tzx6wIJz+yUAU8Vi6/
7KQbovwTRVKt5kY2wDBqYaqNI0v+ULPnwFEpf2Q20uZk81MTnfxDWQ3dP9gO+f5U
4PDTMAzz7J98OZu07PfyqRb2MwKBgQDbH7EQNLOOnZ64DnyHI639flCuKGUw8KWm
eVUZ6MPvIyVhI++FSiU8x9EBM3KMjCSTz9Rf3dCtye2F/PChwxSQGRQ4CH9hWKLC
Z4PZ//imT1JQaqAPe2Ml63grhp80YOup4fJ/H6TxeaK+0wgWB7bQgP/lPujal8RD
Tz7YucqQ9QKBgG68lTgN/d+lcFlHsSa5rBkn3vvCmoBQ3jykMgCKxEQ3pWKyD2vy
nMpI3oyjhslnNj2oh/cjWGmdYR6bcXwsWRuUaXfaRcCPfeIOFL76qSKkY8fea9S0
iQZdkFrWtfmvHt8w/0+nVwYjky6dzmhtTtf7zKEundmokCQvDOE9/QxfAoGAVDWv
tEysnKhScOWQUdcSbJL4qpV3ngE9h+alH9nmQqa9HMHUsOK3wM4BsnZ1FTJedDew
pE74fXFWyOFWELSJ2H7q2EXbvit0EUX60/KdOjzNo332mTyP8+i0O/X2hQiiSJ0+
tkARAYP/WVp8hwrb5PFOZmlwz2D32e5AdsWf5WkCgYEAkXFSO49R1OpJJEkIqNQG
0BIMr/x9d6bRmDKd0ao1Ej78szG3KMUZp140eUpgirUfaICL3ztf91sBMbKhFu34
mn46P8IgFFSpbz0kbKpZWGnKosf5QVDGrItTVynWoFN4EksDWXPs+xt9CtdWfONo
9ItjmMgxlsBAkOc78HdGz40=
-----END PRIVATE KEY-----
"""


def _make_ssl_context():
    """Build an SSLContext using the leaf cert (signed by our CA)."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    # ssl.SSLContext.load_cert_chain() requires file paths, so write to temp
    # files then delete them immediately after loading into the context.
    tmp_cert = tempfile.NamedTemporaryFile(suffix=".pem", delete=False)
    tmp_key  = tempfile.NamedTemporaryFile(suffix=".pem", delete=False)
    try:
        tmp_cert.write(_LEAF_CERT_PEM.encode())
        tmp_cert.close()
        tmp_key.write(_LEAF_KEY_PEM.encode())
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
  <title>Blocked — Focus Guard</title>
  <style>
    *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }

    html, body {
      min-height: 100%;
      background: #07101f;
      font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
      -webkit-font-smoothing: antialiased;
    }

    .card {
      background: #0d1929;
      border: 1px solid #162035;
      border-top: 3px solid #3b82f6;
      border-radius: 14px;
      padding: 44px 52px 36px;
      width: 100%;
      max-width: 460px;
      animation: rise 0.35s cubic-bezier(0.16, 1, 0.3, 1) both;
    }

    @keyframes rise {
      from { opacity: 0; transform: translateY(18px); }
      to   { opacity: 1; transform: translateY(0); }
    }

    /* ── Brand ── */
    .brand {
      display: flex;
      align-items: center;
      gap: 9px;
      margin-bottom: 36px;
    }

    .brand-mark {
      width: 30px;
      height: 30px;
      background: #3b82f6;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }

    .brand-mark svg {
      width: 16px;
      height: 16px;
      fill: #fff;
    }

    .brand-name {
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 1.8px;
      text-transform: uppercase;
      color: #3b82f6;
    }

    /* ── Status tag ── */
    .tag {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      background: rgba(239,68,68,0.08);
      border: 1px solid rgba(239,68,68,0.18);
      color: #f87171;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 1.4px;
      text-transform: uppercase;
      padding: 4px 10px;
      border-radius: 5px;
      margin-bottom: 18px;
    }

    .tag-dot {
      width: 5px;
      height: 5px;
      background: #ef4444;
      border-radius: 50%;
    }

    /* ── Domain ── */
    .domain {
      font-size: 26px;
      font-weight: 700;
      color: #f1f5f9;
      letter-spacing: -0.4px;
      margin-bottom: 8px;
      word-break: break-all;
    }

    .reason {
      font-size: 14px;
      color: #475569;
      line-height: 1.5;
      margin-bottom: 32px;
    }

    /* ── Divider ── */
    .rule {
      height: 1px;
      background: #162035;
      margin-bottom: 20px;
    }

    /* ── Session row ── */
    .session-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .session-label {
      font-size: 13px;
      color: #334155;
    }

    .session-live {
      display: flex;
      align-items: center;
      gap: 7px;
      font-size: 12px;
      font-weight: 600;
      color: #22c55e;
    }

    .live-dot {
      width: 7px;
      height: 7px;
      background: #22c55e;
      border-radius: 50%;
      animation: blink 2s ease-in-out infinite;
    }

    @keyframes blink {
      0%, 100% { opacity: 1; }
      50%       { opacity: 0.3; }
    }

    /* ── Footer ── */
    .footer {
      margin-top: 28px;
      font-size: 11px;
      color: #1e293b;
      text-align: center;
      letter-spacing: 0.3px;
    }
  </style>
</head>
<body>
  <div class="card">

    <div class="brand">
      <div class="brand-mark">
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 2L4 6v6c0 5.25 3.4 10.15 8 11.35C16.6 22.15 20 17.25 20 12V6l-8-4zm-1 13l-3-3 1.4-1.4 1.6 1.6 4.2-4.2L16.6 9.4 11 15z"/>
        </svg>
      </div>
      <span class="brand-name">Focus Guard</span>
    </div>

    <div class="tag"><span class="tag-dot"></span>Blocked</div>

    <div class="domain">BLOCKED_SITE</div>
    <p class="reason">This site is off-limits during your focus session.</p>

    <div class="rule"></div>

    <div class="session-row">
      <span class="session-label">Focus session</span>
      <span class="session-live"><span class="live-dot"></span>Active</span>
    </div>

    <div class="footer">NACOMES &nbsp;·&nbsp; The Polytechnic, Ibadan &nbsp;·&nbsp; 2026</div>

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

def _ensure_ca_trusted():
    """Install the Focus Guard CA cert into Windows Trusted Root if needed.

    Runs on every session start so HTTPS blocking works even when the app
    was not installed via the normal installer flow (e.g. running from source).
    Requires admin rights — the app already runs elevated.
    """
    import tempfile, os as _os, subprocess as _sp
    # Remove any old cert with the previous CN to avoid conflicts
    _sp.run(['certutil', '-delstore', 'Root', 'focusguard.local'],
            capture_output=True, check=False, timeout=10)
    tmp = tempfile.NamedTemporaryFile(suffix='.cer', delete=False)
    try:
        tmp.write(_CERT_PEM.encode())
        tmp.close()
        _sp.run(['certutil', '-addstore', '-f', 'Root', tmp.name],
                capture_output=True, check=False, timeout=20)
    finally:
        try:
            _os.unlink(tmp.name)
        except OSError:
            pass


def start_block_server():
    """Start block-page servers on 127.0.0.1:80 (HTTP) and :443 (HTTPS)."""
    global _http_server, _https_server, _http_thread, _https_thread

    if _http_server is not None:
        return

    _ensure_ca_trusted()

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
