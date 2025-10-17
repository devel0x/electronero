const config = window.MEETING_CONFIG || {};
// const roomId = String(config.roomId || 'ambassador-hub');
const urlParams = new URLSearchParams(window.location.search);
const roomId = urlParams.get("room") || String(config.roomId || 'ambassador-hub');
const displayName = String(config.displayName || 'Ambassador');
const capacity = config.capacity || {};

const statusBanner = document.getElementById('statusBanner');
const videoWall = document.getElementById('videoWall');
const participantList = document.getElementById('participantList');
const chatMessages = document.getElementById('chatMessages');
const chatForm = document.getElementById('chatForm');
const chatInput = document.getElementById('chatInput');
const toggleAudioBtn = document.getElementById('toggleAudioBtn');
const toggleVideoBtn = document.getElementById('toggleVideoBtn');
const shareScreenBtn = document.getElementById('shareScreenBtn');
const refreshConnectionsBtn = document.getElementById('refreshConnectionsBtn');
const localVideo = document.getElementById('localVideo');

const localStream = new MediaStream();
let cameraStream = null;
let audioTrack = null;
let cameraTrack = null;
let currentVideoTrack = null;
let screenTrack = null;
let usingScreenShare = false;

let websocket;
let selfPeerId = null;
const participants = new Map();
const peers = new Map();
let connectionAllowed = true;
let reconnectTimer = null;

function updateStatus(text, tone = 'info') {
  if (!statusBanner) return;
  statusBanner.classList.remove('text-info', 'text-warning', 'text-danger', 'text-success');
  statusBanner.classList.add(`text-${tone}`);
  statusBanner.textContent = text;
}

