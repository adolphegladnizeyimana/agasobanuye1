import os, re, json, sqlite3, secrets, mimetypes, uuid, time
from datetime import datetime, timezone, timedelta
from functools import wraps
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, send_file, session, abort
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE = Path(__file__).resolve().parent
DATA = BASE / 'data'; DATA.mkdir(exist_ok=True)
UPLOADS = DATA / 'uploads'; UPLOADS.mkdir(exist_ok=True)
DB = DATA / 'agasobanuye1.sqlite3'
app = Flask(__name__, static_folder='public', static_url_path='')
secret_file = DATA / '.secret'
app.secret_key = os.environ.get('SECRET_KEY') or (secret_file.read_text().strip() if secret_file.exists() else None)
if not app.secret_key:
    app.secret_key = secrets.token_hex(32)
    secret_file.write_text(app.secret_key)
app.config.update(MAX_CONTENT_LENGTH=750 * 1024 * 1024, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE') == '1')

def conn():
    c=sqlite3.connect(DB, timeout=15); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); c.execute('PRAGMA journal_mode=WAL'); return c

def now(): return datetime.now(timezone.utc).isoformat()
def row(r): return dict(r) if r else None
def fail(message, code=400): return jsonify({'error':message}),code
def user():
    if not session.get('uid'): return None
    with conn() as c: return row(c.execute('SELECT id,name,email,role,premium_until,created_at FROM users WHERE id=?',(session['uid'],)).fetchone())
def premium(u): return bool(u and (u['role']=='admin' or (u['premium_until'] and u['premium_until'] > now())))
def auth(fn):
    @wraps(fn)
    def inner(*a,**kw):
        if not user(): return fail('Sign in to continue.',401)
        return fn(*a,**kw)
    return inner
def admin(fn):
    @wraps(fn)
    def inner(*a,**kw):
        u=user()
        if not u or u['role']!='admin': return fail('Admin access required.',403)
        return fn(*a,**kw)
    return inner
@app.before_request
def csrf_guard():
    if request.method in ('POST','PUT','PATCH','DELETE') and request.endpoint not in ('login','register'):
        if request.headers.get('X-CSRF-Token') != session.get('csrf') or not session.get('csrf'): return fail('Invalid security token. Refresh the page.',403)

def setting(c,key,default=''):
    r=c.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone(); return r['value'] if r else default

