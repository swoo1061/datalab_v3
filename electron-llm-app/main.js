const {
  app,
  BrowserWindow,
  ipcMain,
  Menu,
  globalShortcut,
  session,
  shell,
} = require("electron");
const { execFile } = require("child_process");
const { autoUpdater } = require("electron-updater");
const fs = require("fs");
const path = require("path");

let win;
let sessionKey = null;

function execFileAsync(command, args) {
  return new Promise((resolve, reject) => {
    execFile(command, args, (err, stdout, stderr) => {
      if (err) {
        reject(err);
        return;
      }
      resolve({ stdout, stderr });
    });
  });
}

function getApiBase() {
  return (process.env.DATALAB_API_BASE || process.env.API_BASE || "http://127.0.0.1:8000").replace(/\/$/, "");
}

function loadApiBaseFromEnvFile() {
  if (process.env.DATALAB_API_BASE || process.env.API_BASE) return;
  const candidates = [
    path.join(__dirname, ".env"),
    path.join(__dirname, "..", ".env"),
  ];
  for (const filePath of candidates) {
    if (!fs.existsSync(filePath)) continue;
    const content = fs.readFileSync(filePath, "utf8");
    for (const rawLine of content.split(/\r?\n/)) {
      const line = rawLine.trim();
      if (!line || line.startsWith("#")) continue;
      const idx = line.indexOf("=");
      if (idx === -1) continue;
      const key = line.slice(0, idx).trim();
      if (key !== "DATALAB_API_BASE" && key !== "API_BASE") continue;
      let value = line.slice(idx + 1).trim();
      if (
        (value.startsWith("\"") && value.endsWith("\"")) ||
        (value.startsWith("'") && value.endsWith("'"))
      ) {
        value = value.slice(1, -1);
      }
      if (value) process.env.DATALAB_API_BASE = value;
      return;
    }
  }
}

// Allow SameSite=None cookies without HTTPS in Electron (dev/local only).
app.commandLine.appendSwitch(
  "disable-features",
  "SameSiteByDefaultCookies,CookiesWithoutSameSiteMustBeSecure"
);

loadApiBaseFromEnvFile();

function createWindow() {
  Menu.setApplicationMenu(null);

  win = new BrowserWindow({
    width: 1200,
    height: 800,
    frame: false,   
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: false,
     
    },
  });

  win.loadFile("renderer/login.html");

  globalShortcut.register("CommandOrControl+R", () => win?.reload());
  globalShortcut.register("F5", () => win?.reload());
  globalShortcut.register("CommandOrControl+Shift+I", () => {
    win?.webContents.toggleDevTools();
  });
}

function initAutoUpdate() {
  // Auto-check for updates on app start.
  autoUpdater.autoDownload = true;
  autoUpdater.on("update-downloaded", () => {
    // Apply update on next quit or immediately if window exists.
    if (win) {
      win.webContents.send("update-downloaded");
    }
    autoUpdater.quitAndInstall();
  });
  autoUpdater.checkForUpdatesAndNotify();
}

ipcMain.handle("go", (e, page) => {
  const [file, queryString] = page.split("?");
  win.loadFile(
    path.join(__dirname, "renderer", `${file}.html`),
    { search: queryString ? `?${queryString}` : "" }
  );
});

ipcMain.handle("set-session-cookie", async (e, { url, name, value, expirationDate }) => {
  const cookieUrl = url.endsWith("/") ? url : `${url}/`;
  const cookie = {
    url: cookieUrl,
    name,
    value,
    httpOnly: true,
    sameSite: "unspecified",
    path: "/",
    secure: false,
  };
  if (expirationDate) cookie.expirationDate = expirationDate;
  await session.defaultSession.cookies.set(cookie);
  return true;
});

ipcMain.handle("clear-session-cookie", async (e, { url, name }) => {
  const cookieUrl = url.endsWith("/") ? url : `${url}/`;
  await session.defaultSession.cookies.remove(cookieUrl, name);
  return true;
});

ipcMain.handle("set-session-key", (e, key) => {
  sessionKey = key || null;
  return true;
});

ipcMain.handle("get-session-key", async () => {
  if (sessionKey) return sessionKey;
  try {
    const cookieUrl = `${getApiBase()}/`;
    const cookies = await session.defaultSession.cookies.get({
      url: cookieUrl,
      name: "sessionid",
    });
    const cookieValue = cookies?.[0]?.value || null;
    if (cookieValue) {
      sessionKey = cookieValue;
    }
    return sessionKey;
  } catch (e) {
    return sessionKey;
  }
});