function appendSystemMessage(text) {
  if (!chatMessages) return;
  const bubble = document.createElement('div');
  bubble.className = 'chat-bubble text-secondary';
  bubble.textContent = text;
  chatMessages.appendChild(bubble);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function appendChatMessage({ peerId, name, text, timestamp }) {
  if (!chatMessages) return;
  const bubble = document.createElement('div');
  const isSelf = peerId === selfPeerId;
  bubble.className = `chat-bubble${isSelf ? ' me' : ''}`;

  const author = document.createElement('strong');
  author.textContent = name || 'Ambassador';
  const meta = document.createElement('span');
  meta.className = 'chat-meta';
  try {
    meta.textContent = new Date(timestamp || Date.now()).toLocaleTimeString();
  } catch (err) {
    meta.textContent = '';
  }
  const message = document.createElement('div');
  message.textContent = text;

  bubble.appendChild(author);
  bubble.appendChild(meta);
  bubble.appendChild(message);
  chatMessages.appendChild(bubble);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function ensureParticipantRow(peerId, name) {
  if (!participantList) return;
  const lookupId = peerId === selfPeerId ? 'self' : peerId;
  let row = participantList.querySelector(`[data-peer-id="${lookupId}"]`);
  if (!row) {
    row = document.createElement('li');
    row.dataset.peerId = lookupId;
    row.className = 'd-flex align-items-center gap-2 mb-2';
    const indicator = document.createElement('span');
    indicator.className = 'badge bg-success';
    indicator.textContent = '●';
    const label = document.createElement('span');
    row.appendChild(indicator);
    row.appendChild(label);
    participantList.appendChild(row);
  }
  const label = row.querySelector('span:nth-child(2)');
  if (label) {
    label.textContent = name;
  }
}

function removeParticipantRow(peerId) {
  if (!participantList) return;
  const lookupId = peerId === selfPeerId ? 'self' : peerId;
  const row = participantList.querySelector(`[data-peer-id="${lookupId}"]`);
  if (row && row.dataset.peerId !== 'self') {
    row.remove();
  }
}

function ensureRemoteTile(peerId, name) {
  let tile = videoWall.querySelector(`[data-peer-tile="${peerId}"]`);
  if (!tile) {
    tile = document.createElement('div');
    tile.className = 'video-tile';
    tile.dataset.peerTile = peerId;
    const video = document.createElement('video');
    video.autoplay = true;
    video.playsInline = true;      // ← critical for iOS/Safari
    video.muted = false;           // ← make sure remote video isn’t muted
    const label = document.createElement('span');
    label.className = 'video-label';
    label.textContent = name || 'Connecting…';
    tile.appendChild(video);
    tile.appendChild(label);
    videoWall.appendChild(tile);
    peers.set(peerId, { pc: null, tile, video, label, senders: {} });
  } else if (name) {
    const label = tile.querySelector('.video-label');
    if (label) {
      label.textContent = name;
    }
  }
  const peer = peers.get(peerId);
  if (peer && name) {
    peer.label.textContent = name;
  }
  return peers.get(peerId);
}

function removePeer(peerId) {
  const peer = peers.get(peerId);
  if (peer) {
    if (peer.pc) {
      try {
        peer.pc.ontrack = null;
        peer.pc.onicecandidate = null;
        peer.pc.onconnectionstatechange = null;
        peer.pc.close();
      } catch (err) {
        console.error('Failed closing peer', peerId, err);
      }
    }
    if (peer.tile) {
      peer.tile.remove();
    }
    peers.delete(peerId);
  }
}

function sendJson(payload) {
  if (websocket && websocket.readyState === WebSocket.OPEN) {
    websocket.send(JSON.stringify(payload));
  }
}

function sendSignal(target, data) {
  sendJson({ type: 'signal', target, data });
}

async function negotiateOffer(peerId) {
  const peer = peers.get(peerId);
  if (!peer || !peer.pc) return;
  try {
    const offer = await peer.pc.createOffer();
    await peer.pc.setLocalDescription(offer);
    sendSignal(peerId, { type: 'offer', sdp: peer.pc.localDescription });
  } catch (err) {
    console.error('Offer negotiation failed', err);
  }
}

async function handleSignal(peerId, data) {
  let peer = peers.get(peerId);
  if (!peer || !peer.pc) {
    peer = await createPeerConnection(peerId, participants.get(peerId));
  }
  if (!peer || !peer.pc) return;
  try {
    if (data.type === 'offer') {
      await peer.pc.setRemoteDescription(new RTCSessionDescription(data.sdp));
      const answer = await peer.pc.createAnswer();
      await peer.pc.setLocalDescription(answer);
      sendSignal(peerId, { type: 'answer', sdp: peer.pc.localDescription });
    } else if (data.type === 'answer') {
      if (!peer.pc.currentRemoteDescription) {
        await peer.pc.setRemoteDescription(new RTCSessionDescription(data.sdp));
      }
    } else if (data.type === 'candidate' && data.candidate) {
      await peer.pc.addIceCandidate(new RTCIceCandidate(data.candidate));
    }
  } catch (err) {
    console.error('Signal handling failed', err);
  }
}

async function createPeerConnection(peerId, name) {
  let peer = peers.get(peerId);
  if (peer && peer.pc) {
    if (name) {
      peer.label.textContent = name;
    }
    return peer;
  }

  peer = ensureRemoteTile(peerId, name || participants.get(peerId));
  const pc = new RTCPeerConnection({
    iceServers: [
      { urls: 'stun:stun.l.google.com:19302' },
      // 🚀 Optional but highly recommended for mobile users:
      // Replace these with your actual TURN server credentials once set up
      {
        urls: 'turn:turn.yourdomain.com:3478',
        username: 'turnuser',
        credential: 'turnpassword'
      }
    ]
  });
  
  peer.pc = pc;


  pc.ontrack = (event) => {
    if (!peer.video) return;
    const [stream] = event.streams;
    if (stream) {
      peer.video.srcObject = stream;
  
      // ✅ Force playback on mobile (Safari/iOS/Android)
      peer.video
        .play()
        .catch(err => console.warn('Autoplay blocked on mobile, will resume after user gesture:', err));
    }
  };

  pc.onicecandidate = (event) => {
    if (event.candidate) {
      sendSignal(peerId, { type: 'candidate', candidate: event.candidate });
    }
  };

  pc.onconnectionstatechange = () => {
    if (pc.connectionState === 'failed' || pc.connectionState === 'disconnected') {
      appendSystemMessage(`${participants.get(peerId) || 'Peer'} connection lost.`);
    }
  };

  peer.senders = peer.senders || {};
  if (audioTrack && !peer.senders.audio) {
    try {
      peer.senders.audio = pc.addTrack(audioTrack, localStream);
    } catch (err) {
      console.error('Unable to add audio track', err);
    }
  }
  if (currentVideoTrack && !peer.senders.video) {
    try {
      peer.senders.video = pc.addTrack(currentVideoTrack, localStream);
    } catch (err) {
      console.error('Unable to add video track', err);
    }
  }

  return peer;
}

function updateParticipant(peerId, name) {
  participants.set(peerId, name);
  ensureParticipantRow(peerId, name);
  if (peerId !== selfPeerId) {
    ensureRemoteTile(peerId, name);
  }
}

function dropParticipant(peerId) {
  participants.delete(peerId);
  removeParticipantRow(peerId);
  if (peerId !== selfPeerId) {
    removePeer(peerId);
  }
}

async function initLocalMedia() {
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: true });
    cameraStream.getAudioTracks().forEach((track) => {
      audioTrack = track;
      localStream.addTrack(track);
    });
    cameraStream.getVideoTracks().forEach((track) => {
      cameraTrack = track;
      currentVideoTrack = track;
      localStream.addTrack(track);
    });
    if (localStream.getTracks().length > 0) {
      localVideo.srcObject = localStream;
    }
    if (toggleAudioBtn) {
      toggleAudioBtn.disabled = !audioTrack;
      toggleAudioBtn.textContent = audioTrack ? '🔊 Audio On' : '🔇 No Audio';
    }
    if (toggleVideoBtn) {
      toggleVideoBtn.disabled = !currentVideoTrack;
      toggleVideoBtn.textContent = currentVideoTrack ? '🎥 Video On' : '🚫 Video Off';
    }
    const statusParts = [`Ready – connected as ${displayName}`];
    if (capacity.participants_per_room_limit) {
      statusParts.push(`Room cap ${capacity.participants_per_room_limit}`);
    } else {
      statusParts.push('Room cap unlimited');
    }
    if (capacity.rooms_limit) {
      statusParts.push(`${capacity.rooms_limit} rooms available`);
    }
    updateStatus(statusParts.join(' · '), 'success');
  } catch (err) {
    console.error('Media access failed', err);
    updateStatus('Microphone or camera unavailable. Chat only mode.', 'warning');
    if (toggleAudioBtn) {
      toggleAudioBtn.disabled = true;
      toggleAudioBtn.textContent = '🔇 No Audio';
    }
    if (toggleVideoBtn) {
      toggleVideoBtn.disabled = true;
      toggleVideoBtn.textContent = '🚫 No Video';
    }
  }
}

