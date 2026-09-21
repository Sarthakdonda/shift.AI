package com.shiftai.mobile;

import android.Manifest;
import android.app.Activity;
import android.app.DownloadManager;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.ConnectivityManager;
import android.net.LinkProperties;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.RouteInfo;
import android.net.Uri;
import android.net.wifi.WifiManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.View;
import android.webkit.*;
import android.webkit.CookieManager;
import android.widget.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.json.JSONObject;

/**
 * Hosts the dedicated app frontend (appfrontend), not the marketing website.
 * The shell only connects: the workspace inside decides which screen to show,
 * so the app never opens a landing page.
 */
public class MainActivity extends Activity {
    private static final int CANVAS = Color.rgb(251, 250, 248);
    private static final int LOCAL_NETWORK_PERMISSION = 43;
    private WebView web;
    private LinearLayout root;
    private String server;
    private ValueCallback<Uri[]> upload;
    private volatile boolean destroyed = false;
    private boolean connecting = false;
    private boolean offline = false;
    private String pagePath;
    private volatile Network localNetwork;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable retryConnection = () -> connect();

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        server = BuildConfig.LOCAL_MODE ? getPreferences(0).getString("server", BuildConfig.DEFAULT_SERVER) : BuildConfig.DEFAULT_SERVER;
        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(CANVAS);
        root.setOnApplyWindowInsetsListener((view, insets) -> {
            view.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
                insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            return insets;
        });
        web = new WebView(this);
        web.setBackgroundColor(CANVAS);
        // The app frame owns its own scrolling, so the system overscroll glow
        // would only make a native surface look like a web page.
        web.setOverScrollMode(View.OVER_SCROLL_NEVER);
        web.setVerticalScrollBarEnabled(false);
        web.setHorizontalScrollBarEnabled(false);
        WebSettings config = web.getSettings();
        config.setJavaScriptEnabled(true);
        config.setDomStorageEnabled(true);
        config.setAllowFileAccess(false);
        config.setAllowContentAccess(true);
        config.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        config.setUserAgentString(config.getUserAgentString() + " ShiftAIAndroid/1.2");
        CookieManager.getInstance().setAcceptCookie(true);
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if (workspaceUrl(uri)) return false;
                if ("https".equals(uri.getScheme()) || "http".equals(uri.getScheme()) || "mailto".equals(uri.getScheme())) {
                    try { startActivity(new Intent(Intent.ACTION_VIEW, uri)); }
                    catch (Exception ignored) { toast("No app can open this link."); }
                }
                return true;
            }
            @Override public void onPageFinished(WebView view, String url) {
                CookieManager.getInstance().flush();
                if (!offline && sameServer(Uri.parse(url))) {
                    Uri uri = Uri.parse(url);
                    pagePath = (uri.getEncodedPath() == null ? "/" : uri.getEncodedPath()) +
                        (uri.getEncodedQuery() == null ? "" : "?" + uri.getEncodedQuery());
                }
            }
            @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) {
                    Log.w("ShiftAI", "WebView error " + error.getErrorCode() + " for " + request.getUrl() + ": " + error.getDescription());
                    showOffline();
                }
            }
            @Override public void onReceivedHttpError(WebView view, WebResourceRequest request, WebResourceResponse response) {
                if (request.isForMainFrame() && response.getStatusCode() >= 500) {
                    Log.w("ShiftAI", "WebView HTTP " + response.getStatusCode() + " for " + request.getUrl());
                    showOffline();
                }
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (upload != null) upload.onReceiveValue(null);
                upload = callback;
                try { startActivityForResult(params.createIntent(), 42); }
                catch (Exception error) { upload.onReceiveValue(null); upload = null; toast("No file picker is available."); }
                return true;
            }
        });
        web.setDownloadListener((url, userAgent, disposition, mimeType, length) -> {
            if (!workspaceUrl(Uri.parse(url))) {
                toast("Open this export in your browser to download it.");
                return;
            }
            try {
                DownloadManager.Request request = new DownloadManager.Request(Uri.parse(url));
                String cookie = CookieManager.getInstance().getCookie(url);
                if (cookie != null) request.addRequestHeader("Cookie", cookie);
                request.addRequestHeader("User-Agent", userAgent);
                request.setMimeType(mimeType);
                request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, URLUtil.guessFileName(url, disposition, mimeType));
                ((DownloadManager)getSystemService(DOWNLOAD_SERVICE)).enqueue(request);
                toast("Downloading to Downloads.");
            } catch (Exception error) { toast("Download could not start. Please check your connection and try again."); }
        });
        root.addView(web, new LinearLayout.LayoutParams(-1,0,1));
        setContentView(root);
        getWindow().setBackgroundDrawable(new android.graphics.drawable.ColorDrawable(CANVAS));
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR | View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
        beginConnection();
    }

    private int appPort() { return BuildConfig.APP_PORT; }

    private boolean sameServer(Uri uri) {
        Uri base = Uri.parse(server);
        return base.getHost() != null && Objects.equals(base.getScheme(), uri.getScheme()) && Objects.equals(base.getHost(), uri.getHost()) && base.getPort() == uri.getPort();
    }

    private boolean workspaceUrl(Uri uri) {
        Uri base = Uri.parse(server);
        return sameServer(uri) || (BuildConfig.LOCAL_MODE && Objects.equals(base.getScheme(), uri.getScheme()) &&
            Objects.equals(base.getHost(), uri.getHost()) && uri.getPort() == BuildConfig.API_PORT &&
            uri.getPath() != null && uri.getPath().startsWith("/api/"));
    }

    private void toast(String message) { Toast.makeText(this, message, Toast.LENGTH_LONG).show(); }

    private boolean hasLocalNetworkPermission() {
        return !BuildConfig.LOCAL_MODE || Build.VERSION.SDK_INT < 33 ||
            checkSelfPermission(Manifest.permission.NEARBY_WIFI_DEVICES) == PackageManager.PERMISSION_GRANTED;
    }

    private void beginConnection() {
        if (!hasLocalNetworkPermission()) {
            showMessage("Allow nearby devices", "Shift AI needs nearby-device access to connect securely to your computer on this Wi-Fi network.");
            requestPermissions(new String[]{Manifest.permission.NEARBY_WIFI_DEVICES}, LOCAL_NETWORK_PERMISSION);
            return;
        }
        if (BuildConfig.LOCAL_MODE) showMessage("Opening your workspace", "Connecting to your computer over Wi-Fi…");
        connect();
    }

    private void connect() {
        if (connecting || destroyed) return;
        if (!hasLocalNetworkPermission()) {
            offline = true;
            showMessage("Nearby devices access is required", "Allow Nearby devices in Android Settings, then return to Shift AI.");
            return;
        }
        handler.removeCallbacks(retryConnection);
        if (!BuildConfig.LOCAL_MODE) { openServer(BuildConfig.DEFAULT_SERVER); return; }
        connecting = true;
        final String remembered = server;
        Log.i("ShiftAI", "Connecting; remembered=" + remembered + ", default=" + BuildConfig.DEFAULT_SERVER);
        new Thread(() -> {
            String found = reachable(remembered) ? remembered : null;
            if (found == null && !Objects.equals(remembered, BuildConfig.DEFAULT_SERVER) && reachable(BuildConfig.DEFAULT_SERVER)) found = BuildConfig.DEFAULT_SERVER;
            final String selected = found;
            runOnUiThread(() -> {
                if (destroyed) return;
                connecting = false;
                if (selected == null) {
                    Log.i("ShiftAI", "No remembered/default server reachable; starting discovery");
                    discover();
                } else {
                    Log.i("ShiftAI", "Opening " + selected);
                    openServer(selected);
                }
            });
        }, "shift-auto-connect").start();
    }

    private void openServer(String address) {
        server = address;
        offline = false;
        if (BuildConfig.LOCAL_MODE) getPreferences(0).edit().putString("server", address).apply();
        // The app frontend resolves the saved session itself and never shows a
        // landing page, so the shell always opens the root route.
        if (pagePath == null) pagePath = "/";
        web.loadUrl(server + pagePath);
    }

    /**
     * Android keeps a hotspot's client network separate from the cellular
     * default network. Bind local builds to the Wi-Fi route that can actually
     * reach the computer, whether this phone joined Wi-Fi or created it.
     */
    private void bindLocalNetwork(String address) {
        if (!BuildConfig.LOCAL_MODE || address == null || address.isEmpty()) return;
        try {
            InetAddress target = InetAddress.getByName(new URI(address).getHost());
            ConnectivityManager manager = (ConnectivityManager)getSystemService(CONNECTIVITY_SERVICE);
            for (Network candidate : manager.getAllNetworks()) {
                NetworkCapabilities capabilities = manager.getNetworkCapabilities(candidate);
                LinkProperties links = manager.getLinkProperties(candidate);
                if (capabilities == null || links == null || !capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) continue;
                for (RouteInfo route : links.getRoutes()) {
                    if (route.matches(target) && manager.bindProcessToNetwork(candidate)) {
                        localNetwork = candidate;
                        Log.i("ShiftAI", "Using local network " + links.getInterfaceName() + " for " + target.getHostAddress());
                        return;
                    }
                }
            }
        } catch (Exception error) {
            Log.w("ShiftAI", "Could not select a local network for " + address, error);
        }
    }

    private boolean reachable(String address) {
        if (address == null || address.isEmpty()) return false;
        HttpURLConnection health = null, frontend = null;
        try {
            URI base = new URI(address);
            if (!"http".equals(base.getScheme()) || base.getPort() != appPort() || !InetAddress.getByName(base.getHost()).isSiteLocalAddress()) {
                Log.w("ShiftAI", "Rejected local server address: " + address);
                return false;
            }
            bindLocalNetwork(address);
            URL healthUrl = new URL("http://" + base.getHost() + ":" + BuildConfig.API_PORT + "/api/health/live");
            health = (HttpURLConnection)(localNetwork == null ? healthUrl.openConnection() : localNetwork.openConnection(healthUrl));
            health.setConnectTimeout(1500); health.setReadTimeout(2000); health.setInstanceFollowRedirects(false);
            if (health.getResponseCode() != 200) {
                Log.w("ShiftAI", "Backend health returned " + health.getResponseCode() + " for " + address);
                return false;
            }
            java.io.ByteArrayOutputStream bytes = new java.io.ByteArrayOutputStream();
            try (java.io.InputStream input = health.getInputStream()) {
                byte[] buffer = new byte[1024]; int count;
                while ((count = input.read(buffer)) != -1 && bytes.size() < 16384) bytes.write(buffer, 0, count);
            }
            JSONObject json = new JSONObject(new String(bytes.toByteArray(), StandardCharsets.UTF_8));
            if (!json.has("gemini_configured") || !json.has("google_client_id")) {
                Log.w("ShiftAI", "Backend health response was incomplete for " + address);
                return false;
            }
            URL frontendUrl = new URL(address + "/login");
            frontend = (HttpURLConnection)(localNetwork == null ? frontendUrl.openConnection() : localNetwork.openConnection(frontendUrl));
            frontend.setConnectTimeout(1500); frontend.setReadTimeout(5000); frontend.setRequestMethod("HEAD");
            int status = frontend.getResponseCode();
            if (status != 200) Log.w("ShiftAI", "App frontend returned " + status + " for " + address);
            return status == 200;
        } catch (Exception error) {
            Log.w("ShiftAI", "Could not reach " + address, error);
            return false;
        }
        finally { if (health != null) health.disconnect(); if (frontend != null) frontend.disconnect(); }
    }

    private void showOffline() {
        offline = true;
        showMessage("Your workspace will be here shortly", BuildConfig.LOCAL_MODE ?
            "Keep your computer’s shiftAI servers running and both devices on the same Wi-Fi. We’ll reconnect automatically." :
            "Check your internet connection. We’ll reconnect automatically.");
        handler.removeCallbacks(retryConnection);
        handler.postDelayed(retryConnection, 5000);
    }

    private void showMessage(String title, String message) {
        web.loadDataWithBaseURL(null, "<html><meta name='viewport' content='width=device-width,initial-scale=1'>"
            + "<body style='margin:0;background:#fbfaf8;color:#141b23;font:15px/1.5 -apple-system,Roboto,sans-serif;"
            + "display:grid;place-items:center;min-height:100vh;-webkit-user-select:none'>"
            + "<main style='padding:28px;max-width:360px;text-align:center'>"
            + "<div style='width:64px;height:64px;margin:0 auto 20px;border-radius:22px;background:#fff1e0'></div>"
            + "<h2 style='margin:0 0 8px;font-size:19px;font-weight:600;letter-spacing:-.02em'>" + title + "</h2>"
            + "<p style='margin:0;line-height:1.6;color:#79838f;font-size:14px'>" + message + "</p>"
            + "</main></body></html>", "text/html", "UTF-8", null);
    }

    private void discover() {
        if (connecting || destroyed) return;
        connecting = true;
        new Thread(() -> {
            LinkedHashSet<String> found = new LinkedHashSet<>();
            WifiManager.MulticastLock lock = null;
            try {
                WifiManager wifi = (WifiManager)getApplicationContext().getSystemService(WIFI_SERVICE);
                lock = wifi.createMulticastLock("shift-discovery");
                lock.acquire();
                String nonce = UUID.randomUUID().toString();
                byte[] query = new JSONObject().put("service", "shift-ai-discover-v1").put("nonce", nonce).toString().getBytes(StandardCharsets.UTF_8);
                try (DatagramSocket socket = new DatagramSocket()) {
                    socket.setBroadcast(true);
                    socket.setSoTimeout(600);
                    Set<InetAddress> destinations = new HashSet<>();
                    destinations.add(InetAddress.getByName("255.255.255.255"));
                    for (NetworkInterface net : Collections.list(NetworkInterface.getNetworkInterfaces()))
                        for (InterfaceAddress addr : net.getInterfaceAddresses())
                            if (addr.getBroadcast() != null) destinations.add(addr.getBroadcast());
                    long deadline = System.currentTimeMillis() + 4000;
                    long nextSend = 0;
                    while (!destroyed && System.currentTimeMillis() < deadline) {
                        if (System.currentTimeMillis() >= nextSend) {
                            for (InetAddress destination : destinations)
                                try { socket.send(new DatagramPacket(query, query.length, destination, 45831)); } catch (Exception ignored) { }
                            nextSend = System.currentTimeMillis() + 1200;
                        }
                        DatagramPacket reply = new DatagramPacket(new byte[2048], 2048);
                        try {
                            socket.receive(reply);
                            JSONObject json = new JSONObject(new String(reply.getData(), 0, reply.getLength(), StandardCharsets.UTF_8));
                            if (nonce.equals(json.optString("nonce")) && "shift-ai-discover-v1".equals(json.optString("service"))
                                && json.optInt("app_port") == appPort() && json.optInt("api_port") == BuildConfig.API_PORT
                                && reply.getAddress().isSiteLocalAddress())
                                found.add("http://" + reply.getAddress().getHostAddress() + ":" + appPort());
                        } catch (Exception ignored) { }
                    }
                }
            } catch (Exception ignored) { }
            finally { if (lock != null && lock.isHeld()) lock.release(); }
            String available = null;
            for (String candidate : found) { if (reachable(candidate)) { available = candidate; break; } }
            final String selected = available;
            runOnUiThread(() -> {
                connecting = false;
                if (destroyed) return;
                if (selected == null) showOffline(); else openServer(selected);
            });
        }, "shift-discovery").start();
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request == 42 && upload != null) {
            upload.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(result, data));
            upload = null;
        }
    }
    @Override public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(requestCode, permissions, results);
        if (requestCode != LOCAL_NETWORK_PERMISSION) return;
        if (results.length > 0 && results[0] == PackageManager.PERMISSION_GRANTED) {
            offline = false;
            beginConnection();
        } else {
            offline = true;
            showMessage("Nearby devices access is required", "Allow Nearby devices in Android Settings, then return to Shift AI.");
        }
    }
    @Override public void onBackPressed() { if (!offline && web.canGoBack()) web.goBack(); else super.onBackPressed(); }
    @Override protected void onResume() { super.onResume(); if (offline && hasLocalNetworkPermission()) connect(); }
    @Override protected void onPause() { super.onPause(); CookieManager.getInstance().flush(); }
    @Override protected void onDestroy() {
        destroyed = true;
        handler.removeCallbacksAndMessages(null);
        if (upload != null) upload.onReceiveValue(null);
        root.removeView(web);
        web.destroy();
        super.onDestroy();
    }
}
