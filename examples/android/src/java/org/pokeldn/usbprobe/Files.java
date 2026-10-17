package org.pokeldn.usbprobe;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;
import java.io.File;
import java.io.FileNotFoundException;
import java.io.IOException;

/** Read-only access to files under the app's private folder, for the share sheet; androidx's FileProvider without androidx. */
public final class Files extends ContentProvider {
    static Uri uri(Context context, File file) {
        return new Uri.Builder().scheme("content").authority(context.getPackageName() + ".files")
            .path(file.getAbsolutePath()).build();
    }

    private File file(Uri uri) throws FileNotFoundException {
        try {
            File file = new File(uri.getPath()).getCanonicalFile();
            File root = getContext().getFilesDir().getCanonicalFile();
            if (!file.getPath().startsWith(root.getPath() + File.separator) || !file.isFile()) throw new FileNotFoundException(uri.toString());
            return file;
        } catch (IOException error) { throw new FileNotFoundException(uri.toString()); }
    }

    @Override public ParcelFileDescriptor openFile(Uri uri, String mode) throws FileNotFoundException {
        return ParcelFileDescriptor.open(file(uri), ParcelFileDescriptor.MODE_READ_ONLY);
    }

    @Override public Cursor query(Uri uri, String[] projection, String selection, String[] args, String order) {
        try {
            File file = file(uri);
            MatrixCursor cursor = new MatrixCursor(new String[] {OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE});
            cursor.addRow(new Object[] {file.getName(), file.length()});
            return cursor;
        } catch (FileNotFoundException error) { return null; }
    }

    @Override public String getType(Uri uri) { return "application/octet-stream"; }
    @Override public boolean onCreate() { return true; }
    @Override public Uri insert(Uri uri, ContentValues values) { return null; }
    @Override public int delete(Uri uri, String selection, String[] args) { return 0; }
    @Override public int update(Uri uri, ContentValues values, String selection, String[] args) { return 0; }
}
