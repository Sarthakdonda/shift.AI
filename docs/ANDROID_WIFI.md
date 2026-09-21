# shiftAI on Android

The Android app loads **`appfrontend`**, a dedicated phone application surface,
not the marketing website. It opens straight into the workspace: there is no
landing page, no server picker, no Connect button and no native toolbar. See
[appfrontend/README.md](../appfrontend/README.md) for what the app contains.

Ports: the app frontend uses TCP **3100**, the API uses TCP **8000**, and
automatic discovery uses UDP **45831**. The website on 3000/3001 is a separate
surface and is not needed by the phone.

## Download from the website

Choose **Android app** on the landing page, then **Download for Android**.
Open the APK and allow installation from that browser when Android asks.
Android 8 or later is required.

The public app opens the hosted app frontend, so users need internet but not
your computer, Wi-Fi network, or any server configuration. Sign in with an email
account to reach saved projects. This is a connected app, not an offline copy.
Google web sign-in requires a full browser; use the website in Chrome for it.

## Your installed Wi-Fi app

1. Connect your computer and phone to the same Wi-Fi or shared hotspot.
2. Double-click `start-wifi.cmd` and keep the servers running. It starts the
   API on 8000 and the app frontend on 3100.
3. Open **Shift AI**. It connects automatically and sign-in cookies persist.

The first launch may show one Windows administrator prompt. It creates only
three inbound rules for TCP 3100, TCP 8000 and UDP 45831, restricted to
`LocalSubnet`. Windows Firewall stays enabled, no network is switched between
Public and Private, and internet hosts cannot use these rules. Later launches
do not prompt while those rules remain present. The setup also removes the two
blanket Public-profile Node.js rules that Windows may have created for all ports;
other applications' firewall rules are not changed.

The app checks the remembered computer, then discovers a running shiftAI server
if the address changed. If the servers are unavailable it shows a short
connection message and retries automatically. It never silently switches local
work to the hosted service. Starting the servers is sufficient; USB is only
needed for the first installation.

For separate terminals, start the backend with `python run.py --lan` from
`backend`, and the app with `npm.cmd run dev -- --hostname 0.0.0.0 --port 3100`
from `appfrontend`. The launcher leaves existing servers alone. If your existing
backend was started without `--lan`, restart it yourself with that option.

Wi-Fi must permit device-to-device connections. The launcher handles the narrow
Windows Firewall rules; no router port forwarding or profile change is needed.
Guest-network isolation can still prevent devices from communicating.

**Upgrading from version 1.1:** the shell now looks for the app frontend on
3100 and requires the `app_port` field that the current backend advertises.
Rebuild and reinstall with `--install` after updating; an older APK keeps
looking for the website on 3000.

## Build and install

Requires JDK 21, Android SDK platform 36 and build-tools 36.0.0. Environment
variables `JAVA_HOME`, `ANDROID_HOME` or `ANDROID_SDK_ROOT` can override defaults.

For the personal Wi-Fi app (the initial address is optional; discovery finds the
computer either way):

```powershell
backend/.venv/Scripts/python.exe tools/build_android.py --local --install
backend/.venv/Scripts/python.exe tools/build_android.py --local --server http://YOUR_PC_IP:3100 --install
```

`--server` must point at port 3100; the build rejects the website port so an APK
cannot be shipped pointing at the wrong surface.

For the downloadable hosted app:

```powershell
backend/.venv/Scripts/python.exe tools/build_android.py --publish
```

That builds and verifies `android/dist/shift-ai.apk`, then copies it to
`frontend/public/downloads/shift-ai.apk`. Deploy the frontend to publish an
update. The build command rejects publishing a local-server APK.

**The hosted app needs its own deployment.** `appfrontend` is a separate Next.js
project, so deploy it separately and point the build at it:

```powershell
$env:SHIFT_APP_URL='https://your-app-deployment.example'
backend/.venv/Scripts/python.exe tools/build_android.py --publish
```

The default is `https://shiftai-app.vercel.app`. Set `NEXT_PUBLIC_API_BASE_URL`
on that deployment to the backend, and add its origin to `CORS_ORIGINS`.

Both variants share the same application ID and signing key, so installing one
replaces the other while preserving app data. Rebuild the personal variant with
`--install` afterwards to leave it on your phone.

The signing key is stored only in `.local/android/shift-local.keystore`. Back it
up privately and retain it for updates. Do not commit it. The APK contains neither
AI-provider secrets nor database credentials. Build intermediates are stored in
`.local/android/build`. The public APK is intentionally tracked for deployment.

## What the shell does

- Opens `/` and lets the app decide the screen; it never guesses `/login` or
  `/dashboard`.
- Reports `ShiftAIAndroid/1.2` in the user agent, which the app uses to route
  deliverable downloads through Android's download manager.
- Disables overscroll glow and scrollbars, because the app frame owns scrolling.
- Pads for system window insets, so the keyboard resizes the app instead of
  covering the composer.
- File selection supports document uploads. Deliverable and blueprint downloads
  use authenticated file URLs and are saved to Android Downloads.

Use Chrome for features the embedded browser does not support.