function toggleAudio() {
  if (!audioTrack) return;
  audioTrack.enabled = !audioTrack.enabled;
  toggleAudioBtn.classList.toggle('btn-outline-light', audioTrack.enabled);
  toggleAudioBtn.classList.toggle('btn-danger', !audioTrack.enabled);
  toggleAudioBtn.textContent = audioTrack.enabled ? '🔊 Audio On' : '🔇 Audio Off';
}

function toggleVideo() {
  if (!currentVideoTrack) return;
  currentVideoTrack.enabled = !currentVideoTrack.enabled;
  toggleVideoBtn.classList.toggle('btn-outline-light', currentVideoTrack.enabled);
  toggleVideoBtn.classList.toggle('btn-danger', !currentVideoTrack.enabled);
  toggleVideoBtn.textContent = currentVideoTrack.enabled ? '🎥 Video On' : '🚫 Video Off';
}

async function startScreenShare() {
  if (usingScreenShare) {
    stopScreenShare();
    return;
  }
  try {
    const screenStream = await navigator.mediaDevices.getDisplayMedia({ video: true });
    screenTrack = screenStream.getVideoTracks()[0];
    if (!screenTrack) return;
    usingScreenShare = true;
    shareScreenBtn.classList.remove('btn-outline-light');
    shareScreenBtn.classList.add('btn-success');
    shareScreenBtn.textContent = '🛑 Stop Share';

    replaceVideoTrack(screenTrack);
    screenTrack.onended = () => {
      stopScreenShare();
    };
  } catch (err) {
    console.error('Screen share failed', err);
  }
}