def init():
    with conn() as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT NOT NULL,email TEXT NOT NULL UNIQUE,password_hash TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'member',premium_until TEXT,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS titles(id INTEGER PRIMARY KEY,title TEXT NOT NULL,slug TEXT NOT NULL UNIQUE,description TEXT NOT NULL DEFAULT '',genre TEXT NOT NULL DEFAULT 'Drama',kind TEXT NOT NULL DEFAULT 'Movie',year INTEGER,runtime TEXT,age_rating TEXT DEFAULT '13+',language TEXT DEFAULT 'Kinyarwanda',poster TEXT DEFAULT '',backdrop TEXT DEFAULT '',video_url TEXT DEFAULT '',video_file TEXT DEFAULT '',trailer_url TEXT DEFAULT '',featured INTEGER DEFAULT 0,premium INTEGER DEFAULT 0,downloadable INTEGER DEFAULT 1,published INTEGER DEFAULT 1,views INTEGER DEFAULT 0,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS news(id INTEGER PRIMARY KEY,title TEXT NOT NULL,body TEXT NOT NULL,cover TEXT DEFAULT '',premium INTEGER DEFAULT 0,published INTEGER DEFAULT 1,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS payment_requests(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),plan TEXT NOT NULL,method TEXT NOT NULL,payer_name TEXT NOT NULL,payer_phone TEXT NOT NULL,reference TEXT DEFAULT '',proof_file TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',admin_note TEXT DEFAULT '',created_at TEXT NOT NULL,reviewed_at TEXT);
        CREATE TABLE IF NOT EXISTS watchlist(user_id INTEGER NOT NULL REFERENCES users(id),title_id INTEGER NOT NULL REFERENCES titles(id),PRIMARY KEY(user_id,title_id));
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_titles_published ON titles(published,created_at); CREATE INDEX IF NOT EXISTS idx_requests_status ON payment_requests(status,created_at);''')
        defaults={'site_name':'Agasobanuye1','hero_eyebrow':'THE STORIES YOU LOVE, IN YOUR LANGUAGE','hero_heading':'Stories hit different here.','hero_subtitle':'Discover movies, series and stories worth staying in for. Your next favorite starts here.','plan_price':'5000','plan_days':'30','momo_code':'1693488','payment_phone':'0794990345','whatsapp':'0794990345','tiktok':'GLAD ENT','instagram':'GLAD RWA','owner':'ADOLPHE NIZEYIMANA','announcement':'Welcome to your new home for entertainment.'}
        for k,v in defaults.items(): c.execute('INSERT OR IGNORE INTO settings VALUES (?,?)',(k,v))
        if not c.execute('SELECT id FROM titles LIMIT 1').fetchone():
            items=[
            ('The Last Light','the-last-light','When the city goes quiet, one unexpected discovery changes everything. A striking story about courage, connection, and the things we leave unsaid.','Thriller','Movie',2025,'1h 48m','16+','Kinyarwanda','/assets/poster-night.jpg','/assets/hero.jpg',1,0),
            ('Beyond the Hills','beyond-the-hills','A journey across familiar landscapes becomes a search for something far more personal.','Adventure','Movie',2024,'2h 06m','13+','Kinyarwanda','/assets/poster-journey.jpg','/assets/poster-journey.jpg',0,0),
            ('After Dark','after-dark','One night. Too many secrets. A gripping mystery in the heart of the city.','Mystery','Series',2025,'6 episodes','16+','English','/assets/poster-night.jpg','/assets/poster-night.jpg',0,1),
            ('The Road Home','the-road-home','Every road leads somewhere. This one leads back to what matters.','Drama','Movie',2023,'1h 56m','13+','Kinyarwanda','/assets/poster-journey.jpg','/assets/poster-journey.jpg',0,0),
            ('City of Secrets','city-of-secrets','A new face in the city uncovers a story nobody wanted told.','Thriller','Series',2025,'8 episodes','16+','Kinyarwanda','/assets/poster-night.jpg','/assets/poster-night.jpg',0,1),
            ('Golden Hour','golden-hour','The smallest moments leave the biggest mark.','Drama','Movie',2024,'1h 42m','All','English','/assets/poster-journey.jpg','/assets/poster-journey.jpg',0,0)]
            for t in items: c.execute('INSERT INTO titles(title,slug,description,genre,kind,year,runtime,age_rating,language,poster,backdrop,featured,premium,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(*t,now()))
        if not c.execute('SELECT id FROM news LIMIT 1').fetchone():
            c.execute('INSERT INTO news(title,body,cover,premium,created_at) VALUES (?,?,?,?,?)',('A new chapter starts here','Welcome to Agasobanuye1. This is your space for cinema, entertainment, and stories that stay with you. Check back for official updates and new releases.','/assets/hero.jpg',0,now()))
                env_email = os.environ.get('ADMIN_EMAIL','').strip().lower()
        env_password = os.environ.get('ADMIN_PASSWORD','').strip()
        existing_admin = c.execute("SELECT id FROM users WHERE role='admin' LIMIT 1").fetchone()
        if not existing_admin:
            email = env_email or 'admin@agasobanuye1.local'
            password = env_password or secrets.token_urlsafe(15)
            c.execute('INSERT INTO users(name,email,password_hash,role,created_at) VALUES (?,?,?,?,?)',('Administrator',email,generate_password_hash(password),'admin',now()))
            print('\n'+'='*55+'\nFIRST-RUN ADMIN LOGIN\nEmail: '+email+'\nPassword: '+password+'\n'+'='*55+'\n',flush=True)
        else:
            if env_email and env_password:
                c.execute("UPDATE users SET email=?, password_hash=? WHERE role='admin'",(env_email, generate_password_hash(env_password)))
                print(f"\n=== ADMIN UPDATED to {env_email} ===\n", flush=True)
@app.get('/')
def index(): return send_from_directory('public','index.html')
@app.get('/api/bootstrap')
def bootstrap():
    if not session.get('csrf'): session['csrf']=secrets.token_urlsafe(32)
    with conn() as c: settings={r['key']:r['value'] for r in c.execute('SELECT * FROM settings')}
    return jsonify({'user':user(),'csrf':session['csrf'],'settings':settings})
@app.post('/api/register')
def register():
    d=request.get_json(silent=True) or {}; name=str(d.get('name','')).strip()[:80]; email=str(d.get('email','')).strip().lower(); password=str(d.get('password',''))
    if len(name)<2 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(password)<10: return fail('Enter a name, valid email, and a password of at least 10 characters.')
    try:
        with conn() as c:
            cur=c.execute('INSERT INTO users(name,email,password_hash,created_at) VALUES (?,?,?,?)',(name,email,generate_password_hash(password),now())); uid=cur.lastrowid
    except sqlite3.IntegrityError: return fail('This email is already registered.',409)
    session.clear(); session['uid']=uid; session['csrf']=secrets.token_urlsafe(32)
    return jsonify({'user':user(),'csrf':session['csrf']})
@app.post('/api/login')
def login():
    d=request.get_json(silent=True) or {}; email=str(d.get('email','')).strip().lower()
    with conn() as c: r=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
    if not r or not check_password_hash(r['password_hash'],str(d.get('password',''))): return fail('Email or password is incorrect.',401)
    session.clear(); session['uid']=r['id']; session['csrf']=secrets.token_urlsafe(32)
    return jsonify({'user':user(),'csrf':session['csrf']})
@app.post('/api/logout')
def logout(): session.clear(); return jsonify({'ok':True})
@app.get('/api/titles')
def titles():
    q=request.args.get('q','').strip()[:100]; genre=request.args.get('genre',''); kind=request.args.get('kind',''); limit=min(max(int(request.args.get('limit','100')),1),100); offset=max(int(request.args.get('offset','0')),0)
    sql='SELECT id,title,slug,description,genre,kind,year,runtime,age_rating,language,poster,backdrop,featured,premium,downloadable,views,created_at FROM titles WHERE published=1'; args=[]
    if q: sql+=' AND (title LIKE ? OR description LIKE ? OR genre LIKE ?)'; args+=['%'+q+'%']*3
    if genre: sql+=' AND genre=?'; args.append(genre)
    if kind: sql+=' AND kind=?'; args.append(kind)
    with conn() as c:
        total=c.execute('SELECT COUNT(*) FROM ('+sql+')',args).fetchone()[0]; items=[row(r) for r in c.execute(sql+' ORDER BY featured DESC, created_at DESC, id DESC LIMIT ? OFFSET ?',args+[limit,offset])]
    return jsonify({'items':items,'total':total})
@app.get('/api/titles/<int:tid>')
def title(tid):
    with conn() as c: r=c.execute('SELECT id,title,slug,description,genre,kind,year,runtime,age_rating,language,poster,backdrop,trailer_url,featured,premium,downloadable,views FROM titles WHERE id=? AND published=1',(tid,)).fetchone()
    if not r: return fail('Title not found.',404)
    return jsonify(row(r))
@app.get('/api/news')
def news():
    u=user(); with_premium=premium(u)
    with conn() as c: items=[row(r) for r in c.execute('SELECT * FROM news WHERE published=1 AND (premium=0 OR ?=1) ORDER BY created_at DESC',(int(with_premium),))]
    return jsonify({'items':items})
@app.get('/api/news/<int:nid>')
def news_detail(nid):
    with conn() as c: r=c.execute('SELECT * FROM news WHERE id=? AND published=1',(nid,)).fetchone()
    if not r: return fail('Article not found.',404)
    if r['premium'] and not premium(user()): return fail('Premium membership required.',403)
    return jsonify(row(r))
@app.post('/api/titles/<int:tid>/play')
@auth
def play(tid):
    with conn() as c:
        r=c.execute('SELECT * FROM titles WHERE id=? AND published=1',(tid,)).fetchone()
        if not r: return fail('Title not found.',404)
        if r['premium'] and not premium(user()): return fail('Upgrade to Premium to watch this title.',403)
        if not r['video_file'] and not r['video_url']: return fail('This title is coming soon. The admin has not added a video yet.',409)
        c.execute('UPDATE titles SET views=views+1 WHERE id=?',(tid,))
    return jsonify({'url':'/api/stream/'+str(tid) if r['video_file'] else r['video_url']})
@app.get('/api/stream/<int:tid>')
@auth
def stream(tid):
    with conn() as c: r=c.execute('SELECT video_file,premium,published FROM titles WHERE id=?',(tid,)).fetchone()
    if not r or not r['published'] or (r['premium'] and not premium(user())) or not r['video_file']: abort(403)
    return send_from_directory(UPLOADS,r['video_file'],conditional=True)
@app.get('/api/titles/<int:tid>/download')
@auth
def download(tid):
    if not premium(user()): return fail('Premium membership required for downloads.',403)
    with conn() as c: r=c.execute('SELECT title,video_file,downloadable,published FROM titles WHERE id=?',(tid,)).fetchone()
    if not r or not r['published'] or not r['downloadable'] or not r['video_file']: return fail('Download is not available for this title.',404)
    return send_from_directory(UPLOADS,r['video_file'],as_attachment=True,download_name=secure_filename(r['title'])+Path(r['video_file']).suffix)
@app.get('/api/watchlist')
@auth
def watchlist():
    with conn() as c: return jsonify({'ids':[r[0] for r in c.execute('SELECT title_id FROM watchlist WHERE user_id=?',(user()['id'],))]})
@app.post('/api/watchlist/<int:tid>')
@auth
def toggle_watchlist(tid):
    uid=user()['id']
    with conn() as c:
        if not c.execute('SELECT id FROM titles WHERE id=? AND published=1',(tid,)).fetchone(): return fail('Title not found.',404)
        r=c.execute('SELECT 1 FROM watchlist WHERE user_id=? AND title_id=?',(uid,tid)).fetchone()
        if r: c.execute('DELETE FROM watchlist WHERE user_id=? AND title_id=?',(uid,tid))
        else: c.execute('INSERT INTO watchlist VALUES (?,?)',(uid,tid))
    return jsonify({'saved':not bool(r)})

def store_file(file, allowed, max_bytes):
    if not file or not file.filename: raise ValueError('Choose a file to upload.')
    ext=Path(secure_filename(file.filename)).suffix.lower()
    if ext not in allowed: raise ValueError('Unsupported file type. Allowed: '+', '.join(allowed))
    header=file.stream.read(32)
    if ext in ('.jpg','.jpeg') and not header.startswith(b'\xff\xd8\xff'): raise ValueError('Invalid JPEG file.')
    if ext=='.png' and not header.startswith(b'\x89PNG\r\n\x1a\n'): raise ValueError('Invalid PNG file.')
    if ext=='.pdf' and not header.startswith(b'%PDF'): raise ValueError('Invalid PDF file.')
    if ext=='.webp' and header[0:4]!=b'RIFF': raise ValueError('Invalid WebP file.')
    if ext=='.mp4' and b'ftyp' not in header: raise ValueError('Invalid MP4 file.')
    if ext=='.webm' and not header.startswith(b'\x1a\x45\xdf\xa3'): raise ValueError('Invalid WebM file.')
    name=uuid.uuid4().hex+ext; path=UPLOADS/name; size=len(header)
    try:
        with path.open('wb') as out:
            out.write(header)
            while True:
                chunk=file.stream.read(1024*1024)
                if not chunk: break
                size+=len(chunk)
                if size>max_bytes: raise ValueError('File is too large.')
                out.write(chunk)
        return name
    except Exception:
        path.unlink(missing_ok=True)
        raise
@app.post('/api/payment-requests')
@auth
def payment_request():
    d=request.form; method=d.get('method',''); payer=d.get('payer_name','').strip()[:100]; phone=d.get('payer_phone','').strip()[:30]
    if method not in ('MTN MoMo','Airtel Money') or len(payer)<2 or not re.fullmatch(r'[+\d\s-]{9,20}',phone): return fail('Enter a valid method, SIM registration name and payer phone.')
    with conn() as c:
        if c.execute("SELECT id FROM payment_requests WHERE user_id=? AND status='pending'",(user()['id'],)).fetchone(): return fail('You already have a pending request. Please wait for review.',409)
    try: proof=store_file(request.files.get('proof'),{'.jpg','.jpeg','.png','.webp','.pdf'},6*1024*1024)
    except ValueError as e: return fail(str(e))
    with conn() as c: c.execute('INSERT INTO payment_requests(user_id,plan,method,payer_name,payer_phone,reference,proof_file,created_at) VALUES (?,?,?,?,?,?,?,?)',(user()['id'],'monthly',method,payer,phone,d.get('reference','').strip()[:100],proof,now()))
    return jsonify({'ok':True,'message':'Payment proof submitted. An admin will review it before access is granted.'}),201
@app.get('/api/my-requests')
@auth
def my_requests():
    with conn() as c: return jsonify({'items':[row(r) for r in c.execute('SELECT id,plan,method,payer_name,payer_phone,reference,status,admin_note,created_at,reviewed_at FROM payment_requests WHERE user_id=? ORDER BY id DESC',(user()['id'],))]})

@app.get('/api/admin/overview')
@admin
def overview():
    with conn() as c:
        return jsonify({'titles':c.execute('SELECT COUNT(*) FROM titles').fetchone()[0],'members':c.execute("SELECT COUNT(*) FROM users WHERE role='member'").fetchone()[0],'pending':c.execute("SELECT COUNT(*) FROM payment_requests WHERE status='pending'").fetchone()[0],'views':c.execute('SELECT COALESCE(SUM(views),0) FROM titles').fetchone()[0],'premium_members':c.execute('SELECT COUNT(*) FROM users WHERE premium_until>?',(now(),)).fetchone()[0],'recent':[row(r) for r in c.execute('SELECT p.id,p.payer_name,p.method,p.status,p.created_at,u.email FROM payment_requests p JOIN users u ON u.id=p.user_id ORDER BY p.id DESC LIMIT 5')]})
@app.get('/api/admin/titles')
@admin
def admin_titles():
    with conn() as c: return jsonify({'items':[row(r) for r in c.execute('SELECT * FROM titles ORDER BY id DESC')]})

def title_payload(d):
    allowed=['title','description','genre','kind','year','runtime','age_rating','language','poster','backdrop','video_url','trailer_url','featured','premium','downloadable','published']
    o={k:d[k] for k in allowed if k in d}
    for k in ('featured','premium','downloadable','published'): 
        if k in o: o[k]=int(bool(o[k]))
    for k in ('title','description','genre','kind','runtime','age_rating','language','poster','backdrop','video_url','trailer_url'):
        if k in o: o[k]=str(o[k]).strip()[:4000 if k=='description' else 1000]
    if 'title' in o and len(o['title'])<2: raise ValueError('Title must be at least 2 characters.')
    for k in ('poster','backdrop','video_url','trailer_url'):
        if k in o and o[k] and not (o[k].startswith('/') or o[k].startswith('https://')): raise ValueError(k+' must be HTTPS or a local path.')
    if 'year' in o: o['year']=int(o['year']) if o['year'] else None
    return o
@app.post('/api/admin/titles')
@admin
def add_title():
    try: d=title_payload(request.get_json() or {})
    except (ValueError,TypeError) as e: return fail(str(e))
    if 'title' not in d: return fail('Title is required.')
    d['slug']=re.sub(r'[^a-z0-9]+','-',d['title'].lower()).strip('-')+'-'+secrets.token_hex(3); d['created_at']=now()
    with conn() as c:
        cur=c.execute('INSERT INTO titles('+','.join(d)+') VALUES ('+','.join('?'*len(d))+')',list(d.values()))
    return jsonify({'id':cur.lastrowid}),201
@app.put('/api/admin/titles/<int:tid>')
@admin
def update_title(tid):
    try: d=title_payload(request.get_json() or {})
    except (ValueError,TypeError) as e: return fail(str(e))
    if not d: return fail('No fields supplied.')
    with conn() as c: cur=c.execute('UPDATE titles SET '+','.join(k+'=?' for k in d)+' WHERE id=?',list(d.values())+[tid])
    if not cur.rowcount: return fail('Title not found.',404)
    return jsonify({'ok':True})
@app.put('/api/admin/titles/<int:tid>/video')
@admin
def attach_video(tid):
    name=str((request.get_json() or {}).get('name',''))
    if not re.fullmatch(r'[0-9a-f]{32}\.(mp4|webm)',name) or not (UPLOADS/name).is_file(): return fail('Uploaded video not found.')
    with conn() as c: cur=c.execute('UPDATE titles SET video_file=? WHERE id=?',(name,tid))
    if not cur.rowcount: return fail('Title not found.',404)
    return jsonify({'ok':True})
@app.delete('/api/admin/titles/<int:tid>')
@admin
def delete_title(tid):
    with conn() as c: c.execute('DELETE FROM watchlist WHERE title_id=?',(tid,)); c.execute('DELETE FROM titles WHERE id=?',(tid,))
    return jsonify({'ok':True})
@app.post('/api/admin/upload')
@admin
def upload():
    kind=request.form.get('kind','image'); allowed={'.jpg','.jpeg','.png','.webp'} if kind=='image' else {'.mp4','.webm'} if kind=='video' else set()
    if not allowed: return fail('Invalid upload type.')
    try: name=store_file(request.files.get('file'),allowed,15*1024*1024 if kind=='image' else 700*1024*1024)
    except ValueError as e: return fail(str(e))
    return jsonify({'url':'/api/media/'+name,'name':name})
@app.get('/api/media/<name>')
def media(name):
    if not re.fullmatch(r'[0-9a-f]{32}\.(jpg|jpeg|png|webp|mp4|webm)',name): abort(404)
    # Uploaded video is only available through authenticated /api/stream.
    if name.endswith(('.mp4','.webm')): abort(403)
    return send_from_directory(UPLOADS,name)
@app.get('/api/admin/payments')
@admin
def admin_payments():
    with conn() as c: return jsonify({'items':[row(r) for r in c.execute('SELECT p.*,u.name AS user_name,u.email AS user_email FROM payment_requests p JOIN users u ON u.id=p.user_id ORDER BY CASE p.status WHEN \'pending\' THEN 0 ELSE 1 END,p.id DESC')]})
@app.get('/api/admin/payments/<int:pid>/proof')
@admin
def proof(pid):
    with conn() as c: r=c.execute('SELECT proof_file FROM payment_requests WHERE id=?',(pid,)).fetchone()
    if not r: abort(404)
    return send_from_directory(UPLOADS,r['proof_file'])
@app.post('/api/admin/payments/<int:pid>/review')
@admin
def review(pid):
    d=request.get_json() or {}; status=d.get('status'); note=str(d.get('note','')).strip()[:500]
    if status not in ('approved','rejected'): return fail('Choose approve or reject.')
    with conn() as c:
        r=c.execute('SELECT * FROM payment_requests WHERE id=?',(pid,)).fetchone()
        if not r: return fail('Request not found.',404)
        if r['status']!='pending': return fail('This request was already reviewed.',409)
        if status=='approved':
            days=max(1,min(int(setting(c,'plan_days','30')),365)); current=c.execute('SELECT premium_until FROM users WHERE id=?',(r['user_id'],)).fetchone()['premium_until']; start=max(datetime.now(timezone.utc),datetime.fromisoformat(current) if current else datetime.now(timezone.utc))
            c.execute('UPDATE users SET premium_until=? WHERE id=?',((start+timedelta(days=days)).isoformat(),r['user_id']))
        c.execute('UPDATE payment_requests SET status=?,admin_note=?,reviewed_at=? WHERE id=?',(status,note,now(),pid))
    return jsonify({'ok':True})
@app.get('/api/admin/users')
@admin
def admin_users():
    with conn() as c: return jsonify({'items':[row(r) for r in c.execute('SELECT id,name,email,role,premium_until,created_at FROM users ORDER BY id DESC')]})
@app.post('/api/admin/users/<int:uid>/premium')
@admin
def user_premium(uid):
    d=request.get_json() or {}; days=int(d.get('days',0))
    if days<0 or days>3650: return fail('Days must be between 0 and 3650.')
    until=(datetime.now(timezone.utc)+timedelta(days=days)).isoformat() if days else None
    with conn() as c: cur=c.execute('UPDATE users SET premium_until=? WHERE id=? AND role!=\'admin\'',(until,uid))
    if not cur.rowcount: return fail('Member not found.',404)
    return jsonify({'ok':True})
@app.get('/api/admin/news')
@admin
def admin_news():
    with conn() as c: return jsonify({'items':[row(r) for r in c.execute('SELECT * FROM news ORDER BY id DESC')]})
@app.post('/api/admin/news')
@admin
def add_news():
    d=request.get_json() or {}; title=str(d.get('title','')).strip()[:200]; body=str(d.get('body','')).strip()[:10000]
    if len(title)<3 or len(body)<10: return fail('Enter a headline and at least 10 characters of article text.')
    with conn() as c: cur=c.execute('INSERT INTO news(title,body,cover,premium,published,created_at) VALUES (?,?,?,?,?,?)',(title,body,str(d.get('cover',''))[:1000],int(bool(d.get('premium'))),int(bool(d.get('published',True))),now()))
    return jsonify({'id':cur.lastrowid}),201
@app.put('/api/admin/news/<int:nid>')
@admin
def update_news(nid):
    d=request.get_json() or {}; fields={k:d[k] for k in ('title','body','cover','premium','published') if k in d}
    if not fields: return fail('No fields supplied.')
    for k in ('premium','published'):
        if k in fields: fields[k]=int(bool(fields[k]))
    with conn() as c: cur=c.execute('UPDATE news SET '+','.join(k+'=?' for k in fields)+' WHERE id=?',list(fields.values())+[nid])
    if not cur.rowcount: return fail('Article not found.',404)
    return jsonify({'ok':True})
@app.delete('/api/admin/news/<int:nid>')
@admin
def delete_news(nid):
    with conn() as c: c.execute('DELETE FROM news WHERE id=?',(nid,))
    return jsonify({'ok':True})
@app.put('/api/admin/settings')
@admin
def update_settings():
    allowed={'site_name','hero_eyebrow','hero_heading','hero_subtitle','plan_price','plan_days','momo_code','payment_phone','whatsapp','tiktok','instagram','owner','announcement'}; d=request.get_json() or {}
    with conn() as c:
        for k,v in d.items():
            if k in allowed: c.execute('INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(k,str(v).strip()[:1000]))
    return jsonify({'ok':True})
@app.post('/api/account/password')
@auth
def password():
    d=request.get_json() or {}; old=str(d.get('current','')); new=str(d.get('new',''))
    if len(new)<10: return fail('New password must be at least 10 characters.')
    with conn() as c:
        r=c.execute('SELECT password_hash FROM users WHERE id=?',(user()['id'],)).fetchone()
        if not check_password_hash(r['password_hash'],old): return fail('Current password is incorrect.',403)
        c.execute('UPDATE users SET password_hash=? WHERE id=?',(generate_password_hash(new),user()['id']))
    return jsonify({'ok':True})
@app.errorhandler(413)
def too_big(e): return fail('Upload exceeds server limit.',413)

if __name__=='__main__':
    init(); app.run(host='0.0.0.0',port=int(os.environ.get('PORT','8000')),debug=False,threaded=True)
