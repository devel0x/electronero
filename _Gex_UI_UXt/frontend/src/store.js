import { create } from 'zustand';
import axios from 'axios';

const api = axios.create({ baseURL: 'http://localhost:8000' });

export const useGexStore = create((set, get) => ({
  repos: [],
  selectedRepo: null,
  tree: [],
  openFile: null,
  editorValue: '',
  runId: null,
  logs: [],
  diffs: [],
  progress: { current: 0, total: 0, file: '' },

  fetchRepos: async () => {
    const { data } = await api.get('/repos');
    set({ repos: data });
  },
  cloneRepo: async (gitUrl) => {
    await api.post('/repos/clone', { git_url: gitUrl });
    await get().fetchRepos();
  },
  loadLocalRepo: async (localPath) => {
    await api.post('/repos/load', { local_path: localPath });
    await get().fetchRepos();
  },
  openRepo: async (repoName) => {
    const { data } = await api.get(`/repos/${repoName}/tree`);
    set({ selectedRepo: repoName, tree: data, openFile: null, editorValue: '' });
  },
  openRepoFile: async (path) => {
    const repo = get().selectedRepo;
    const { data } = await api.get(`/repos/${repo}/file`, { params: { path } });
    set({ openFile: data.path, editorValue: data.content });
  },
  startRun: async (mode, file = null) => {
    const repo = get().selectedRepo;
    const { data } = await api.post('/runs/start', { repo, mode, file });
    set({ runId: data.run_id, logs: [], diffs: [] });
    get().connectRunSocket(data.run_id);
  },
  stopRun: async () => {
    const runId = get().runId;
    if (runId) await api.post(`/runs/${runId}/stop`);
  },
  connectRunSocket: (runId) => {
    const ws = new WebSocket(`ws://localhost:8000/ws/runs/${runId}`);
    ws.onmessage = async (event) => {
      const payload = JSON.parse(event.data);
      if (payload.type === 'progress') {
        set({ progress: payload });
      }
      if (payload.type === 'log' || payload.type === 'error') {
        set((state) => ({ logs: [...state.logs, payload.message] }));
      }
      if (payload.type === 'done') {
        const { data } = await api.get(`/runs/${runId}/diffs`);
        set({ diffs: data });
        ws.close();
      }
    };
  }
}));
