const { app, BrowserWindow, ipcMain, Menu, globalShortcut } = require("electron");
const path = require("path");

let win;

function createWindow() {
  // 메뉴 제거
  Menu.setApplicationMenu(null);

  win = new BrowserWindow({
    width: 1200,
    height: 800,

    frame: false,            // 🔥 이게 핵심 (OS 타이틀바 제거)
    titleBarStyle: "hidden", // (Windows에선 거의 영향 없음, 있어도 무방)

    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      partition: "persist:datalab90",
    },
  });

  win.loadFile("renderer/login.html");

  // 새로고침
  globalShortcut.register("CommandOrControl+R", () => win?.reload());
  globalShortcut.register("F5", () => win?.reload());

  // DevTools
  globalShortcut.register("CommandOrControl+Shift+I", () => {
    win?.webContents.toggleDevTools();
  });
}

ipcMain.handle("go", (e, page) => {
  // page 예시: "clinic_guide?clinic=봄빛 병원"
  const [file, queryString] = page.split("?");

  win.loadFile(
    path.join(__dirname, "renderer", `${file}.html`),
    {
      search: queryString ? `?${queryString}` : "",
    }
  );
});

app.whenReady().then(createWindow);

app.on("will-quit", () => {
  globalShortcut.unregisterAll();
});