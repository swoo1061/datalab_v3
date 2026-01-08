const { app, BrowserWindow, ipcMain, Menu, globalShortcut } = require("electron");
const path = require("path");

let win;

function createWindow() {
  // 🔥 메뉴 완전 제거
  Menu.setApplicationMenu(null);

  win = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      partition: "persist:datalab90",
    },
  });

  win.loadFile("renderer/login.html");
// ✅ 새로고침 단축키 등록
  globalShortcut.register("CommandOrControl+R", () => {
    if (win) win.reload();
  });

  globalShortcut.register("F5", () => {
    if (win) win.reload();
  });


  // 🔧 DevTools 단축키 등록
  globalShortcut.register("CommandOrControl+Shift+I", () => {
    if (!win) return;
    win.webContents.toggleDevTools();
  });
}

ipcMain.handle("go", (e, page) => {
  win.loadFile(`renderer/${page}.html`);
});

app.whenReady().then(createWindow);

// 앱 종료 시 단축키 해제
app.on("will-quit", () => {
  globalShortcut.unregisterAll();
});
