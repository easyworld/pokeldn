package org.pokeldn.usbprobe;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;

/** Keeps the app in the foreground while a run holds the board, so Android does not stop the
 *  embedded Python mid-trade when the screen locks or the player switches apps. */
public final class RunService extends Service {
    private static final String CHANNEL = "runs";
    static final String STOP = "org.pokeldn.usbprobe.STOP_RUN";

    @Override public int onStartCommand(Intent intent, int flags, int id) {
        NotificationManager notifications = getSystemService(NotificationManager.class);
        if (Build.VERSION.SDK_INT >= 26)
            notifications.createNotificationChannel(new NotificationChannel(CHANNEL, "Sessions", NotificationManager.IMPORTANCE_LOW));
        PendingIntent open = PendingIntent.getActivity(this, 0, new Intent(this, PokeldnActivity.class),
            PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder builder = Build.VERSION.SDK_INT >= 26 ? new Notification.Builder(this, CHANNEL) : new Notification.Builder(this);
        Notification note = builder.setContentTitle("pokeldn").setContentText("A session is running with the board.")
            .setSmallIcon(android.R.drawable.stat_sys_data_bluetooth).setContentIntent(open).setOngoing(true).build();
        try {
            if (Build.VERSION.SDK_INT >= 29) startForeground(1, note, ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE);
            else startForeground(1, note);
        } catch (RuntimeException error) {
            // Android 14 grants a connected-device service only with USB access to a device; without it the run goes on unprotected.
            android.util.Log.w("PokeLDN", "No foreground service: " + error);
            stopSelf();
            return START_NOT_STICKY;
        }
        // A stop is a start with STOP: Android crashes an app whose foreground service ends before
        // startForeground, which a run shorter than the service's start would otherwise cause.
        if (intent != null && STOP.equals(intent.getAction())) {
            if (Build.VERSION.SDK_INT >= 24) stopForeground(STOP_FOREGROUND_REMOVE);
            stopSelf();
        }
        return START_NOT_STICKY;
    }

    @Override public IBinder onBind(Intent intent) { return null; }
}
