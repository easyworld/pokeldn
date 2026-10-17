package org.pokeldn.usbprobe;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.View;
import android.view.WindowInsets;
import android.view.Window;
import android.webkit.*;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import java.net.HttpURLConnection;
import java.net.URL;

/** The app: the desktop interface (gui/main.py) served by the embedded Python, shown full screen. */
public class PokeldnActivity extends Activity {
    private static final String TAG = "PokeLDN";
    static final int PORT = 8550;
    private static final int PICK = 10;
    private WebView web;
    private ValueCallback<Uri[]> picking;
    private android.widget.FrameLayout frame;
    private View notice;
    private final Handler main = new Handler(Looper.getMainLooper());
    private boolean probed, serverUp, loaded, firstFrame;

    @SuppressLint("SetJavaScriptEnabled")
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        Window window = getWindow();
        window.setStatusBarColor(0xff0b0b0d);
        window.setNavigationBarColor(0xff0b0b0d);
        Bridge.attach(this);
        web = new WebView(this);
        web.setBackgroundColor(0xff0b0b0d);
        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        // WebView copies the system font size into text zoom; above 100% Flutter draws text so large that
        // every screen is blank (examples/android/README.md, WebView).
        settings.setTextZoom(100);
        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (picking != null) picking.onReceiveValue(null);
                picking = callback;
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*");
                if (params.getMode() == FileChooserParams.MODE_OPEN_MULTIPLE) intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
                startActivityForResult(intent, PICK);
                return true;
            }
            @Override public boolean onConsoleMessage(ConsoleMessage message) {
                Log.d(TAG, "web: " + message.message());
                return true;
            }
        });
        web.setWebViewClient(new WebViewClient() {
            // Links out of the app (docs, GitHub) open in the browser.
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if ("127.0.0.1".equals(uri.getHost())) return false;
                startActivity(new Intent(Intent.ACTION_VIEW, uri));
                return true;
            }
            @Override public void onPageFinished(WebView view, String url) {
                if (!probed && !url.startsWith("http")) probe();
            }
        });
        web.loadDataWithBaseURL(null, "<html><body style='background:#0b0b0d'></body></html>", "text/html", "utf-8", null);
        // Android 15 draws apps edge to edge: keep the page clear of the status, navigation and keyboard areas.
        frame = new android.widget.FrameLayout(this);
        frame.setBackgroundColor(0xff0b0b0d);
        frame.addView(web);
        frame.setOnApplyWindowInsetsListener((view, insets) -> {
            if (android.os.Build.VERSION.SDK_INT >= 30) {
                android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.ime());
                view.setPadding(bars.left, bars.top, bars.right, bars.bottom);
                return WindowInsets.CONSUMED;
            }
            return insets;
        });
        setContentView(frame);
        startServer();
    }

    private void startServer() {
        String files = getFilesDir().getAbsolutePath(), natives = getApplicationInfo().nativeLibraryDir;
        new Thread(() -> {
            try {
                if (!Python.isStarted()) Python.start(new AndroidPlatform(getApplicationContext()));
                Python.getInstance().getModule("android_gui").callAttr("serve", PORT, files, natives);
            } catch (Exception error) { Log.e(TAG, "The interface stopped", error); }
        }, "pokeldn-gui").start();
        new Thread(this::waitForServer, "pokeldn-wait").start();
        if (getIntent().getBooleanExtra("selftest", false)) new Thread(() -> {
            try {
                while (!Python.isStarted()) Thread.sleep(100);
                Thread.sleep(15000);   // the interface has set the environment up
                for (String line : Python.getInstance().getModule("android_selftest").callAttr("run",
                        getIntent().getStringExtra("only") == null ? "" : getIntent().getStringExtra("only")).toString().split("\n"))
                    Log.i(TAG, "selftest " + line);
            } catch (Exception error) { Log.e(TAG, "selftest", error); }
        }, "pokeldn-selftest").start();
    }

    private void waitForServer() {
        for (int attempt = 0; attempt < 600; attempt++) {
            try {
                HttpURLConnection connection = (HttpURLConnection)new URL("http://127.0.0.1:" + PORT + "/").openConnection();
                connection.setConnectTimeout(500);
                if (connection.getResponseCode() == 200) {
                    main.post(() -> { serverUp = true; loadInterface(); });
                    return;
                }
            } catch (Exception ignored) { }
            try { Thread.sleep(200); } catch (InterruptedException error) { return; }
        }
    }

    // Flutter's web engine picks skwasm only with WasmGC (Chrome 119) and WebGL, else CanvasKit,
    // which draws no image in this interface (examples/android/README.md, WebView).
    private static final int MIN_WEBVIEW = 119;
    private static final String PROBE = "(function(){var gc=false;try{gc=WebAssembly.validate(new Uint8Array("
            + "[0,97,115,109,1,0,0,0,1,5,1,95,1,120,0]))}catch(e){}var c=document.createElement('canvas');"
            + "var gl=!!(c.getContext('webgl2')||c.getContext('webgl'));return (gc?'G':'-')+(gl?'W':'-')})()";

    private void probe() {
        probed = true;
        web.evaluateJavascript(PROBE, result -> {
            String found = result == null ? "" : result.replace("\"", "");
            PackageInfoLine info = PackageInfoLine.current();
            Log.i(TAG, "WebView " + info.text + ", WasmGC " + found.contains("G") + ", WebGL " + found.contains("W"));
            boolean old = info.major > 0 && info.major < MIN_WEBVIEW;
            if (!found.contains("G") || !found.contains("W") || old || getIntent().getBooleanExtra("oldwebview", false))
                showNotice("Update Android System WebView",
                        "pokeldn draws its screens with Android System WebView, and the version on this phone is too old "
                        + "or cannot use the graphics features they need. The app may show blank screens or no text.\n\n"
                        + "Update Android System WebView (and Google Chrome) from the Play Store, then open pokeldn again.",
                        info, false);
            else loadInterface();
        });
    }

    private void loadInterface() {
        if (!serverUp || !probed || loaded || notice != null) return;
        loaded = true;
        web.loadUrl("http://127.0.0.1:" + PORT + "/");
        watchFirstFrame(0);
    }

    /** The page's loading spinner leaves at Flutter's first frame (flutter_bootstrap.js). */
    private void watchFirstFrame(int seconds) {
        main.postDelayed(() -> web.evaluateJavascript("document.getElementById('loading')===null", drawn -> {
            if ("true".equals(drawn)) {
                firstFrame = true;
                if (notice != null && seconds >= 60) hideNotice();
                return;
            }
            if (seconds == 60 && notice == null)
                showNotice("The interface has not started",
                        "pokeldn has been loading for a minute. On some phones an outdated Android System WebView keeps "
                        + "the screen blank.\n\nUpdate Android System WebView from the Play Store, or keep waiting.",
                        PackageInfoLine.current(), true);
            if (seconds < 600) watchFirstFrame(seconds + 2);
        }), 2000);
    }

    private void showNotice(String heading, String body, PackageInfoLine info, boolean waiting) {
        android.widget.LinearLayout box = new android.widget.LinearLayout(this);
        box.setOrientation(android.widget.LinearLayout.VERTICAL);
        box.setBackgroundColor(0xff0b0b0d);
        box.setGravity(android.view.Gravity.CENTER_VERTICAL);
        int pad = dp(28);
        box.setPadding(pad, pad, pad, pad);
        box.setClickable(true);
        android.widget.ImageView logo = new android.widget.ImageView(this);
        logo.setImageResource(R.mipmap.ic_launcher);
        box.addView(logo, new android.widget.LinearLayout.LayoutParams(dp(64), dp(64)));
        box.addView(text(heading, 24, 0xffffffff, dp(20)));
        box.addView(text(body, 15, 0xffb4b4bc, dp(12)));
        box.addView(text("WebView: " + info.text, 13, 0xff7a7a84, dp(12)));
        box.addView(button("Update Android System WebView", true, v -> openStore(info.name)), wide(dp(28)));
        if (waiting) box.addView(button("Keep waiting", false, v -> hideNotice()), wide(dp(10)));
        else box.addView(button("Continue anyway", false, v -> { hideNotice(); loadInterface(); }), wide(dp(10)));
        notice = box;
        frame.addView(box);
    }

    private void hideNotice() {
        if (notice != null) frame.removeView(notice);
        notice = null;
    }

    private void openStore(String name) {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse("market://details?id=" + name)));
        } catch (android.content.ActivityNotFoundException error) {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse("https://play.google.com/store/apps/details?id=" + name)));
        }
    }

    private android.widget.TextView text(String value, int size, int color, int top) {
        android.widget.TextView view = new android.widget.TextView(this);
        view.setText(value);
        view.setTextSize(size);
        view.setTextColor(color);
        view.setPadding(0, top, 0, 0);
        view.setLineSpacing(0, 1.2f);
        return view;
    }

    private android.widget.Button button(String label, boolean filled, View.OnClickListener click) {
        android.widget.Button view = new android.widget.Button(this);
        view.setText(label);
        view.setAllCaps(false);
        view.setTextSize(15);
        view.setTextColor(filled ? 0xff0b0b0d : 0xffffffff);
        android.graphics.drawable.GradientDrawable shape = new android.graphics.drawable.GradientDrawable();
        shape.setCornerRadius(dp(24));
        shape.setColor(filled ? 0xff47aefa : 0x17ffffff);
        view.setBackground(shape);
        view.setOnClickListener(click);
        return view;
    }

    private android.widget.LinearLayout.LayoutParams wide(int top) {
        android.widget.LinearLayout.LayoutParams params =
                new android.widget.LinearLayout.LayoutParams(android.widget.LinearLayout.LayoutParams.MATCH_PARENT, dp(48));
        params.topMargin = top;
        return params;
    }

    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }

    /** The WebView provider the system uses: its package (the Play Store page) and version. */
    static final class PackageInfoLine {
        final String name, text;
        final int major;
        PackageInfoLine(String name, String text, int major) { this.name = name; this.text = text; this.major = major; }
        static PackageInfoLine current() {
            android.content.pm.PackageInfo info = WebView.getCurrentWebViewPackage();
            if (info == null) return new PackageInfoLine("com.google.android.webview", "none", 0);
            int major = 0;
            try { major = Integer.parseInt(info.versionName.split("\\.")[0]); } catch (RuntimeException ignored) { }
            return new PackageInfoLine(info.packageName, info.packageName + " " + info.versionName, major);
        }
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (Bridge.onResult(request, result, data)) return;
        if (request != PICK || picking == null) return;
        Uri[] chosen = null;
        if (result == RESULT_OK && data != null) {
            if (data.getClipData() != null) {
                chosen = new Uri[data.getClipData().getItemCount()];
                for (int i = 0; i < chosen.length; i++) chosen[i] = data.getClipData().getItemAt(i).getUri();
            } else if (data.getData() != null) chosen = new Uri[] {data.getData()};
        }
        picking.onReceiveValue(chosen);
        picking = null;
    }

    @Override public void onBackPressed() {
        if (web.canGoBack()) web.goBack();
        else moveTaskToBack(true);
    }

    @Override protected void onResume() { super.onResume(); Bridge.refresh(); }
}
