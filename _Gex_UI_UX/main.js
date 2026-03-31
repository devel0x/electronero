const { app, BrowserWindow, dialog, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs/promises');
const { spawn } = require('child_process');

function createWindow() {
  const win = new BrowserWindow({
    width: 1600,
    height: 980,
    minWidth: 1200,
    minHeight: 760,
    backgroundColor: '#080b16',
    title: '_Gex UI/UX',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  win.loadFile(path.join(__dirname, 'index.html'));
}

async function walkDirectory(dirPath, rootPath = dirPath) {
  const entries = await fs.readdir(dirPath, { withFileTypes: true });
  const nodes = [];

  for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
    if (entry.name === '.git' || entry.name === 'node_modules') {
      continue;
    }

    const fullPath = path.join(dirPath, entry.name);
    const relPath = path.relative(rootPath, fullPath) || '.';

    if (entry.isDirectory()) {
      nodes.push({
        type: 'directory',
        name: entry.name,
        path: fullPath,
        relPath,
        children: await walkDirectory(fullPath, rootPath),
      });
    } else {
      nodes.push({
        type: 'file',
        name: entry.name,
        path: fullPath,
        relPath,
      });
    }
  }

  return nodes;
}

ipcMain.handle('dialog:pickDirectory', async () => {
  const result = await dialog.showOpenDialog({
    properties: ['openDirectory'],
  });

  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }

  const selectedPath = result.filePaths[0];
  const tree = await walkDirectory(selectedPath, selectedPath);

  return {
    root: selectedPath,
    tree,
  };
});

ipcMain.handle('fs:readFile', async (_, filePath) => {
  return fs.readFile(filePath, 'utf8');
});

ipcMain.handle('gex:runScan', async (_, payload) => {
  const {
    rootDirectory,
    filePath,
    gexCommand = '_Gex',
    extraArgs = [],
    cwd,
  } = payload;

  const before = await fs.readFile(filePath, 'utf8');

  const args = [filePath, ...extraArgs];

  const runCwd = cwd || rootDirectory;

  const output = await new Promise((resolve, reject) => {
    const child = spawn(gexCommand, args, { cwd: runCwd, shell: true });

    let stdout = '';
    let stderr = '';

    child.stdout.on('data', (chunk) => {
      stdout += chunk.toString();
    });

    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString();
    });

    child.on('error', (error) => {
      reject(error);
    });

    child.on('close', (code) => {
      resolve({ code, stdout, stderr });
    });
  });

  const after = await fs.readFile(filePath, 'utf8');

  return {
    filePath,
    before,
    after,
    changed: before !== after,
    ...output,
    timestamp: new Date().toISOString(),
  };
});

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
