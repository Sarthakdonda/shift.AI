"""Fixed native wrappers and isolated OS-worker packaging; no source ZIP masquerades as a binary."""
import hashlib
import json
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path
from bson import ObjectId
from app.core.config import get_settings
from app.core.errors import AppError
from app.repositories.store import now

TEMPLATE = Path(__file__).resolve().parents[1] / 'templates' / 'portable'
TOOLS = Path(__file__).resolve().parents[2] / 'build-tools'
TARGETS = {'windows':('.exe','Windows'), 'macos':('.dmg','Darwin'), 'android':('.apk',None), 'android_bundle':('.aab',None), 'ios':('.ipa','Darwin')}


def windows_compiler_available():
    if shutil.which('link.exe'):
        return True
    for variable in ('ProgramFiles(x86)', 'ProgramFiles'):
        base = os.environ.get(variable)
        if not base:
            continue
        locator = Path(base) / 'Microsoft Visual Studio/Installer/vswhere.exe'
        if locator.is_file():
            result = subprocess.run([str(locator), '-latest', '-products', '*', '-requires',
                'Microsoft.VisualStudio.Component.VC.Tools.x86.x64', '-find',
                'VC/Tools/MSVC/*/bin/Hostx64/x64/link.exe'], capture_output=True, text=True,
                timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
            if any(Path(line.strip()).is_file() for line in result.stdout.splitlines() if line.strip()):
                return True
    return False


def native_sources(spec, app_id):
    config = {'$schema':'https://schema.tauri.app/config/2','productName':spec['name'],'version':'1.0.0',
        'identifier':'ai.shift.generated.p'+app_id,'build':{'frontendDist':'../../'},
        'app':{'withGlobalTauri':True,'windows':[{'label':'main','title':spec['name'],'width':1200,'height':800}],
            'security':{'csp':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src ipc: http://ipc.localhost; object-src 'none'; base-uri 'self'"}},
        'bundle':{'active':True,'targets':['nsis','dmg'],'icon':['icons/icon.png','icons/icon.ico','icons/icon.icns'],
            'windows':{'webviewInstallMode':{'type':'embedBootstrapper'}}}}
    cargo = """[package]
name = "shift_generated_app"
version = "1.0.0"
edition = "2021"
[lib]
name = "shift_generated_lib"
crate-type = ["staticlib", "cdylib", "rlib"]
[build-dependencies]
tauri-build = { version = "2", features = [] }
[dependencies]
tauri = { version = "2", features = [] }
tauri-plugin-dialog = "2"
tauri-plugin-fs = "2"
rusqlite = { version = "0.38", features = ["bundled"] }
serde_json = "1"
"""
    return {
        'native/src-tauri/tauri.conf.json':json.dumps(config,ensure_ascii=False,indent=2),
        'native/src-tauri/Cargo.toml':cargo,
        'native/src-tauri/build.rs':'fn main() { tauri_build::build() }\n',
        'native/src-tauri/src/main.rs':'#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]\nfn main() { shift_generated_lib::run() }\n',
        'native/src-tauri/src/lib.rs':(TEMPLATE/'native.rs').read_text('utf-8'),
        'native/src-tauri/capabilities/default.json':json.dumps({'identifier':'main','windows':['main'],'permissions':['core:default']}),
    }


def capability(target):
    if target not in TARGETS: return 'Unsupported platform.'
    required=TARGETS[target][1]
    if required and platform.system()!=required: return required+' build worker required.'
    if not (TOOLS/'node_modules/@tauri-apps/cli/tauri.js').exists(): return 'Install backend/build-tools dependencies on the native worker.'
    if not shutil.which('cargo'): return 'Rust and the native compiler toolchain are required.'
    if platform.system() == 'Windows' and not windows_compiler_available():
        return 'Install Microsoft C++ Build Tools with Desktop development with C++ and a Windows SDK (link.exe is missing). Android builds on a Windows Rust host also need this host compiler.'
    if target.startswith('android') and not (os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')):
        return 'Android SDK, NDK, JDK and Rust Android targets must be configured on the worker.'
    if target=='ios' and not get_settings().native_apple_team:
        return 'Apple development team, signing identity and provisioning profile required.'
    if target not in get_settings().native_worker_targets.split(','):
        return 'Configure a dedicated '+target+' native worker before packaging.'
    return ''


def run_command(args, cwd, timeout, env):
    from app.services.portable_validation import run_process
    result=run_process(args,cwd,timeout,env)
    if result.returncode:
        raise AppError((result.stderr or result.stdout or 'Native compiler failed.')[-5000:],422,'native_build')
    return (result.stdout+'\n'+result.stderr)[-5000:]


def package_job(store,pid,actor,artifact_id):
    row=store.db.application_artifacts.find_one({'_id':ObjectId(artifact_id),'project_id':pid})
    key={'_id':row['_id']}
    try:
        store.project(pid,actor,'write')
        build=store.db.application_builds.find_one({'_id':ObjectId(row['build_id']),'project_id':pid,'status':'ready'})
        if not build or build['spec'].get('storage_mode','shared_server')=='shared_server':
            raise AppError('A validated portable build is required.',409)
        reason=capability(row['target'])
        if reason: raise AppError(reason,503,'native_configuration')
        store.db.application_artifacts.update_one(key,{'$set':{'status':'building','started_at':now()},'$push':{'logs':'Preparing fixed Tauri wrapper and SQLite adapter.'}})
        root=Path(get_settings().native_artifact_dir).resolve()
        root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='shift-native-') as directory:
            work=Path(directory)
            for name,text in build['files'].items():
                path=(work/name).resolve()
                if not path.is_relative_to(work):raise AppError('Invalid source path.')
                path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8')
            # Native distribution only embeds web files, never its own Cargo build tree.
            web=work/'native'/'web';web.mkdir()
            for name in ('index.html','app.js','storage.js','style.css','spec.js','icon.svg','manifest.webmanifest','sw.js'):
                shutil.copyfile(work/name,web/name)
            config_path=work/'native/src-tauri/tauri.conf.json'
            config=json.loads(config_path.read_text('utf-8'))
            config['build']['frontendDist']='../web'
            if row['target']=='ios':config['bundle']['iOS']={'developmentTeam':get_settings().native_apple_team}
            config_path.write_text(json.dumps(config),encoding='utf-8')
            cli=[shutil.which('node'),str(TOOLS/'node_modules/@tauri-apps/cli/tauri.js')]
            # Generated data never supplies commands, dependencies, signing values or environment.
            allowed={'PATH','PATHEXT','COMSPEC','SYSTEMDRIVE','SYSTEMROOT','WINDIR','TEMP','TMP','HOME','USERPROFILE','LOCALAPPDATA','APPDATA','PROGRAMDATA','ALLUSERSPROFILE','PROGRAMFILES','PROGRAMFILES(X86)','CARGO_HOME','RUSTUP_HOME','JAVA_HOME','ANDROID_HOME','ANDROID_SDK_ROOT','NDK_HOME','ANDROID_NDK_HOME','DEVELOPER_DIR','VCINSTALLDIR','VCTOOLSINSTALLDIR','WINDOWSSDKDIR','LIB','INCLUDE'}
            env={k:v for k,v in os.environ.items() if k.upper() in allowed}
            env.update(CARGO_NET_OFFLINE='true',CARGO_BUILD_JOBS='2')
            if get_settings().native_dependency_network:env['CARGO_NET_OFFLINE']='false'
            cwd=work/'native'
            def stage(args, timeout, label):
                store.db.application_artifacts.update_one(key, {'$push': {'logs': label}})
                output = run_command(cli + args, cwd, timeout, env)
                store.db.application_artifacts.update_one(key, {'$push': {'logs': output}})
            stage(['icon',str(work/'icon.svg'),'--output',str(cwd/'src-tauri/icons')],60,'Generating application icons.')
            target=row['target']
            if target in ('windows','macos'):
                args=['build','--bundles','nsis' if target=='windows' else 'dmg']
            else:
                mobile='android' if target.startswith('android') else 'ios'
                stage([mobile,'init','--ci'],180,'Preparing '+mobile+' project.')
                args=[mobile,'build']
                if mobile=='android':args+=['--debug','--apk' if target=='android' else '--aab','--target','aarch64']
            stage(args,get_settings().native_build_timeout,'Compiling '+target+' artifact.')
            candidates=[p for p in (cwd/'src-tauri').rglob('*'+TARGETS[target][0]) if p.is_file() and ('bundle' in p.parts or 'outputs' in p.parts or 'apple' in p.parts)]
            if not candidates:raise AppError('Compiler returned without a distributable artifact.',422,'native_build')
            source=max(candidates,key=lambda p:p.stat().st_mtime)
            verify_artifact(source,target)
            artifact=root/(artifact_id+source.suffix)
            shutil.copyfile(source,artifact)
            sha=hashlib.sha256(artifact.read_bytes()).hexdigest()
            store.project(pid,actor,'write')
            store.db.application_artifacts.update_one(key,{'$set':{'status':'ready','path':str(artifact),'size':artifact.stat().st_size,'sha256':sha,'finished_at':now(),
                'signing':'development_or_unsigned','validation':'compiler_and_format_verified','device_validation':'not_executed'},'$push':{'logs':'Artifact format verified. Installation/device validation and production signing are not certified.'}})
    except Exception as exc:
        configuration=isinstance(exc,AppError) and exc.code=='native_configuration'
        store.db.application_artifacts.update_one(key,{'$set':{'status':'requires_configuration' if configuration else 'failed','error':exc.message if isinstance(exc,AppError) else 'Native packaging failed; previous artifacts are preserved.','finished_at':now()}})


def verify_artifact(path,target):
    import zipfile
    if path.stat().st_size<1024:raise AppError('Native artifact is empty or truncated.',422)
    if target=='windows' and path.open('rb').read(2)!=b'MZ':raise AppError('Invalid Windows executable.',422)
    if target=='macos':
        with path.open('rb') as stream:
            stream.seek(-512,2)
            if stream.read(4)!=b'koly':raise AppError('Invalid macOS disk image.',422)
    if target in ('android','android_bundle','ios'):
        if not zipfile.is_zipfile(path):raise AppError('Invalid mobile artifact.',422)
        with zipfile.ZipFile(path) as z:
            names=z.namelist()
            valid=('AndroidManifest.xml' in names and any(n.endswith('.dex') for n in names)) if target=='android' else ('BundleConfig.pb' in names if target=='android_bundle' else any(n.startswith('Payload/') and n.endswith('Info.plist') for n in names))
            if not valid:raise AppError('Mobile artifact is missing required package contents.',422)
