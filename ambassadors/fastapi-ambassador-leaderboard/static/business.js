(() => {
  const ICE_SERVERS = [{ urls: 'stun:stun.l.google.com:19302' }];

  function formatTime(iso) {
    if (!iso) return '';
    try {
      const date = new Date(iso);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (err) {
      return '';
    }
  }

  function createElement(tag, opts = {}) {
    const el = document.createElement(tag);
    Object.entries(opts).forEach(([key, value]) => {
      if (key === 'class') {
        el.className = value;
      } else if (key === 'text') {
        el.textContent = value;
      } else if (key === 'html') {
        el.innerHTML = value;
      } else if (value !== undefined) {
        el.setAttribute(key, value);
      }
    });
    return el;
  }

  function BusinessRoomBoot(config) {
    if (!config || !config.wsUrl) {
      console.warn('Business room boot aborted: invalid payload');
      return;
    }

    const state = {
      config,
      ws: null,
      selfId: null,
      awaitingReady: false,
      inCall: false,
      audioMuted: false,
      localStream: null,
      screenStream: null,
      peerConnections: new Map(),
      participants: new Map(),
      remoteContainers: new Map(),
      destroyed: false,
    };

    const els = {
      messageStream: document.getElementById('messageStream'),
      messageCounter: document.getElementById('messageCounter'),
      chatForm: document.getElementById('chatForm'),
      chatInput: document.getElementById('chatInput'),
      participantList: document.getElementById('participantList'),
      joinCallBtn: document.getElementById('joinCallBtn'),
      muteCallBtn: document.getElementById('muteCallBtn'),
      leaveCallBtn: document.getElementById('leaveCallBtn'),
      shareScreenBtn: document.getElementById('shareScreenBtn'),
      localPreview: document.getElementById('localPreview'),
      screenPreview: document.getElementById('screenPreview'),
      remoteMedia: document.getElementById('remoteMedia'),
    };

    const supportsWebRTC = typeof window.RTCPeerConnection === 'function' && navigator.mediaDevices;
    if (!supportsWebRTC) {
      disableCallControls('Voice and screen share require a modern browser with WebRTC support.');
    }

    bindEvents();
    connectWebSocket();

    function bindEvents() {
      if (els.chatForm) {
        els.chatForm.addEventListener('submit', (event) => {
          event.preventDefault();
          const body = (els.chatInput?.value || '').trim();
          if (!body) return;
          if (state.ws?.readyState !== WebSocket.OPEN) return;
          state.ws.send(JSON.stringify({ type: 'chat', body }));
          els.chatInput.value = '';
        });
      }

      if (els.joinCallBtn) {
        els.joinCallBtn.addEventListener('click', async () => {
          if (!supportsWebRTC || state.inCall) return;
          await joinCall();
        });
      }

      if (els.leaveCallBtn) {
        els.leaveCallBtn.addEventListener('click', () => {
          if (!state.inCall) return;
          leaveCall();
        });
      }

      if (els.muteCallBtn) {
        els.muteCallBtn.addEventListener('click', () => {
          if (!state.localStream) return;
          state.audioMuted = !state.audioMuted;
          state.localStream.getAudioTracks().forEach((track) => {
            track.enabled = !state.audioMuted;
          });
          els.muteCallBtn.textContent = state.audioMuted ? 'Unmute' : 'Mute';
          els.muteCallBtn.classList.toggle('btn-warning', state.audioMuted);
        });
      }

      if (els.shareScreenBtn) {
        els.shareScreenBtn.addEventListener('click', () => {
          if (!state.inCall) return;
          if (state.screenStream) {
            stopScreenShare();
          } else {
            startScreenShare();
          }
        });
      }
    }

    function disableCallControls(reason) {
      [els.joinCallBtn, els.muteCallBtn, els.leaveCallBtn, els.shareScreenBtn].forEach((btn) => {
        if (btn) {
          btn.disabled = true;
          btn.classList.add('disabled');
        }
      });
      if (reason && els.messageStream) {
        pushSystemMessage(reason);
      }
    }

    function updateCallButtons() {
      if (!supportsWebRTC) return;
      if (els.joinCallBtn) {
        els.joinCallBtn.disabled = state.inCall;
        els.joinCallBtn.classList.toggle('disabled', state.inCall);
      }
      if (els.leaveCallBtn) {
        els.leaveCallBtn.disabled = !state.inCall;
      }
      if (els.muteCallBtn) {
        els.muteCallBtn.disabled = !state.inCall;
        els.muteCallBtn.textContent = state.audioMuted ? 'Unmute' : 'Mute';
        els.muteCallBtn.classList.toggle('btn-warning', state.audioMuted);
      }
      if (els.shareScreenBtn) {
        els.shareScreenBtn.disabled = !state.inCall;
        els.shareScreenBtn.textContent = state.screenStream ? 'Stop share' : 'Share screen';
      }
    }

    function connectWebSocket() {
      try {
        state.ws = new WebSocket(config.wsUrl);
      } catch (err) {
        pushSystemMessage('Unable to connect to business room. Please refresh.');
        return;
      }

      state.ws.addEventListener('open', () => {
        pushSystemMessage('Connected to the business room.');
        if (state.inCall && state.selfId) {
          sendSignal('ready');
        }
      });

      state.ws.addEventListener('message', (event) => {
        try {
          const payload = JSON.parse(event.data);
          handleSocketMessage(payload);
        } catch (err) {
          console.warn('Invalid websocket payload', err);
        }
      });

      state.ws.addEventListener('close', () => {
        pushSystemMessage('Connection closed. Refresh to reconnect.');
        leaveCall();
      });

      state.ws.addEventListener('error', () => {
        pushSystemMessage('A network error occurred.');
      });
    }

    function handleSocketMessage(data) {
      if (!data || typeof data !== 'object') return;
      switch (data.type) {
        case 'welcome':
          state.selfId = data.self?.id || null;
          if (state.awaitingReady && state.selfId) {
            sendSignal('ready');
            state.awaitingReady = false;
          }
          if (state.inCall && state.selfId && state.participants.size) {
            state.participants.forEach((participant, pid) => {
              if (!pid || pid === state.selfId) return;
              const entry = ensureConnection(pid);
              if (entry && entry.isInitiator && entry.pc.signalingState === 'stable' && entry.pc.connectionState !== 'connected') {
                maybeInitiateOffer(pid);
              }
            });
          }
          break;
        case 'history':
          renderHistory(data.messages || []);
          break;
        case 'chat':
          appendMessage(data);
          break;
        case 'system':
          pushSystemMessage(data.message, data.timestamp);
          break;
        case 'presence':
          updateParticipants(data.participants || []);
          break;
        case 'signal':
          handleSignal(data);
          break;
        case 'pong':
          break;
        default:
          break;
      }
    }

    function renderHistory(messages) {
      if (!els.messageStream) return;
      els.messageStream.innerHTML = '';
      (messages || []).forEach((message) => appendMessage(message));
    }

    function appendMessage(message) {
      if (!els.messageStream || !message) return;
      const type = message.type || 'chat';
      const item = createElement('div', { class: 'message-item' });
      if (type === 'system') {
        item.classList.add('system-message');
        const meta = formatTime(message.timestamp);
        item.textContent = meta ? `[${meta}] ${message.message}` : message.message;
      } else {
        const bubble = createElement('div', { class: 'message-bubble' });
        const header = createElement('div', { class: 'd-flex justify-content-between align-items-center mb-1' });
        const sender = createElement('div', { class: 'fw-semibold' });
        const meta = createElement('div', { class: 'message-meta' });
        const body = createElement('div');
        const displayName = message.sender?.display_name || 'Ambassador';
        const initials = message.sender?.initials || '?';
        const color = message.sender?.color || '#4aa3ff';
        const badge = createElement('span', {
          class: 'badge',
          text: initials,
        });
        badge.style.background = color;
        badge.style.color = '#0d1117';
        badge.style.marginRight = '0.5rem';
        sender.appendChild(badge);
        sender.append(document.createTextNode(displayName));
        meta.textContent = formatTime(message.timestamp);
        body.textContent = message.body || '';
        header.appendChild(sender);
        header.appendChild(meta);
        bubble.appendChild(header);
        bubble.appendChild(body);
        item.appendChild(bubble);
      }
      els.messageStream.appendChild(item);
      if (els.messageStream.childElementCount) {
        if (els.messageCounter) {
          const total = els.messageStream.childElementCount;
          els.messageCounter.textContent = `${total} message${total === 1 ? '' : 's'}`;
        }
        els.messageStream.scrollTop = els.messageStream.scrollHeight;
      }
    }

    function pushSystemMessage(message, timestamp) {
      appendMessage({ type: 'system', message, timestamp: timestamp || new Date().toISOString() });
    }

    function updateParticipants(participants) {
      state.participants.clear();
      participants.forEach((participant) => {
        if (participant?.id) {
          state.participants.set(participant.id, participant);
        }
      });
      if (!els.participantList) return;
      els.participantList.innerHTML = '';
      const list = participants.slice().sort((a, b) => a.display_name.localeCompare(b.display_name));
      list.forEach((participant) => {
        const pill = createElement('div', { class: 'participant-pill' });
        const avatar = createElement('div', { class: 'participant-avatar', text: participant.initials || '?' });
        avatar.style.background = participant.color || '#4aa3ff';
        const meta = createElement('div');
        const name = createElement('div', { class: 'fw-semibold', text: participant.display_name || 'Ambassador' });
        const handle = participant.telegram ? createElement('div', { class: 'small text-info', text: participant.telegram }) : null;
        meta.appendChild(name);
        if (handle) meta.appendChild(handle);
        pill.appendChild(avatar);
        pill.appendChild(meta);
        els.participantList.appendChild(pill);
        updateRemoteLabel(participant.id, participant.display_name);
      });
      if (state.inCall && state.selfId) {
        list.forEach((participant) => {
          if (!participant.id || participant.id === state.selfId) return;
          const entry = ensureConnection(participant.id);
          if (!entry) return;
          entry.isInitiator = state.selfId > participant.id;
          if (entry.isInitiator && entry.pc.signalingState === 'stable' && entry.pc.connectionState !== 'connected') {
            maybeInitiateOffer(participant.id);
          }
        });
      }
    }

    function updateRemoteLabel(remoteId, name) {
      const container = state.remoteContainers.get(remoteId);
      if (container) {
        const label = container.querySelector('.remote-name');
        if (label) label.textContent = name || 'Ambassador';
      }
    }

    function ensureRemoteContainer(remoteId) {
      let container = state.remoteContainers.get(remoteId);
      if (container) return container;
      const wrapper = createElement('div', { class: 'remote-card p-3 bg-dark bg-opacity-50 rounded-3', 'data-remote': remoteId });
      const header = createElement('div', { class: 'd-flex justify-content-between align-items-center mb-2' });
      const name = createElement('div', { class: 'fw-semibold remote-name', text: 'Ambassador' });
      const status = createElement('span', { class: 'badge bg-info-subtle text-info-emphasis', text: 'Live' });
      header.appendChild(name);
      header.appendChild(status);
      const audio = document.createElement('audio');
      audio.autoplay = true;
      audio.controls = false;
      audio.className = 'remote-audio w-100';
      const video = document.createElement('video');
      video.autoplay = true;
      video.playsInline = true;
      video.muted = false;
      video.className = 'remote-video w-100 mt-2';
      video.classList.add('d-none');
      wrapper.appendChild(header);
      wrapper.appendChild(audio);
      wrapper.appendChild(video);
      if (els.remoteMedia) {
        els.remoteMedia.appendChild(wrapper);
      }
      state.remoteContainers.set(remoteId, wrapper);
      const participant = state.participants.get(remoteId);
      if (participant?.display_name) {
        name.textContent = participant.display_name;
      }
      return wrapper;
    }

    function removeRemoteContainer(remoteId) {
      const container = state.remoteContainers.get(remoteId);
      if (container && container.parentElement) {
        container.parentElement.removeChild(container);
      }
      state.remoteContainers.delete(remoteId);
    }

    function handleSignal(message) {
      const from = message.from;
      if (!from || from === state.selfId) return;
      const target = message.target;
      if (target && state.selfId && target !== state.selfId) return;
      const signal = message.signal;
      const payload = message.payload || {};

      switch (signal) {
        case 'ready':
          if (state.inCall) {
            ensureConnection(from);
            maybeInitiateOffer(from);
          }
          break;
        case 'offer':
          handleOffer(from, payload.sdp);
          break;
        case 'answer':
          handleAnswer(from, payload.sdp);
          break;
        case 'ice':
          handleIceCandidate(from, payload.candidate);
          break;
        case 'leave-call':
          closeConnection(from, 'left the call');
          break;
        case 'renegotiate':
          triggerRenegotiation(from);
          break;
        case 'screen-share':
          handleRemoteScreenSignal(from, payload);
          break;
        default:
          break;
      }
    }

    function ensureConnection(remoteId) {
      if (state.peerConnections.has(remoteId)) {
        return state.peerConnections.get(remoteId);
      }
      if (!supportsWebRTC) return null;
      const pc = new RTCPeerConnection({ iceServers: ICE_SERVERS });
      const entry = {
        pc,
        isInitiator: state.selfId ? state.selfId > remoteId : false,
        audioSender: null,
        screenSender: null,
      };
      state.peerConnections.set(remoteId, entry);

      pc.onicecandidate = (event) => {
        if (event.candidate) {
          sendSignal('ice', { candidate: event.candidate }, remoteId);
        }
      };

      pc.ontrack = (event) => {
        const [stream] = event.streams;
        const kind = event.track.kind;
        const container = ensureRemoteContainer(remoteId);
        if (kind === 'audio') {
          const audioEl = container.querySelector('.remote-audio');
          if (audioEl) {
            audioEl.srcObject = stream;
          }
        } else if (kind === 'video') {
          const videoEl = container.querySelector('.remote-video');
          if (videoEl) {
            videoEl.srcObject = stream;
            videoEl.classList.remove('d-none');
          }
        }
        event.track.addEventListener('ended', () => {
          if (kind === 'video') {
            const videoEl = container.querySelector('.remote-video');
            if (videoEl) {
              videoEl.srcObject = null;
              videoEl.classList.add('d-none');
            }
          }
        });
      };

      pc.onconnectionstatechange = () => {
        if (['failed', 'closed', 'disconnected'].includes(pc.connectionState)) {
          closeConnection(remoteId, pc.connectionState);
        }
      };

      attachLocalTracks(remoteId);
      return entry;
    }

    function attachLocalTracks(remoteId) {
      const entry = state.peerConnections.get(remoteId);
      if (!entry) return;
      if (state.localStream) {
        const audioTrack = state.localStream.getAudioTracks()[0];
        if (audioTrack && !entry.audioSender) {
          entry.audioSender = entry.pc.addTrack(audioTrack, state.localStream);
        }
      }
      if (state.screenStream) {
        const videoTrack = state.screenStream.getVideoTracks()[0];
        if (videoTrack && !entry.screenSender) {
          entry.screenSender = entry.pc.addTrack(videoTrack, state.screenStream);
        }
      }
    }

    async function maybeInitiateOffer(remoteId) {
      const entry = ensureConnection(remoteId);
      if (!entry) return;
      if (!state.localStream) return;
      if (!entry.isInitiator) {
        // let the peer initiate
        return;
      }
      try {
        const offer = await entry.pc.createOffer();
        await entry.pc.setLocalDescription(offer);
        sendSignal('offer', { sdp: offer }, remoteId);
      } catch (err) {
        console.warn('offer failed', err);
      }
    }

    async function handleOffer(remoteId, sdp) {
      if (!state.inCall) return;
      const entry = ensureConnection(remoteId);
      if (!entry) return;
      entry.isInitiator = false;
      try {
        await entry.pc.setRemoteDescription(new RTCSessionDescription(sdp));
        attachLocalTracks(remoteId);
        const answer = await entry.pc.createAnswer();
        await entry.pc.setLocalDescription(answer);
        sendSignal('answer', { sdp: answer }, remoteId);
      } catch (err) {
        console.warn('answer failed', err);
      }
    }

    async function handleAnswer(remoteId, sdp) {
      const entry = state.peerConnections.get(remoteId);
      if (!entry) return;
      try {
        await entry.pc.setRemoteDescription(new RTCSessionDescription(sdp));
      } catch (err) {
        console.warn('setRemoteDescription failed', err);
      }
    }

    async function handleIceCandidate(remoteId, candidate) {
      const entry = state.peerConnections.get(remoteId);
      if (!entry || !candidate) return;
      try {
        await entry.pc.addIceCandidate(new RTCIceCandidate(candidate));
      } catch (err) {
        console.warn('ice candidate failed', err);
      }
    }

    function triggerRenegotiation(remoteId) {
      const entry = state.peerConnections.get(remoteId);
      if (!entry) return;
      if (entry.isInitiator) {
        maybeInitiateOffer(remoteId);
      }
    }

    function handleRemoteScreenSignal(remoteId, payload) {
      const active = Boolean(payload?.active);
      const container = state.remoteContainers.get(remoteId);
      if (!container) return;
      const videoEl = container.querySelector('.remote-video');
      if (videoEl && !active) {
        videoEl.srcObject = null;
        videoEl.classList.add('d-none');
      }
    }

    async function joinCall() {
      if (!supportsWebRTC) {
        pushSystemMessage('Voice is not available in this browser.');
        return;
      }
      try {
        state.localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
        state.localStream.getAudioTracks().forEach((track) => {
          track.enabled = !state.audioMuted;
        });
        if (els.localPreview) {
          els.localPreview.srcObject = state.localStream;
          els.localPreview.muted = true;
          els.localPreview.play().catch(() => {});
        }
        state.inCall = true;
        updateCallButtons();
        if (state.selfId) {
          sendSignal('ready');
        } else {
          state.awaitingReady = true;
        }
      } catch (err) {
        pushSystemMessage('Microphone access is required to join voice.');
        console.warn('join call failed', err);
      }
    }

    function leaveCall() {
      if (!state.inCall) return;
      state.inCall = false;
      updateCallButtons();
      if (state.ws?.readyState === WebSocket.OPEN && state.selfId) {
        sendSignal('leave-call');
      }
      if (state.screenStream) {
        stopScreenShare();
      }
      if (state.localStream) {
        state.localStream.getTracks().forEach((track) => track.stop());
        state.localStream = null;
      }
      if (els.localPreview) {
        els.localPreview.srcObject = null;
      }
      if (els.screenPreview) {
        els.screenPreview.srcObject = null;
      }
      Array.from(state.peerConnections.keys()).forEach((remoteId) => {
        closeConnection(remoteId, 'call ended');
      });
    }

    async function startScreenShare() {
      if (!supportsWebRTC || !state.inCall) return;
      try {
        const stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false });
        state.screenStream = stream;
        const track = stream.getVideoTracks()[0];
        if (els.screenPreview) {
          els.screenPreview.srcObject = stream;
          els.screenPreview.muted = true;
          els.screenPreview.play().catch(() => {});
        }
        track.addEventListener('ended', () => {
          stopScreenShare();
        });
        state.peerConnections.forEach((entry, remoteId) => {
          if (!entry.screenSender) {
            entry.screenSender = entry.pc.addTrack(track, stream);
          } else {
            entry.screenSender.replaceTrack(track).catch(() => {});
          }
          if (entry.isInitiator) {
            maybeInitiateOffer(remoteId);
          } else {
            sendSignal('renegotiate', { reason: 'screen-share' }, remoteId);
          }
        });
        sendSignal('screen-share', { active: true });
        updateCallButtons();
      } catch (err) {
        console.warn('screen share failed', err);
      }
    }

    function stopScreenShare() {
      if (!state.screenStream) return;
      state.screenStream.getTracks().forEach((track) => track.stop());
      state.screenStream = null;
      if (els.screenPreview) {
        els.screenPreview.srcObject = null;
      }
      state.peerConnections.forEach((entry, remoteId) => {
        if (entry.screenSender) {
          entry.screenSender.replaceTrack(null).catch(() => {});
          entry.screenSender = null;
        }
        if (entry.isInitiator) {
          maybeInitiateOffer(remoteId);
        } else {
          sendSignal('renegotiate', { reason: 'screen-stop' }, remoteId);
        }
      });
      sendSignal('screen-share', { active: false });
      updateCallButtons();
    }

    function closeConnection(remoteId, reason) {
      const entry = state.peerConnections.get(remoteId);
      if (entry) {
        try {
          entry.pc.getSenders().forEach((sender) => {
            try {
              sender.track?.stop();
            } catch (err) {
              // ignore
            }
          });
          entry.pc.close();
        } catch (err) {
          console.warn('close connection error', err);
        }
      }
      state.peerConnections.delete(remoteId);
      removeRemoteContainer(remoteId);
      if (reason) {
        const participant = state.participants.get(remoteId);
        const name = participant?.display_name || 'An ambassador';
        pushSystemMessage(`${name} ${reason}.`);
      }
    }

    function sendSignal(signal, payload = {}, target) {
      if (state.ws?.readyState !== WebSocket.OPEN) return;
      const message = { type: 'signal', signal, payload };
      if (target) message.target = target;
      state.ws.send(JSON.stringify(message));
    }
  }

  window.BusinessRoomBoot = BusinessRoomBoot;
})();
