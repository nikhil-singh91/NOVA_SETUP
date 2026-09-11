const { app, BrowserWindow, shell } = require('electron');
const path = require('path');
const http = require('http');

function checkViteReady(url, maxRetries = 30, intervalMs = 500) {
  return new Promise((resolve) => {
    let retries = 0;
    const attempt = () => {
      const req = http.get(url, (res) => {
        if (res.statusCode >= 200 && res.statusCode < 400) {
          resolve(true);
        } else if (retries < maxRetries) {
          retries++;
          setTimeout(attempt, intervalMs);
        } else {
          resolve(false);
        }
      });
      req.on('error', () => {
        if (retries < maxRetries) {
          retries++;
          setTimeout(attempt, intervalMs);
        } else {
          resolve(false);
        }
      });
      req.end();
    };
    attempt();
  });
}

async function createWindow() {
  const mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 1020,
    minHeight: 680,
    titleBarStyle: 'hiddenInset',
    backgroundColor: '#080c14',
    show: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
    },
  });

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;
  const devUrl = 'http://127.0.0.1:5173';

  if (isDev) {
    const isReady = await checkViteReady(devUrl);
    if (isReady) {
      mainWindow.loadURL(devUrl);
    } else {
      mainWindow.loadFile(path.join(__dirname, '../dist/index.html')).catch(() => {
        mainWindow.loadURL(devUrl);
      });
    }
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
