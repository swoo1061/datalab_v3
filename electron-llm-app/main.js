const {
  app,
  BrowserWindow,
  ipcMain,
  Menu,
  globalShortcut,
  session,
} = require("electron");
const fs = require("fs");
const path = require("path");

let win;
let sessionKey = null;

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

ipcMain.handle("go", (e, page) => {
  const [file, queryString] = page.split("?");
  win.loadFile(
    path.join(__dirname, "renderer", `${file}.html`),
    { search: queryString ? `?${queryString}` : "" }
  );
});

ipcMain.handle("set-session-cookie", async (e, { url, name, value }) => {
  const cookieUrl = url.endsWith("/") ? url : `${url}/`;
  await session.defaultSession.cookies.set({
    url: cookieUrl,
    name,
    value,
    httpOnly: true,
    sameSite: "unspecified",
    path: "/",
    secure: false,
  });
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

ipcMain.handle("get-session-key", () => sessionKey);

ipcMain.handle("clear-session-key", () => {
  sessionKey = null;
  return true;
});

ipcMain.handle("app-quit", () => {
  app.quit();
});

app.whenReady().then(createWindow);
app.on("will-quit", () => globalShortcut.unregisterAll());
