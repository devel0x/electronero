let state = {
  root: null,
  tree: [],
  currentFile: null,
  queuedFiles: [],
  monacoReady: false,
  editor: null,
  diffEditor: null,
  leftModel: null,
  rightModel: null,
};

const els = {
  pickFolder: document.getElementById('pick-folder'),
  bootstrapGex: document.getElementById('bootstrap-gex'),
  fileTree: document.getElementById('file-tree'),
  rootLabel: document.getElementById('root-label'),
  currentFile: document.getElementById('current-file'),
  diffStatus: document.getElementById('diff-status'),
  outputMode: document.getElementById('output-mode'),
  focusInput: document.getElementById('focus-input'),
  runOutput: document.getElementById('run-output'),
  queueList: document.getElementById('queue-list'),
  scanCurrent: document.getElementById('scan-current'),
  enqueueCurrent: document.getElementById('enqueue-current'),
  runQueue: document.getElementById('run-queue'),
  clearQueue: document.getElementById('clear-queue'),
};

function setRunOutput(text) {
  els.runOutput.textContent = text;
}

function renderTree(nodes, depth = 0) {
  const fragment = document.createDocumentFragment();

  for (const node of nodes) {
    const item = document.createElement('div');
    item.className = `file-item ${node.type === 'directory' ? 'dir' : ''}`;
    item.textContent = `${'\u00A0'.repeat(depth * 2)}${node.type === 'directory' ? '▸' : '•'} ${node.name}`;

    if (node.type === 'file') {
      item.onclick = () => openFile(node.path);
      if (node.path === state.currentFile) {
        item.classList.add('active');
      }
    }

    fragment.appendChild(item);

    if (node.type === 'directory' && node.children?.length) {
      fragment.appendChild(renderTree(node.children, depth + 1));
    }
  }

  return fragment;
}

function refreshTree() {
  els.fileTree.innerHTML = '';
  els.fileTree.appendChild(renderTree(state.tree));
}

function refreshQueue() {
  els.queueList.innerHTML = '';
  state.queuedFiles.forEach((file) => {
    const li = document.createElement('li');
    li.textContent = file;
    els.queueList.appendChild(li);
  });
}

async function openFile(filePath) {
  if (!state.monacoReady) return;

  const content = await window.gexApi.readFile(filePath);
  state.currentFile = filePath;
  els.currentFile.textContent = filePath;

  const lang = detectLanguage(filePath);
  const model = monaco.editor.createModel(content, lang);

  if (state.editor.getModel()) {
    state.editor.getModel().dispose();
  }

  state.editor.setModel(model);

  state.leftModel?.dispose();
  state.rightModel?.dispose();
  state.leftModel = monaco.editor.createModel(content, lang);
  state.rightModel = monaco.editor.createModel(content, lang);
  state.diffEditor.setModel({
    original: state.leftModel,
    modified: state.rightModel,
  });

  els.diffStatus.textContent = 'Loaded baseline';
  refreshTree();
}

function detectLanguage(filePath) {
  const ext = filePath.split('.').pop() || '';
  const map = {
    js: 'javascript',
    ts: 'typescript',
    jsx: 'javascript',
    tsx: 'typescript',
    py: 'python',
    cpp: 'cpp',
    c: 'c',
    h: 'cpp',
    hpp: 'cpp',
    rs: 'rust',
    md: 'markdown',
    json: 'json',
    yml: 'yaml',
    yaml: 'yaml',
    sh: 'shell',
    html: 'html',
    css: 'css',
  };

  return map[ext] || 'plaintext';
}

