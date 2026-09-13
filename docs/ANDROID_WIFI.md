# Shift AI on Android over Wi-Fi

The Android companion loads the workspace from your computer. USB is needed only
for the initial APK installation, not everyday use. Keep the computer awake and
connect both devices to the same Wi-Fi (a shared hotspot also works if it permits
devices to communicate).

## Everyday startup

1. Double-click `start-wifi.cmd` in the project root and keep its window open.
2. Open **Shift AI** on the phone and sign in with your existing email account.
3. If the address changed, tap **Server → Find server**, then select your computer.
   Alternatively, enter the `http://...:3000` address printed by the launcher.

From PowerShell you can also run `./start-wifi.cmd`. For separate terminals:

```powershell
cd D:\shiftAI\backend
python run.py --lan
```

```powershell
cd D:\shiftAI\frontend
npm.cmd run dev -- --hostname 0.0.0.0 --port 3000
```

The launcher leaves existing servers alone. If an existing backend was started
without `--lan`, restart that backend yourself using the command above. Ctrl+C
in the launcher stops only the processes that launcher created.

The phone uses TCP 3000 for the interface and TCP 8000 for the API. Find server
uses UDP 45831. No router port forwarding or wireless ADB setup is required.
The setup does not change Windows Firewall. If discovery is blocked but the web
ports work, enter the server address manually. Guest Wi-Fi/client isolation can
block device-to-device traffic even when both devices use the same network name.

## App behavior

- The server address and sign-in cookies persist across app launches.
- **Retry** reloads the current page; **Server** lets you change computers.
- File selection supports document uploads. Ordinary HTTP downloads go to Android
  Downloads. Browser-generated blob exports should be opened in Chrome using the
  same server address; the app displays this instruction when needed.
- This local HTTP setup uses email sign-in. Google sign-in requires a supported
  browser and configured secure web origin.
- Stopping the computer server makes the app unavailable. It is not an offline
  copy, and the APK contains no database credentials or AI provider keys.
- Existing projects remain in the same database, associated with the same account.

## Rebuild or reinstall

With JDK 21, Android SDK platform 36, and build-tools 36.0.0 installed:

```powershell
backend/.venv/Scripts/python.exe tools/build_android.py --server http://YOUR_PC_IP:3000 --install
```

`ANDROID_HOME`/`ANDROID_SDK_ROOT` and `JAVA_HOME` can override the default local
tool paths. The default paths target this Windows workspace. The APK is written
to `android/dist/shift-ai.apk`. It can also be copied to the phone and installed
with Android's package installer.

The local development signing key lives in `.local/android/shift-local.keystore`.
Keep it to install future updates without uninstalling the app. It uses a standard
development password and is not a production distribution key. Build intermediates
are in `.local/android/build`. Both the signing key and APK output are ignored by Git.

The companion follows Android's [WebView guide](https://developer.android.com/develop/ui/views/layout/webapps/webview)
and uses the SDK's [AAPT2](https://developer.android.com/tools/aapt2), D8 and
[APK signer](https://developer.android.com/tools/apksigner).
