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
        });
        web.loadDataWithBaseURL(null, "<html><body style='background:#0b0b0d'></body></html>", "text/html", "utf-8", null);
        // Android 15 draws apps edge to edge: keep the page clear of the status, navigation and keyboard areas.
        android.widget.FrameLayout frame = new android.widget.FrameLayout(this);
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
                    new Handler(Looper.getMainLooper()).post(() -> web.loadUrl("http://127.0.0.1:" + PORT + "/"));
                    return;
                }
            } catch (Exception ignored) { }
            try { Thread.sleep(200); } catch (InterruptedException error) { return; }
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