ipcMain.handle("clear-session-key", () => {
  sessionKey = null;
  return true;
});

ipcMain.handle("app-quit", () => {
  app.quit();
});

ipcMain.handle("app-get-version", () => app.getVersion());
ipcMain.handle("app-get-update-url", () => {
  const feeds = autoUpdater.getFeedURL ? autoUpdater.getFeedURL() : null;
  return feeds || null;
});
ipcMain.handle("open-external", async (e, url) => {
  if (
    typeof url !== "string" ||
    !/^(https?:\/\/|kakaowork:\/\/)/i.test(url)
  ) {
    throw new Error("invalid external url");
  }
  await shell.openExternal(url);
  return true;
});

ipcMain.handle("open-kakaowork", async () => {
  // On Windows, `start kakaowork://` tends to refocus an already-running KakaoWork window.
  if (process.platform === "win32") {
    await execFileAsync("cmd", ["/c", "start", "", "kakaowork://"]);

    // Extra foreground attempt: find KakaoWork window and activate it explicitly.
    const focusScript = [
      "$ErrorActionPreference='SilentlyContinue'",
      "$ws=New-Object -ComObject WScript.Shell",
      "$p=Get-Process -Name 'KakaoWork' | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1",
      "if (-not $p) { $p=Get-Process | Where-Object { $_.MainWindowHandle -ne 0 -and ($_.ProcessName -match '^KakaoWork$' -or $_.MainWindowTitle -match '카카오워크|KakaoWork') } | Select-Object -First 1 }",
      "if ($p) { [void]$ws.AppActivate($p.Id); Start-Sleep -Milliseconds 120; [void]$ws.AppActivate($p.Id) }",
      "if ($p -and $p.MainWindowHandle -ne 0) {",
      "  Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public static class Win32 { [DllImport(\"user32.dll\")] public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow); [DllImport(\"user32.dll\")] public static extern bool SetForegroundWindow(IntPtr hWnd); }' -ErrorAction SilentlyContinue | Out-Null",
      "  [Win32]::ShowWindowAsync($p.MainWindowHandle, 9) | Out-Null",
      "  Start-Sleep -Milliseconds 80",
      "  [Win32]::SetForegroundWindow($p.MainWindowHandle) | Out-Null",
      "}",
    ].join(";");

    try {
      await execFileAsync("powershell", [
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        focusScript,
      ]);
    } catch (e) {
      // Ignore focus errors; the app may still open successfully.
    }

    return true;
  }

  await shell.openExternal("kakaowork://");
  return true;
});

ipcMain.handle("open-notion", async () => {
  if (process.platform === "win32") {
    await execFileAsync("cmd", ["/c", "start", "", "notion://"]);

    const focusScript = [
      "$ErrorActionPreference='SilentlyContinue'",
      "$ws=New-Object -ComObject WScript.Shell",
      "$p=Get-Process -Name 'Notion' | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1",
      "if (-not $p) { $p=Get-Process | Where-Object { $_.MainWindowHandle -ne 0 -and ($_.ProcessName -match '^Notion$' -or $_.MainWindowTitle -match 'Notion') } | Select-Object -First 1 }",
      "if ($p) { [void]$ws.AppActivate($p.Id); Start-Sleep -Milliseconds 120; [void]$ws.AppActivate($p.Id) }",
      "if ($p -and $p.MainWindowHandle -ne 0) {",
      "  Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public static class Win32 { [DllImport(\"user32.dll\")] public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow); [DllImport(\"user32.dll\")] public static extern bool SetForegroundWindow(IntPtr hWnd); }' -ErrorAction SilentlyContinue | Out-Null",
      "  [Win32]::ShowWindowAsync($p.MainWindowHandle, 9) | Out-Null",
      "  Start-Sleep -Milliseconds 80",
      "  [Win32]::SetForegroundWindow($p.MainWindowHandle) | Out-Null",
      "}",
    ].join(";");

    try {
      await execFileAsync("powershell", [
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        focusScript,
      ]);
    } catch (e) {
      // Ignore focus errors.
    }
    return true;
  }

  await shell.openExternal("notion://");
  return true;
});

app.whenReady().then(() => {
  createWindow();
  initAutoUpdate();
});
app.on("will-quit", () => globalShortcut.unregisterAll());