function stopScreenShare() {
  if (!usingScreenShare) return;
  usingScreenShare = false;
  if (screenTrack) {
    screenTrack.stop();
    localStream.removeTrack(screenTrack);
    screenTrack = null;
  }
  if (cameraTrack) {
    replaceVideoTrack(cameraTrack);
  }
  shareScreenBtn.classList.add('btn-outline-light');
  shareScreenBtn.classList.remove('btn-success');
  shareScreenBtn.textContent = '🖥️ Share Screen';
}

function replaceVideoTrack(newTrack) {
  if (!newTrack) return;
  if (currentVideoTrack && localStream.getVideoTracks().includes(currentVideoTrack)) {
    localStream.removeTrack(currentVideoTrack);
  }
  currentVideoTrack = newTrack;
  localStream.addTrack(newTrack);
  localVideo.srcObject = null;
  localVideo.srcObject = localStream;

  peers.forEach((peer) => {
    if (peer.senders && peer.senders.video) {
      peer.senders.video.replaceTrack(newTrack).catch((err) => {
        console.error('replaceTrack failed', err);
      });
    }
  });
}

function setupChat() {
  if (!chatForm) return;
  chatForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const value = chatInput.value.trim();
    if (!value) return;
    sendJson({ type: 'chat', text: value });
    chatInput.value = '';
  });
}

function setupControls() {
  if (toggleAudioBtn) {
    toggleAudioBtn.addEventListener('click', toggleAudio);
  }
  if (toggleVideoBtn) {
    toggleVideoBtn.addEventListener('click', toggleVideo);
  }
  if (shareScreenBtn) {
    shareScreenBtn.addEventListener('click', startScreenShare);
  }
  if (refreshConnectionsBtn) {
    refreshConnectionsBtn.addEventListener('click', () => {
      peers.forEach((peer, peerId) => {
        if (peerId === selfPeerId) return;
        negotiateOffer(peerId);
      });
    });
  }
}