async function runScan(filePath) {
  if (!filePath) {
    setRunOutput('Select a file first.');
    return;
  }

  setRunOutput(`Preparing _Gex module and scanning ${filePath}...`);

  try {
    const result = await window.gexApi.runScan({
      rootDirectory: state.root,
      filePath,
      outputMode: els.outputMode.value,
      focus: els.focusInput.value.trim(),
    });

    const lang = detectLanguage(result.filePath);
    state.leftModel?.dispose();
    state.rightModel?.dispose();
    state.leftModel = monaco.editor.createModel(result.before, lang);
    state.rightModel = monaco.editor.createModel(result.after, lang);

    state.diffEditor.setModel({
      original: state.leftModel,
      modified: state.rightModel,
    });

    const stamp = new Date(result.timestamp).toLocaleString();
    els.diffStatus.textContent = `${result.changed ? 'Changed' : 'No change'} • exit ${result.code} • ${stamp}`;

    setRunOutput([
      `mode: ${result.outputMode}`,
      `result file: ${result.outputFilePath}`,
      `exit code: ${result.code}`,
      '',
      'stdout:',
      result.stdout || '<empty>',
      '',
      'stderr:',
      result.stderr || '<empty>',
    ].join('\n'));

    if (state.currentFile === filePath && els.outputMode.value === 'append_file') {
      const model = state.editor.getModel();
      model?.setValue(result.after);
    }
  } catch (error) {
    setRunOutput(`Failed to run _Gex:\n${error.message}`);
  }
}

function initMonaco() {
  window.require.config({
    paths: { vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.52.2/min/vs' },
  });

  window.require(['vs/editor/editor.main'], () => {
    monaco.editor.defineTheme('gex-terminal', {
      base: 'vs-dark',
      inherit: false,
      rules: [
        { token: '', foreground: 'D7E4F2' },
        { token: 'comment', foreground: '6D849A' },
        { token: 'keyword', foreground: '53B1FF', fontStyle: 'bold' },
        { token: 'number', foreground: 'FFD479' },
        { token: 'string', foreground: '8BFFB3' },
        { token: 'type.identifier', foreground: '8CC6FF' },
        { token: 'operator', foreground: '66E0FF' },
        { token: 'identifier', foreground: 'E4EEF8' },
      ],
      colors: {
        'editor.background': '#0B121A',
        'editor.foreground': '#D7E4F2',
        'editorLineNumber.foreground': '#5F7489',
        'editorCursor.foreground': '#53B1FF',
        'editor.selectionBackground': '#1F355066',
        'editor.inactiveSelectionBackground': '#16263866',
        'editor.lineHighlightBackground': '#13202E99',
        'editorBracketMatch.background': '#18365388',
        'editorBracketMatch.border': '#4AA8FFAA',
      },
    });

    state.editor = monaco.editor.create(document.getElementById('editor'), {
      theme: 'gex-terminal',
      minimap: { enabled: false },
      fontSize: 13,
      fontLigatures: true,
      smoothScrolling: true,
      automaticLayout: true,
      value: '// Open a folder and select a file to inspect...',
      language: 'javascript',
    });

    state.diffEditor = monaco.editor.createDiffEditor(document.getElementById('diff-editor'), {
      theme: 'gex-terminal',
      minimap: { enabled: false },
      automaticLayout: true,
      renderSideBySide: true,
      originalEditable: false,
    });

    state.monacoReady = true;
  });
}

els.bootstrapGex.onclick = async () => {
  try {
    setRunOutput('Installing/updating local _Gex module...');
    const moduleInfo = await window.gexApi.ensureModule();
    setRunOutput(`_Gex module ready:\n${moduleInfo.moduleDir}`);
  } catch (error) {
    setRunOutput(`Unable to setup _Gex module:\n${error.message}`);
  }
};

els.pickFolder.onclick = async () => {
  const result = await window.gexApi.pickDirectory();
  if (!result) {
    return;
  }

  state.root = result.root;
  state.tree = result.tree;
  state.currentFile = null;
  state.queuedFiles = [];

  els.rootLabel.textContent = result.root;
  els.currentFile.textContent = 'Select a file';
  els.diffStatus.textContent = 'No run yet';
  setRunOutput('Folder opened. Select a file to inspect or queue for _Gex.');

  refreshTree();
  refreshQueue();
};

els.scanCurrent.onclick = () => runScan(state.currentFile);

els.enqueueCurrent.onclick = () => {
  if (!state.currentFile || state.queuedFiles.includes(state.currentFile)) {
    return;
  }

  state.queuedFiles.push(state.currentFile);
  refreshQueue();
};

els.runQueue.onclick = async () => {
  for (const file of state.queuedFiles) {
    await runScan(file);
  }
};

els.clearQueue.onclick = () => {
  state.queuedFiles = [];
  refreshQueue();
};

initMonaco();
