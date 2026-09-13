package com.shiftai.mobile;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.DownloadManager;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.net.wifi.WifiManager;
import android.os.Bundle;
import android.os.Environment;
import android.view.View;
import android.webkit.*;
import android.webkit.CookieManager;
import android.widget.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.json.JSONObject;

/** A local-server companion. The server keeps all business data and AI credentials. */
public class MainActivity extends Activity {
    private WebView web;
    private LinearLayout root;
    private TextView status;
    private String server;
    private ValueCallback<Uri[]> upload;
    private boolean destroyed = false;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        server = getPreferences(0).getString("server", BuildConfig.DEFAULT_SERVER);
        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(255,244,230));
        root.setOnApplyWindowInsetsListener((view, insets) -> {
            view.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
                insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            return insets;
        });
        LinearLayout bar = new LinearLayout(this);
        bar.setGravity(android.view.Gravity.CENTER_VERTICAL);
        status = new TextView(this);
        status.setText("Shift AI");
        status.setTextColor(Color.rgb(11,19,32));
        status.setPadding(20,0,4,0);
        bar.addView(status, new LinearLayout.LayoutParams(0,52,1));
        Button retry = new Button(this);
        retry.setText("Retry");
        retry.setOnClickListener(v -> connect());
        bar.addView(retry);
        Button settings = new Button(this);
        settings.setText("Server");
        settings.setOnClickListener(v -> showServer());
        bar.addView(settings);
        root.addView(bar);
        web = new WebView(this);
        web.setBackgroundColor(Color.rgb(255,244,230));
        WebSettings config = web.getSettings();
        config.setJavaScriptEnabled(true);
        config.setDomStorageEnabled(true);
        config.setAllowFileAccess(false);
        config.setAllowContentAccess(true);
        config.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
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
                if (sameServer(Uri.parse(url))) status.setText("Shift AI · Wi-Fi");
            }
            @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) showOffline();
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
                toast("For browser-generated exports, open this server address in Chrome.");
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
            } catch (Exception error) { toast("Download could not start. Open this server in Chrome to export."); }
        });
        root.addView(web, new LinearLayout.LayoutParams(-1,0,1));
        setContentView(root);
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR | View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
        connect();
    }

    private boolean sameServer(Uri uri) {
        Uri base = Uri.parse(server);
        return Objects.equals(base.getScheme(), uri.getScheme()) && Objects.equals(base.getHost(), uri.getHost()) && base.getPort() == uri.getPort();
    }

    private boolean workspaceUrl(Uri uri) {
        Uri base = Uri.parse(server);
        return sameServer(uri) || (Objects.equals(base.getScheme(), uri.getScheme()) &&
            Objects.equals(base.getHost(), uri.getHost()) && uri.getPort() == 8000 &&
            uri.getPath() != null && uri.getPath().startsWith("/api/"));
    }

    private void toast(String message) { Toast.makeText(this, message, Toast.LENGTH_LONG).show(); }

    private void connect() {
        if (server.isEmpty()) { showOffline(); showServer(); return; }
        status.setText("Connecting…");
        String current = web.getUrl();
        // A slow or unavailable database must not prevent the sign-in page loading.
        web.loadUrl(current != null && sameServer(Uri.parse(current)) ? current : server + "/login");
    }

    private void showOffline() {
        status.setText("Server offline");
        web.loadDataWithBaseURL(null,
            "<html><meta name='viewport' content='width=device-width,initial-scale=1'><body style='background:#fff4e6;color:#0b1320;font:17px sans-serif;padding:32px'>" +
            "<h1>Connect to Shift AI</h1><p>Start <b>start-wifi.cmd</b> on your computer and keep it running.</p>" +
            "<p>Connect both devices to the same Wi-Fi, then tap <b>Retry</b>.</p><p>If your computer's address changed, tap <b>Server → Find server</b>.</p>" +
            "<p>Your saved projects stay on the server. USB is not needed.</p></body></html>", "text/html", "UTF-8", null);
    }

    private void showServer() {
        EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setInputType(android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_VARIATION_URI);
        input.setText(server);
        input.setHint("http://192.168.1.10:3000");
        new AlertDialog.Builder(this).setTitle("Wi-Fi server")
            .setMessage("Use the address printed by start-wifi.cmd. Sign in with your existing email account.")
            .setView(input).setPositiveButton("Connect", (dialog, which) -> {
                try {
                    String value = input.getText().toString().trim();
                    if (!value.contains("://")) value = "http://" + value;
                    URI uri = new URI(value);
                    if (!"http".equals(uri.getScheme()) || uri.getHost() == null || uri.getUserInfo() != null ||
                        uri.getQuery() != null || uri.getFragment() != null ||
                        (uri.getPath() != null && !uri.getPath().isEmpty() && !uri.getPath().equals("/"))) throw new Exception();
                    saveServer(new URI("http", null, uri.getHost(), uri.getPort() == -1 ? 3000 : uri.getPort(), null, null, null).toString());
                } catch (Exception error) { toast("Enter an address such as http://192.168.1.10:3000"); }
            }).setNeutralButton("Find server", (dialog, which) -> discover())
            .setNegativeButton("Cancel", null).show();
    }

    private void saveServer(String value) {
        server = value;
        getPreferences(0).edit().putString("server", value).apply();
        web.clearHistory();
        connect();
    }

    private void discover() {
        status.setText("Finding server…");
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
                    while (System.currentTimeMillis() < deadline) {
                        if (System.currentTimeMillis() >= nextSend) {
                            for (InetAddress destination : destinations)
                                try { socket.send(new DatagramPacket(query, query.length, destination, 45831)); } catch (Exception ignored) { }
                            nextSend = System.currentTimeMillis() + 1200;
                        }
                        DatagramPacket reply = new DatagramPacket(new byte[2048], 2048);
                        try {
                            socket.receive(reply);
                            JSONObject json = new JSONObject(new String(reply.getData(), 0, reply.getLength(), StandardCharsets.UTF_8));
                            if (nonce.equals(json.optString("nonce")) && "shift-ai-discover-v1".equals(json.optString("service")) && json.optInt("port") == 3000 && json.optInt("api_port") == 8000 && reply.getAddress().isSiteLocalAddress())
                                found.add("http://" + reply.getAddress().getHostAddress() + ":3000");
                        } catch (Exception ignored) { }
                    }
                }
            } catch (Exception ignored) { }
            finally { if (lock != null && lock.isHeld()) lock.release(); }
            runOnUiThread(() -> {
                if (destroyed) return;
                status.setText("Shift AI");
                if (found.isEmpty()) {
                    new AlertDialog.Builder(this).setTitle("No server found")
                        .setMessage("Start start-wifi.cmd, check that both devices use the same Wi-Fi, and allow Shift AI through Windows Firewall. You can also enter the computer address manually.")
                        .setPositiveButton("Enter address", (d,w) -> showServer()).setNegativeButton("Cancel", null).show();
                } else {
                    String[] addresses = found.toArray(new String[0]);
                    new AlertDialog.Builder(this).setTitle("Choose your computer")
                        .setItems(addresses, (d,w) -> saveServer(addresses[w])).setNegativeButton("Cancel", null).show();
                }
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
    @Override public void onBackPressed() { if (web.canGoBack()) web.goBack(); else super.onBackPressed(); }
    @Override protected void onPause() { super.onPause(); CookieManager.getInstance().flush(); }
    @Override protected void onDestroy() {
        destroyed = true;
        if (upload != null) upload.onReceiveValue(null);
        root.removeView(web);
        web.destroy();
        super.onDestroy();
    }
}