function connectWebSocket() {
  if (!connectionAllowed) return;
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const wsUrl = `${protocol}://${window.location.host}/ws/meetings/${encodeURIComponent(roomId)}`;
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  updateStatus(`Connecting to meeting · ${displayName}`, 'info');
  websocket = new WebSocket(wsUrl);

  websocket.addEventListener('open', () => {
    updateStatus(`Connected to meeting · ${displayName}`, 'success');
    sendJson({ type: 'join' });
  });

  websocket.addEventListener('close', (event) => {
    if (!connectionAllowed || event.code === 4403 || event.code === 4401) {
      return;
    }
    updateStatus('Disconnected from meeting space.', 'danger');
    appendSystemMessage('Connection closed. Attempting to reconnect…');
    const remotePeerIds = Array.from(peers.keys()).filter((id) => id !== selfPeerId);
    remotePeerIds.forEach((peerId) => dropParticipant(peerId));
    peers.clear();
    participants.clear();
    selfPeerId = null;
    reconnectTimer = setTimeout(connectWebSocket, 3000);
  });

  websocket.addEventListener('error', (event) => {
    console.error('WebSocket error', event);
    updateStatus('Connection issue detected.', 'warning');
  });

  websocket.addEventListener('message', (event) => {
    let message;
    try {
      message = JSON.parse(event.data);
    } catch (err) {
      return;
    }
    switch (message.type) {
      case 'init': {
        selfPeerId = message.peer_id;
        updateParticipant(selfPeerId, `${displayName} (You)`);
        (message.participants || []).forEach((peer) => {
          if (!peer || peer.peer_id === selfPeerId) return;
          updateParticipant(peer.peer_id, peer.display_name || 'Ambassador');
          createPeerConnection(peer.peer_id, peer.display_name);
          negotiateOffer(peer.peer_id);
        });
        break;
      }
      case 'peer-joined': {
        const peer = message.peer;
        if (!peer || peer.peer_id === selfPeerId) break;
        appendSystemMessage(`${peer.display_name || 'Ambassador'} joined the meeting.`);
        updateParticipant(peer.peer_id, peer.display_name || 'Ambassador');
        break;
      }
      case 'peer-left': {
        const peerId = message.peer_id;
        if (!peerId) break;
        const name = participants.get(peerId);
        appendSystemMessage(`${name || 'Ambassador'} left the meeting.`);
        dropParticipant(peerId);
        break;
      }
      case 'chat': {
        appendChatMessage({
          peerId: message.peer_id,
          name: message.display_name,
          text: message.text,
          timestamp: message.timestamp,
        });
        break;
      }
      case 'signal': {
        handleSignal(message.peer_id, message.data);
        break;
      }
      case 'capacity': {
        connectionAllowed = false;
        if (reconnectTimer) {
          clearTimeout(reconnectTimer);
          reconnectTimer = null;
        }
        const reason = message.message || 'Meeting capacity reached.';
        updateStatus(reason, 'warning');
        appendSystemMessage(`⚠️ ${reason}`);
        if (message.metrics) {
          const { rooms_active, rooms_limit, participants_active, participants_per_room_limit } = message.metrics;
          const roomSummary = rooms_limit ? `${rooms_active}/${rooms_limit} rooms in use` : `${rooms_active} rooms active`;
          const participantSummary = participants_per_room_limit
            ? `${participants_active} ambassadors connected (cap ${participants_per_room_limit} per room)`
            : `${participants_active} ambassadors connected`;
          appendSystemMessage(`Current load: ${roomSummary}, ${participantSummary}.`);
        }
        const remotePeers = Array.from(peers.keys()).filter((id) => id !== selfPeerId);
        remotePeers.forEach((peerId) => dropParticipant(peerId));
        peers.clear();
        participants.clear();
        selfPeerId = null;
        if (websocket && websocket.readyState === WebSocket.OPEN) {
          try {
            websocket.close(4403, 'capacity');
          } catch (err) {
            console.warn('Unable to close capacity-limited socket', err);
          }
        }
        websocket = null;
        break;
      }
      case 'admin-disconnect': {
        connectionAllowed = false;
        const reason = message.message || 'You were removed by a meeting administrator.';
        updateStatus(reason, 'danger');
        appendSystemMessage(`⚠️ ${reason}`);
        const remotePeers = Array.from(peers.keys()).filter((id) => id !== selfPeerId);
        remotePeers.forEach((peerId) => dropParticipant(peerId));
        peers.clear();
        participants.clear();
        selfPeerId = null;
        if (websocket && websocket.readyState === WebSocket.OPEN) {
          try {
            websocket.close(4401, 'admin');
          } catch (err) {
            console.warn('Unable to close admin-disconnected socket', err);
          }
        }
        break;
      }
      case 'error': {
        appendSystemMessage(`⚠️ ${message.message || 'Signal delivery failed.'}`);
        break;
      }
      case 'pong':
      default:
        break;
    }
  });
}

(async function bootstrap() {
  await initLocalMedia();
  setupChat();
  setupControls();
  if (capacity.participants_per_room_limit || capacity.rooms_limit) {
    const perRoom = capacity.participants_per_room_limit
      ? `${capacity.participants_per_room_limit} participants per room`
      : 'Unlimited participants per room';
    const rooms = capacity.rooms_limit
      ? `${capacity.rooms_limit} concurrent rooms`
      : 'Unlimited rooms';
    const total = capacity.estimated_total_capacity
      ? `Total simultaneous ambassadors: ~${capacity.estimated_total_capacity}.`
      : '';
    appendSystemMessage(`Capacity guidance: ${perRoom}, ${rooms}. ${total}`.trim());
  }
  connectWebSocket();
})();
