const { app, BrowserWindow, dialog, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs/promises');
const fsSync = require('fs');
const { spawn } = require('child_process');

const GEX_REPO_URL = 'https://github.com/aiassistsecure/_Gex.git';

function createWindow() {
  const win = new BrowserWindow({
    width: 1600,
    height: 980,
    minWidth: 1200,
    minHeight: 760,
    backgroundColor: '#0b1118',
    title: '_Gex UI/UX',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  win.loadFile(path.join(__dirname, 'index.html'));
}

function execCommand(command, args, cwd) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { cwd, shell: false });
    let stdout = '';
    let stderr = '';

    child.stdout.on('data', (chunk) => {
      stdout += chunk.toString();
    });

    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString();
    });

    child.on('error', reject);
    child.on('close', (code) => resolve({ code, stdout, stderr }));
  });
}

async function ensureGexModule() {
  const moduleDir = path.join(__dirname, 'modules', '_Gex');
  const scriptPath = path.join(moduleDir, '_Gex.py');

  if (!fsSync.existsSync(moduleDir)) {
    await fs.mkdir(path.dirname(moduleDir), { recursive: true });
    const cloneResult = await execCommand('git', ['clone', '--depth', '1', GEX_REPO_URL, moduleDir], __dirname);
    if (cloneResult.code !== 0) {
      throw new Error(cloneResult.stderr || cloneResult.stdout || 'Unable to clone _Gex module.');
    }
  } else {
    await execCommand('git', ['-C', moduleDir, 'pull', '--ff-only'], __dirname);
  }

  return { moduleDir, scriptPath };
}

async function walkDirectory(dirPath, rootPath = dirPath) {
  const entries = await fs.readdir(dirPath, { withFileTypes: true });
  const nodes = [];

  for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
    if (entry.name === '.git' || entry.name === 'node_modules' || entry.name === `${path.basename(rootPath)}_gex`) {
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

async function prepareScanTarget(rootDirectory, filePath, outputMode) {
  const relFile = path.relative(rootDirectory, filePath);

  if (outputMode === 'clone_repo') {
    const cloneRoot = `${rootDirectory}_Gex`;
    await fs.rm(cloneRoot, { recursive: true, force: true });
    await fs.cp(rootDirectory, cloneRoot, {
      recursive: true,
      filter: (src) => !src.includes(`${path.sep}.git`) && !src.includes(`${path.sep}node_modules`),
    });

    return {
      scanRoot: cloneRoot,
      scanFilePath: path.join(cloneRoot, relFile),
      relFile,
    };
  }

  return {
    scanRoot: rootDirectory,
    scanFilePath: filePath,
    relFile,
  };
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

ipcMain.handle('fs:readFile', async (_, filePath) => fs.readFile(filePath, 'utf8'));
ipcMain.handle('gex:ensureModule', async () => ensureGexModule());

ipcMain.handle('gex:runScan', async (_, payload) => {
  const {
    rootDirectory,
    filePath,
    outputMode = 'clone_repo',
    focus = '',
  } = payload;

  const { scriptPath } = await ensureGexModule();
  const target = await prepareScanTarget(rootDirectory, filePath, outputMode);

  const before = await fs.readFile(target.scanFilePath, 'utf8');

  const args = [scriptPath, '--scan', target.scanRoot, '--file', target.relFile];
  if (focus) {
    args.push('--focus', focus);
  }

  const output = await execCommand('python3', args, __dirname);
  const after = await fs.readFile(target.scanFilePath, 'utf8');

  let outputFilePath = target.scanFilePath;
  if (outputMode === 'append_file') {
    const ext = path.extname(target.scanFilePath);
    const base = ext ? target.scanFilePath.slice(0, -ext.length) : target.scanFilePath;
    outputFilePath = `${base}_gex${ext}`;
    await fs.writeFile(outputFilePath, after, 'utf8');
  }

  return {
    filePath: target.scanFilePath,
    outputFilePath,
    outputMode,
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
