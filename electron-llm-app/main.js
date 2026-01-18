const {
  app,
  BrowserWindow,
  ipcMain,
  Menu,
  globalShortcut,
  session,
} = require("electron");
const path = require("path");

let win;
let sessionKey = null;

// Allow SameSite=None cookies without HTTPS in Electron (dev/local only).
app.commandLine.appendSwitch(
  "disable-features",
  "SameSiteByDefaultCookies,CookiesWithoutSameSiteMustBeSecure"
);

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
