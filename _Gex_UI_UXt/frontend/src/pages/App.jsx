import { useEffect, useMemo, useState } from 'react';
import Editor, { DiffEditor } from '@monaco-editor/react';
import { useGexStore } from '../store';

const glass = 'bg-slate-900/50 backdrop-blur-xl border border-cyan-400/30 rounded-2xl shadow-[0_0_30px_rgba(34,211,238,0.15)]';

export default function App() {
  const [gitUrl, setGitUrl] = useState('');
  const [localPath, setLocalPath] = useState('');
  const [selectedDiff, setSelectedDiff] = useState(null);
  const state = useGexStore();

  useEffect(() => {
    state.fetchRepos();
  }, []);

  const progressPct = useMemo(() => {
    if (!state.progress.total) return 0;
    return Math.floor((state.progress.current / state.progress.total) * 100);
  }, [state.progress]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-blue-950 to-cyan-900 text-slate-100 p-4">
      <div className="grid grid-cols-12 gap-4 h-[calc(100vh-2rem)]">
        <aside className={`col-span-3 p-4 flex flex-col gap-3 ${glass}`}>
          <h2 className="text-xl font-semibold text-cyan-200">Repos</h2>
          <div className="flex gap-2">
            <input className="flex-1 rounded-lg bg-slate-800/70 p-2" placeholder="Git URL" value={gitUrl} onChange={(e) => setGitUrl(e.target.value)} />
            <button className="px-3 rounded-lg bg-cyan-500/80 hover:bg-cyan-400" onClick={() => state.cloneRepo(gitUrl)}>Clone</button>
          </div>
          <div className="flex gap-2">
            <input className="flex-1 rounded-lg bg-slate-800/70 p-2" placeholder="Local path" value={localPath} onChange={(e) => setLocalPath(e.target.value)} />
            <button className="px-3 rounded-lg bg-indigo-500/80 hover:bg-indigo-400" onClick={() => state.loadLocalRepo(localPath)}>Load</button>
          </div>
          <div className="overflow-auto flex-1 space-y-1">
            {state.repos.map((repo) => (
              <button key={repo.name} className="w-full text-left rounded-lg px-3 py-2 bg-slate-800/60 hover:bg-slate-700/80 transition-all" onClick={() => state.openRepo(repo.name)}>
                {repo.name}
              </button>
            ))}
          </div>
          <div className="border-t border-slate-700 pt-2 overflow-auto max-h-64 space-y-1">
            {state.tree.map((f) => (
              <button key={f.path} className="w-full text-left text-sm rounded px-2 py-1 hover:bg-cyan-500/20" onClick={() => state.openRepoFile(f.path)}>
                {f.path}
              </button>
            ))}
          </div>
        </aside>

        <main className={`col-span-6 p-3 flex flex-col gap-3 ${glass}`}>
          <div className="text-cyan-100 font-medium">Editor / Diff</div>
          {selectedDiff ? (
            <DiffEditor
              height="100%"
              language="python"
              original={selectedDiff.before}
              modified={selectedDiff.after}
              theme="vs-dark"
              options={{ readOnly: true, renderSideBySide: true }}
            />
          ) : (
            <Editor height="100%" language="python" value={state.editorValue} theme="vs-dark" options={{ minimap: { enabled: false } }} />
          )}
        </main>

        <section className={`col-span-3 p-4 flex flex-col gap-3 ${glass}`}>
          <h2 className="text-xl font-semibold">Run _Gex</h2>
          <div className="flex gap-2">
            <button className="flex-1 rounded-lg p-2 bg-cyan-500/80 hover:bg-cyan-400" onClick={() => state.startRun('sequential', state.openFile)}>Scan File</button>
            <button className="flex-1 rounded-lg p-2 bg-emerald-500/80 hover:bg-emerald-400" onClick={() => state.startRun('sequential')}>Scan Repo</button>
          </div>
          <button className="rounded-lg p-2 bg-rose-500/80 hover:bg-rose-400" onClick={state.stopRun}>Stop</button>
          <div className="text-sm">Processing: {state.progress.file || '-'}</div>
          <div className="h-3 rounded-full bg-slate-800 overflow-hidden">
            <div className="h-full bg-gradient-to-r from-cyan-400 to-blue-500 transition-all" style={{ width: `${progressPct}%` }} />
          </div>
          <div className="text-sm">{state.progress.current}/{state.progress.total}</div>

          <div className="font-medium mt-2">Logs</div>
          <div className="bg-slate-950/60 rounded-lg p-2 h-36 overflow-auto text-xs space-y-1">
            {state.logs.map((line, idx) => <div key={idx}>{line}</div>)}
          </div>

          <div className="font-medium">Diffs</div>
          <div className="bg-slate-950/60 rounded-lg p-2 flex-1 overflow-auto space-y-1">
            {state.diffs.map((d) => (
              <button key={d.file} className="w-full text-left rounded px-2 py-1 hover:bg-cyan-500/20" onClick={() => setSelectedDiff(d)}>
                {d.file} <span className="text-xs text-cyan-300">{d.status}</span>
              </button>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
