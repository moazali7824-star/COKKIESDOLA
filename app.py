"""
One-time Cookie Dispenser
-------------------------
Admin uploads a pool of cookies. Each user takes ONE cookie; the moment it is
handed out it is deleted from the pool, so no one else can ever get that same
cookie. Built for Railway (binds to $PORT). Storage = SQLite with an atomic pop
(BEGIN IMMEDIATE) so two simultaneous requests can never grab the same entry.

Change ADMIN_PASSWORD / USER_KEY below (or set them as Railway env vars).
For data that survives redeploys, mount a Railway Volume and set
COOKIE_DB_PATH=/data/cookies.db  (see README).
"""
import os, time, sqlite3, secrets
from flask import (Flask, request, jsonify, session, redirect,
                   render_template_string, Response)

# ---- config (hardcoded defaults; override with Railway env vars) ------------
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Moaz!!admin00")   # admin panel password
USER_KEY       = os.environ.get("USER_KEY", "green2026")             # "" = open to anyone; else users must enter this
SECRET_KEY     = os.environ.get("SECRET_KEY", "cookie-dispenser-moaz-secret-2026")
DB_PATH        = os.environ.get("COOKIE_DB_PATH",
                                os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cookies.db"))
# ----------------------------------------------------------------------------

app = Flask(__name__)
app.secret_key = SECRET_KEY


def db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=15)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=8000")
    return con


def init_db():
    con = db()
    con.execute("""CREATE TABLE IF NOT EXISTS cookies(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT NOT NULL,
        added_at INTEGER NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS taken(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        at INTEGER NOT NULL,
        ip TEXT)""")
    con.commit(); con.close()


init_db()


def client_ip():
    xff = request.headers.get("X-Forwarded-For", "")
    return (xff.split(",")[0].strip() if xff else request.remote_addr) or "?"


