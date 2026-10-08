"""Portable applications compile only data into fixed JS/Rust templates."""
import hashlib
import html
import json
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1] / 'templates' / 'portable'


def compile_portable(spec, build_id, application_id):
    from app.services.native_packaging import native_sources
    release = {'build_id': build_id, 'application_id': application_id, 'schema_version': 1}
    files = {name: (TEMPLATE / name).read_text('utf-8') for name in ('storage.js', 'app.js', 'style.css')}
    files['spec.js'] = 'window.APP_SPEC=' + json.dumps(spec, ensure_ascii=True).replace('<', '\\u003c') + ';\nwindow.APP_RELEASE=' + json.dumps(release) + ';\n'
    files['spec.json'] = json.dumps(spec, ensure_ascii=False, indent=2)
    files['release.json'] = json.dumps(release)
    files['index.html'] = ('<!doctype html><html lang="' + html.escape(spec['language'], quote=True) + '"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="' + html.escape(spec['description'][:300],quote=True) + '">'
        '<meta name="theme-color" content="' + spec['accent'] + '"><title>' + html.escape(spec['name']) + '</title>'
        '<link rel="icon" href="./icon.svg"><link rel="manifest" href="./manifest.webmanifest"><link rel="stylesheet" href="./style.css">'
        '<script defer src="./spec.js"></script><script defer src="./storage.js"></script><script defer src="./app.js"></script>'
        '</head><body><header><a id="brand" href="#"></a><button id="menu" type="button" aria-expanded="false" aria-label="Toggle navigation">Menu</button>'
        '<nav aria-label="Application navigation"></nav></header><div id="status" role="alert" tabindex="-1"></div><main><p>Opening application…</p></main><footer></footer></body></html>')
    files['icon.svg'] = '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512"><rect width="512" height="512" rx="96" fill="' + spec['accent'] + '"/><path d="M128 352V160h80v112h96V160h80v192z" fill="white"/></svg>'
    files['manifest.webmanifest'] = json.dumps({'id':'./','name':spec['name'],'short_name':spec['name'][:25],'start_url':'./index.html','scope':'./','display':'standalone','background_color':'#f6f8f4','theme_color':spec['accent'],'icons':[{'src':'./icon.svg','sizes':'any','type':'image/svg+xml','purpose':'any maskable'}]})
    files['sw.js'] = "const CACHE=" + json.dumps('shift-'+build_id) + """;
const FILES=['./','./index.html','./style.css','./spec.js','./storage.js','./app.js','./icon.svg','./manifest.webmanifest'];
self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(FILES))));
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('shift-')&&k!==CACHE).map(k=>caches.delete(k))))));
self.addEventListener('fetch',e=>{if(e.request.method==='GET'&&new URL(e.request.url).origin===self.location.origin)e.respondWith(fetch(e.request).catch(()=>caches.match(e.request)));});
"""
    files['README.md'] = f"""# {spec['name']}

Ready-to-run static website/application files are at the archive root.
Open index.html for a website. For reliable browser database and PWA support use
a stable HTTPS origin or a local static file server. Publishing is not performed
by shift.AI. Native wrappers are in native/ and use SQLite in the OS app-data
directory; compiled installers are separate downloads, never this source ZIP.

Storage mode: {spec['storage_mode']}. Browser records use IndexedDB, never
localStorage. Single-user local applications do not provide shared authentication
or cross-device sync. Export/import versioned backups to transfer records.
Clearing browser storage or changing origins can lose access to local records.
Sensitive records use AES-GCM with a user passphrase (PBKDF2 SHA-256, 210000 rounds).
Back up regularly; passphrases cannot be recovered. Schema upgrades are additive
and incompatible changes are rejected. Imports merge matching IDs after validating
all records and relationships; unrelated records are preserved atomically.

Native build tools belong on trusted dedicated workers. Code signing and mobile
provisioning require operator credentials. See the platform artifact status for
actual compiler, validation and signing results. No deployment is included.
"""
    files.update(native_sources(spec, application_id))
    findings = [{'severity':'high','component':r['id'],'issue':r['description'],'status':'open'} for r in spec['requirements'] if r['implementation']=='manual']
    return files, {name:hashlib.sha256(data.encode()).hexdigest() for name,data in files.items()}, findings
