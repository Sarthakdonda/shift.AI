"""Build the small Android companion using the installed JDK and Android SDK."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', default='', help='Initial phone server URL, e.g. http://192.168.1.10:3000')
    parser.add_argument('--install', action='store_true')
    args = parser.parse_args()
    sdk = Path(os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT') or Path(os.environ['LOCALAPPDATA']) / 'Android/Sdk')
    java = Path(os.environ.get('JAVA_HOME') or 'C:/Program Files/Java/jdk-21') / 'bin'
    build_tools = sdk / 'build-tools/36.0.0'
    platform = sdk / 'platforms/android-36/android.jar'
    work = ROOT / '.local/android/build'
    dist = ROOT / 'android/dist'
    for folder in [work, dist, work / 'classes', work / 'dex', work / 'res/drawable']:
        folder.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / 'frontend/public/brand/logo-mark-512.png', work / 'res/drawable/icon.png')
    generated = work / 'BuildConfig.java'
    generated.write_text('package com.shiftai.mobile; public final class BuildConfig { public static final String DEFAULT_SERVER = '
                         + json.dumps(args.server) + '; }', encoding='utf-8')

    def run(*command):
        subprocess.run([str(part) for part in command], check=True, cwd=work)

    run(build_tools / 'aapt2.exe', 'compile', '--dir', work / 'res', '-o', work / 'resources.zip')
    run(build_tools / 'aapt2.exe', 'link', '-o', work / 'unsigned.apk', '-I', platform,
        '--manifest', ROOT / 'android/AndroidManifest.xml', work / 'resources.zip')
    run(java / 'javac.exe', '-encoding', 'UTF-8', '-source', '8', '-target', '8', '-classpath', platform,
        '-d', work / 'classes', ROOT / 'android/src/com/shiftai/mobile/MainActivity.java', generated)
    run(java / 'jar.exe', 'cf', work / 'classes.jar', '-C', work / 'classes', '.')
    run(java / 'java.exe', '-cp', build_tools / 'lib/d8.jar', 'com.android.tools.r8.D8',
        '--lib', platform, '--min-api', '26', '--output', work / 'dex', work / 'classes.jar')
    with zipfile.ZipFile(work / 'unsigned.apk', 'a') as apk:
        for dex in (work / 'dex').glob('*.dex'):
            apk.write(dex, dex.name)
    run(build_tools / 'zipalign.exe', '-f', '4', work / 'unsigned.apk', work / 'aligned.apk')
    key = ROOT / '.local/android/shift-local.keystore'
    if not key.exists():
        run(java / 'keytool.exe', '-genkeypair', '-keystore', key, '-storepass', 'android', '-keypass', 'android',
            '-alias', 'shift-local', '-keyalg', 'RSA', '-keysize', '2048', '-validity', '10000', '-dname', 'CN=Shift AI Local Development')
    apk = dist / 'shift-ai.apk'
    run(java / 'java.exe', '-jar', build_tools / 'lib/apksigner.jar', 'sign', '--ks', key,
        '--ks-pass', 'pass:android', '--key-pass', 'pass:android', '--out', apk, work / 'aligned.apk')
    run(java / 'java.exe', '-jar', build_tools / 'lib/apksigner.jar', 'verify', apk)
    print(f'Built and verified: {apk}', flush=True)
    if args.install:
        run(sdk / 'platform-tools/adb.exe', 'install', '-r', apk)
        run(sdk / 'platform-tools/adb.exe', 'shell', 'am', 'start', '-n', 'com.shiftai.mobile/.MainActivity')


if __name__ == '__main__':
    main()