def split_cookies(text, mode):
    """Split a bulk paste into individual cookie entries."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []
    if mode == "line":
        parts = [ln.strip() for ln in text.split("\n")]
    elif mode == "dashes":
        import re
        parts = re.split(r"(?m)^\s*-{3,}\s*$", text)
    else:  # "blank" (default): entries separated by a blank line
        import re
        parts = re.split(r"\n\s*\n", text)
    return [p.strip() for p in parts if p and p.strip()]


def pool_count():
    con = db()
    n = con.execute("SELECT COUNT(*) FROM cookies").fetchone()[0]
    con.close()
    return n


def take_one(ip):
    """Atomically remove and return ONE cookie. None if the pool is empty."""
    con = db()
    try:
        con.isolation_level = None
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT id, content FROM cookies ORDER BY id LIMIT 1").fetchone()
        if not row:
            con.execute("COMMIT")
            return None
        con.execute("DELETE FROM cookies WHERE id=?", (row[0],))
        con.execute("INSERT INTO taken(at, ip) VALUES(?,?)", (int(time.time()), ip))
        con.execute("COMMIT")
        return row[1]
    except Exception:
        try: con.execute("ROLLBACK")
        except Exception: pass
        raise
    finally:
        con.close()


# ============================ USER SIDE =====================================
USER_HTML = r"""
<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Get your cookie</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@500;600;700;800&display=swap" rel="stylesheet">
<style>
:root{--bg:#060a09;--bg2:#0a1411;--card:rgba(17,26,22,.72);--line:rgba(120,165,140,.16);
--green:#2fe86a;--green2:#12b765;--ink:#eaf3ee;--mut:#8fa69a;--gold:#f5c542}
*{box-sizing:border-box}html,body{height:100%}
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:28px 16px;
color:var(--ink);background:var(--bg);overflow-x:hidden;position:relative;
font-family:'Manrope',system-ui,-apple-system,'Segoe UI',Roboto,sans-serif}
.bg{position:fixed;inset:0;z-index:0;overflow:hidden;pointer-events:none}
.bg:before,.bg:after{content:"";position:absolute;width:540px;height:540px;border-radius:50%;filter:blur(90px);opacity:.5}
.bg:before{background:radial-gradient(circle,#1db86a,transparent 60%);top:-180px;left:-120px;animation:float1 14s ease-in-out infinite}
.bg:after{background:radial-gradient(circle,#0e7f6a,transparent 60%);bottom:-200px;right:-140px;animation:float2 16s ease-in-out infinite}
@keyframes float1{50%{transform:translate(80px,60px) scale(1.1)}}
@keyframes float2{50%{transform:translate(-70px,-50px) scale(1.15)}}
.wrap{position:relative;z-index:1;width:100%;max-width:460px}
.brand{display:flex;align-items:center;justify-content:center;gap:9px;margin-bottom:16px}
.brand b{font-weight:800;font-size:18px;letter-spacing:.2px}
.brand .dot{color:var(--green)}
.card{background:var(--card);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);
border:1px solid var(--line);border-radius:24px;padding:30px 26px;
box-shadow:0 30px 80px rgba(0,0,0,.55),inset 0 1px 0 rgba(255,255,255,.04)}
.cookie{width:84px;height:84px;display:block;margin:0 auto 14px;filter:drop-shadow(0 10px 24px rgba(47,232,106,.35));animation:bob 4s ease-in-out infinite}
@keyframes bob{50%{transform:translateY(-7px) rotate(-4deg)}}
h1{font-size:23px;font-weight:800;margin:0 0 4px;text-align:center;letter-spacing:-.3px}
.sub{color:var(--mut);font-size:13.5px;text-align:center;margin:0 auto 18px;max-width:330px;line-height:1.55}
.chips{display:flex;gap:7px;justify-content:center;flex-wrap:wrap;margin-bottom:22px}
.chip{font-size:11.5px;font-weight:600;color:#bfe9cf;background:rgba(47,232,106,.1);border:1px solid rgba(47,232,106,.22);
border-radius:999px;padding:5px 11px;display:inline-flex;align-items:center;gap:5px}
input{width:100%;background:rgba(6,14,11,.7);border:1px solid var(--line);color:var(--ink);border-radius:13px;
padding:13px 14px;font-size:14px;font-family:inherit;margin-bottom:12px;outline:none;transition:border-color .15s,box-shadow .15s}
input:focus{border-color:var(--green);box-shadow:0 0 0 3px rgba(47,232,106,.14)}
.btn{position:relative;width:100%;border:0;border-radius:15px;padding:16px;font-family:inherit;font-weight:800;font-size:15.5px;
cursor:pointer;color:#04231a;background:linear-gradient(180deg,#43f07f,var(--green2));overflow:hidden;
box-shadow:0 12px 30px rgba(47,232,106,.3);transition:transform .12s,box-shadow .2s,opacity .2s}
.btn:hover{transform:translateY(-1px);box-shadow:0 16px 38px rgba(47,232,106,.42)}
.btn:active{transform:translateY(0)}
.btn:disabled{opacity:.5;cursor:default;transform:none;box-shadow:none}
.btn .shine{position:absolute;top:0;left:-60%;width:40%;height:100%;background:linear-gradient(100deg,transparent,rgba(255,255,255,.45),transparent);
transform:skewX(-20deg);animation:shine 3.4s ease-in-out infinite}
@keyframes shine{0%,60%{left:-60%}100%{left:130%}}
.btn.loading .lbl{opacity:0}
.spin{display:none;position:absolute;inset:0;margin:auto;width:20px;height:20px;border:2.5px solid rgba(4,35,26,.3);
border-top-color:#04231a;border-radius:50%;animation:spin .7s linear infinite}
.btn.loading .spin{display:block}
@keyframes spin{to{transform:rotate(360deg)}}
.steps{display:flex;gap:6px;margin:20px 0 2px;justify-content:space-between}
.step{flex:1;text-align:center;color:var(--mut);font-size:11px;line-height:1.4}
.step .n{display:block;width:26px;height:26px;line-height:26px;margin:0 auto 6px;border-radius:50%;
background:rgba(47,232,106,.12);border:1px solid rgba(47,232,106,.25);color:var(--green);font-weight:800;font-size:12px}
.msg{margin-top:16px;font-size:13.5px;line-height:1.55;text-align:center;min-height:18px;font-weight:600}
.ok{color:var(--green)}.err{color:#ff7a7a}.mut{color:var(--mut)}
pre{white-space:pre-wrap;word-break:break-all;background:rgba(6,14,11,.8);border:1px solid var(--line);
border-radius:13px;padding:13px;font-size:12px;line-height:1.5;color:#cfe7d8;max-height:200px;overflow:auto;
margin-top:14px;display:none;font-family:ui-monospace,Consolas,monospace}
.reveal{animation:pop .3s ease}@keyframes pop{from{opacity:0;transform:translateY(8px)}}
.row{display:flex;gap:9px;margin-top:11px}
.row .mini{flex:1;border:1px solid var(--line);background:rgba(23,36,29,.8);color:var(--ink);border-radius:12px;
padding:11px;font-family:inherit;font-weight:700;font-size:13px;cursor:pointer;transition:border-color .15s}
.row .mini:hover{border-color:var(--green)}
.foot{margin-top:16px;text-align:center;color:var(--mut);font-size:11.5px;font-weight:600}
.empty .cookie{filter:grayscale(1) opacity(.5);animation:none}
@media(max-width:380px){.card{padding:24px 18px}h1{font-size:21px}}
</style></head><body><div class="bg"></div>
<div class="wrap">
  <div class="brand">
    <svg width="22" height="22" viewBox="0 0 24 24" fill="#2fe86a"><path d="M12 2a10 10 0 1 0 10 10c0-.5 0-1-.1-1.5a3 3 0 0 1-4.4-3.4A3 3 0 0 1 13 3.1 10 10 0 0 0 12 2z"/></svg>
    <b>Cookie<span class="dot">Vault</span></b>
  </div>
  <div class="card" id="card">
    <svg class="cookie" viewBox="0 0 24 24" fill="#2fe86a"><path d="M12 2a10 10 0 1 0 10 10c0-.5 0-1-.1-1.5a3 3 0 0 1-4.4-3.4A3 3 0 0 1 13 3.1 10 10 0 0 0 12 2zM8.5 9A1.5 1.5 0 1 1 7 10.5 1.5 1.5 0 0 1 8.5 9zm7 5A1.5 1.5 0 1 1 14 15.5 1.5 1.5 0 0 1 15.5 14zm-6 1A1 1 0 1 1 8.5 16 1 1 0 0 1 9.5 15z"/></svg>
    <h1>Claim your cookie</h1>
    <div class="sub">One click gives you a single cookie — and it's instantly removed from the pool, so it's yours alone.</div>
    <div class="chips"><span class="chip">✓ One-time</span><span class="chip">🔒 Private</span><span class="chip">⚡ Instant</span></div>

    {% if need_key %}
    <input id="key" type="text" placeholder="Enter your access key" autocomplete="off" spellcheck="false">
    {% endif %}
    <button class="btn" id="go"><span class="lbl">Get my cookie</span><span class="shine"></span><span class="spin"></span></button>

    <div class="msg" id="msg"></div>
    <pre id="out"></pre>
    <div class="row" id="actions" style="display:none">
      <button class="mini" id="copy">📋 Copy</button>
      <button class="mini" id="dl">⬇ Download .txt</button>
    </div>

    <div class="steps">
      <div class="step"><span class="n">1</span>Click the button</div>
      <div class="step"><span class="n">2</span>Get your cookie</div>
      <div class="step"><span class="n">3</span>Removed for good</div>
    </div>
    <div class="foot" id="left"></div>
  </div>
</div>
<script>
const needKey = {{ 'true' if need_key else 'false' }};
const go=document.getElementById('go'), msg=document.getElementById('msg'),
      out=document.getElementById('out'), actions=document.getElementById('actions'),
      left=document.getElementById('left'), card=document.getElementById('card');
let lastContent="";
function setMsg(t,c){msg.textContent=t;msg.className="msg "+(c||"");}
function setLbl(t){const l=go.querySelector('.lbl'); if(l) l.textContent=t;}
async function take(){
  go.disabled=true; go.classList.add('loading'); setMsg("",""); out.style.display="none"; actions.style.display="none";
  const body={}; if(needKey){const k=document.getElementById('key'); body.key=k?k.value.trim():"";}
  try{
    const r=await fetch('/api/take',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const d=await r.json();
    go.classList.remove('loading');
    if(d.ok){
      lastContent=d.content;
      setMsg("✓ Delivered — this cookie is now yours alone.","ok");
      out.textContent=d.content; out.style.display="block"; out.classList.remove('reveal'); void out.offsetWidth; out.classList.add('reveal');
      actions.style.display="flex";
      if(typeof d.remaining==="number") left.textContent=d.remaining+" cookies left in the pool";
      autoDownload();
    } else if(d.empty){
      setMsg("😵  Oops — you missed it! All cookies have been claimed.","err");
      setLbl("All claimed"); go.disabled=true; card.classList.add('empty');
      left.textContent="0 left in the pool"; out.style.display="none"; actions.style.display="none"; return;
    } else if(d.badkey){ setMsg("Wrong access key — check and try again.","err"); }
    else { setMsg(d.error||"Something went wrong. Try again.","err"); }
  }catch(e){ go.classList.remove('loading'); setMsg("Network error. Try again.","err"); }
  go.disabled=false;
}
function autoDownload(){
  const blob=new Blob([lastContent],{type:'text/plain'});
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob);
  a.download='cookie_'+Date.now()+'.txt'; document.body.appendChild(a); a.click(); a.remove();
}
go.addEventListener('click',take);
document.getElementById('copy').addEventListener('click',()=>{navigator.clipboard.writeText(lastContent);setMsg("Copied ✓","ok");});
document.getElementById('dl').addEventListener('click',autoDownload);
</script></body></html>
"""


@app.get("/")
def user_page():
    return render_template_string(USER_HTML, need_key=bool(USER_KEY))


@app.post("/api/take")
def api_take():
    data = request.get_json(silent=True) or {}
    if USER_KEY and (data.get("key", "") != USER_KEY):
        return jsonify(ok=False, badkey=True)
    content = take_one(client_ip())
    if content is None:
        return jsonify(ok=False, empty=True)
    return jsonify(ok=True, content=content, remaining=pool_count())


# ============================ ADMIN SIDE ====================================
ADMIN_HTML = r"""
<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Admin · Cookie pool</title>
<style>
:root{--bg:#0b0f0d;--card:#121a16;--line:#1f2d25;--green:#2fe86a;--green2:#16a34a;--ink:#e8f1ec;--mut:#9fb0a8}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(1200px 600px at 50% -10%,#10231a,var(--bg));
color:var(--ink);font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;padding:24px 16px}
.wrap{max-width:720px;margin:0 auto}
.top{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px}
h1{font-size:19px;margin:0}
.pill{background:#17241d;border:1px solid var(--line);border-radius:999px;padding:6px 12px;font-size:13px}
.pill b{color:var(--green)}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px;margin-bottom:16px}
label{display:block;font-size:12px;color:var(--mut);margin:0 0 6px}
textarea{width:100%;min-height:200px;background:#0c1511;border:1px solid var(--line);color:var(--ink);
border-radius:11px;padding:12px;font:13px ui-monospace,Consolas,monospace;outline:none;resize:vertical}
textarea:focus{border-color:var(--green)}
.modes{display:flex;gap:14px;margin:12px 0;flex-wrap:wrap;font-size:13px;color:var(--mut)}
.modes label{display:flex;align-items:center;gap:6px;margin:0}
.btn{border:0;border-radius:11px;padding:12px 18px;font-weight:800;font-size:14px;cursor:pointer;
background:linear-gradient(180deg,#33d873,var(--green2));color:#04231a}
.btn.ghost{background:#17241d;color:var(--ink);border:1px solid var(--line)}
.btn.danger{background:#2a1414;color:#ff8d8d;border:1px solid #5a2020}
.actions{display:flex;gap:10px;margin-top:14px;flex-wrap:wrap}
.hint{color:var(--mut);font-size:12px;margin-top:8px;line-height:1.5}
.stat{display:flex;gap:20px;flex-wrap:wrap}
.stat div{font-size:13px;color:var(--mut)}.stat b{display:block;font-size:22px;color:var(--ink)}
.msg{margin-top:12px;font-size:13px}.ok{color:var(--green)}.err{color:#ff6b6b}
a.logout{color:var(--mut);font-size:12px;text-decoration:none}
input[type=file]{color:var(--mut);font-size:13px;margin-top:10px}
</style></head><body><div class="wrap">
  <div class="top"><h1>🍪 Cookie pool — Admin</h1>
    <span class="pill">In pool: <b id="cnt">{{ remaining }}</b></span></div>

  <div class="card">
    <div class="stat">
      <div><b id="sRem">{{ remaining }}</b>remaining</div>
      <div><b id="sTot">{{ taken_total }}</b>handed out (all time)</div>
      <div><b id="sToday">{{ taken_today }}</b>handed out (24h)</div>
    </div>
  </div>

  <div class="card">
    <label>Paste cookies (or choose a .txt file below)</label>
    <textarea id="box" placeholder="Paste your cookies here…"></textarea>
    <input type="file" id="file" accept=".txt,.json,.csv,text/plain">
    <div class="modes">
      <span>Each cookie is separated by:</span>
      <label><input type="radio" name="mode" value="blank" checked> a blank line</label>
      <label><input type="radio" name="mode" value="line"> one per line</label>
      <label><input type="radio" name="mode" value="dashes"> a ----- line</label>
    </div>
    <div class="actions">
      <button class="btn" id="add">Add to pool</button>
      <button class="btn ghost" id="refresh">Refresh count</button>
      <button class="btn danger" id="clear">Clear ALL</button>
      <a class="logout" href="/admin/logout">Log out</a>
    </div>
    <div class="msg" id="msg"></div>
    <div class="hint">Each user gets exactly one cookie, then it's deleted from the pool — no one else can get it.
      User page: <b>/</b>{% if need_key %} · access key required{% endif %}</div>
  </div>
</div>
<script>
const $=id=>document.getElementById(id);
function mode(){return document.querySelector('input[name=mode]:checked').value;}
function setMsg(t,c){$('msg').textContent=t;$('msg').className="msg "+(c||"");}
function setCounts(d){if(d.remaining!=null){$('cnt').textContent=d.remaining;$('sRem').textContent=d.remaining;}
  if(d.taken_total!=null)$('sTot').textContent=d.taken_total; if(d.taken_today!=null)$('sToday').textContent=d.taken_today;}
$('file').addEventListener('change',async e=>{const f=e.target.files[0];if(!f)return;$('box').value=await f.text();setMsg("Loaded "+f.name+" — pick a separator and Add.","ok");});
$('add').addEventListener('click',async()=>{
  const text=$('box').value; if(!text.trim()){setMsg("Nothing to add.","err");return;}
  $('add').disabled=true; setMsg("Adding…","");
  const r=await fetch('/api/admin/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cookies:text,mode:mode()})});
  const d=await r.json(); $('add').disabled=false;
  if(d.ok){setMsg("Added "+d.added+" cookies. Pool now "+d.remaining+".","ok");$('box').value="";setCounts(d);}
  else setMsg(d.error||"Failed.","err");
});
$('refresh').addEventListener('click',async()=>{const d=await(await fetch('/api/admin/stats')).json();setCounts(d);setMsg("Refreshed.","ok");});
$('clear').addEventListener('click',async()=>{
  if(!confirm("Delete ALL cookies from the pool? This cannot be undone."))return;
  const d=await(await fetch('/api/admin/clear',{method:'POST'})).json();
  if(d.ok){setCounts(d);setMsg("Pool cleared.","ok");}
});
</script></body></html>
"""

LOGIN_HTML = r"""
<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Admin login</title>
<style>body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#0b0f0d;
color:#e8f1ec;font-family:system-ui,Segoe UI,Roboto,sans-serif}form{background:#121a16;border:1px solid #1f2d25;
border-radius:16px;padding:26px;width:300px}h1{font-size:17px;margin:0 0 14px;text-align:center}
input{width:100%;background:#0c1511;border:1px solid #1f2d25;color:#e8f1ec;border-radius:10px;padding:12px;margin-bottom:12px;outline:none}
button{width:100%;border:0;border-radius:10px;padding:12px;font-weight:800;background:linear-gradient(180deg,#33d873,#16a34a);color:#04231a;cursor:pointer}
.err{color:#ff6b6b;font-size:13px;text-align:center;margin-bottom:10px}</style></head><body>
<form method="post" action="/admin/login"><h1>🍪 Admin login</h1>
{% if error %}<div class="err">Wrong password</div>{% endif %}
<input type="password" name="password" placeholder="Admin password" autofocus>
<button>Enter</button></form></body></html>
"""


def is_admin():
    return session.get("admin") is True


@app.get("/admin")
def admin_page():
    if not is_admin():
        return render_template_string(LOGIN_HTML, error=False)
    s = stats()
    return render_template_string(ADMIN_HTML, need_key=bool(USER_KEY), **s)


@app.post("/admin/login")
def admin_login():
    if request.form.get("password", "") == ADMIN_PASSWORD:
        session["admin"] = True
        return redirect("/admin")
    return render_template_string(LOGIN_HTML, error=True)


@app.get("/admin/logout")
def admin_logout():
    session.clear()
    return redirect("/admin")


def stats():
    con = db()
    rem = con.execute("SELECT COUNT(*) FROM cookies").fetchone()[0]
    tot = con.execute("SELECT COUNT(*) FROM taken").fetchone()[0]
    day = con.execute("SELECT COUNT(*) FROM taken WHERE at>=?",
                      (int(time.time()) - 86400,)).fetchone()[0]
    con.close()
    return {"remaining": rem, "taken_total": tot, "taken_today": day}


@app.get("/api/admin/stats")
def api_stats():
    if not is_admin():
        return jsonify(error="unauthorized"), 401
    return jsonify(**stats())


@app.post("/api/admin/add")
def api_add():
    if not is_admin():
        return jsonify(error="unauthorized"), 401
    data = request.get_json(silent=True) or {}
    items = split_cookies(data.get("cookies", ""), data.get("mode", "blank"))
    if not items:
        return jsonify(ok=False, error="No cookies found. Check the separator.")
    now = int(time.time())
    con = db()
    con.executemany("INSERT INTO cookies(content, added_at) VALUES(?,?)",
                    [(c, now) for c in items])
    con.commit(); con.close()
    s = stats()
    return jsonify(ok=True, added=len(items), **s)


@app.post("/api/admin/clear")
def api_clear():
    if not is_admin():
        return jsonify(error="unauthorized"), 401
    con = db(); con.execute("DELETE FROM cookies"); con.commit(); con.close()
    return jsonify(ok=True, **stats())


@app.get("/healthz")
def health():
    return Response("ok", mimetype="text/plain")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
