# 🍪 One-Time Cookie Dispenser

A tiny web app: you (admin) upload a **pool of cookies**; each user takes **one**,
and the moment it's handed out it is **deleted** — so no one else can ever get
that same cookie. Built for **Railway** (binds to `$PORT`).

## How it works
- **Admin** → `/admin` (password): paste or upload cookies, see live counts, clear pool.
- **User** → `/` : one click = one cookie → it downloads as a `.txt` and is removed from the pool.
- One cookie is handed to **exactly one** person (atomic pop, safe under concurrent clicks).

## Settings (change these)
Set as **Railway → Variables**, or edit the defaults at the top of `app.py`:

| Variable | What | Default |
|---|---|---|
| `ADMIN_PASSWORD` | password for `/admin` | `Moaz!!admin00` |
| `USER_KEY` | access key users must enter (leave empty `""` = open to anyone) | `green2026` |
| `SECRET_KEY` | session signing secret | (set your own) |
| `COOKIE_DB_PATH` | where the SQLite file lives | `./data/cookies.db` |

## Deploy on Railway (2 ways)

**A) From GitHub (easiest)**
1. Push this folder to a GitHub repo.
2. Railway → New Project → *Deploy from GitHub repo* → pick it.
3. Railway auto-detects Python + `Procfile`. Done — open the generated URL.
4. Add the Variables above (at least change `ADMIN_PASSWORD` + `USER_KEY`).

**B) Railway CLI**
```
npm i -g @railway/cli
railway login
railway init
railway up
```

### ⚠️ Keep your cookies across redeploys (important)
Railway's disk is wiped on every redeploy. To keep the pool:
1. Railway → your service → **Volumes** → New Volume → mount path `/data`.
2. Add variable `COOKIE_DB_PATH=/data/cookies.db`.
Now the pool survives restarts and new deploys.

## Use it
1. Open `/admin`, log in, paste your cookies, pick the separator
   (*blank line between* / *one per line* / *----- line between*), click **Add to pool**.
2. Share your site URL (the `/` page) with your users. If `USER_KEY` is set, give them that key.
3. Each user clicks **Get my cookie** → gets one, it's gone from the pool.

## Run locally
```
pip install -r requirements.txt
python app.py
# open http://localhost:5000  and  http://localhost:5000/admin
```
