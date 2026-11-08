HTML_PAGE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Speech-to-Text Dashboard</title>
<style>
:root { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #172033; background: #f4f6fb; }
* { box-sizing: border-box; }
body { margin: 0; }
header { background: #172554; color: white; padding: 23px 5%; }
header h1 { margin: 0 0 5px; font-size: 25px; }
header p { margin: 0; color: #c7d2fe; font-size: 14px; }
main { max-width: 1250px; margin: 26px auto; padding: 0 20px 40px; }
.grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 15px; margin-bottom: 20px; }
.layout { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 20px; align-items: start; }
.card { min-width: 0; background: white; border: 1px solid #e2e8f0; border-radius: 14px; padding: 20px; box-shadow: 0 3px 12px rgba(15, 23, 42, .035); }
h2 { font-size: 18px; margin: 0 0 8px; }
.subheading { color: #64748b; font-size: 13px; margin: 0 0 18px; }
.status-label { color: #64748b; font-size: 13px; }
.status-value { font-size: 21px; font-weight: 700; margin-top: 8px; }
.controls, .actions { display: flex; flex-wrap: wrap; gap: 9px; }
.controls { margin-bottom: 13px; }
button { border: 0; border-radius: 8px; padding: 10px 14px; cursor: pointer; font-size: 13px; font-weight: 600; }
button:disabled { opacity: .45; cursor: not-allowed; }
.primary { color: white; background: #3156d3; }
.secondary { color: #172033; background: #e8edf6; }
.danger { color: #b42318; background: #fee4e2; }
.small { padding: 7px 10px; }
#connectionStatus { color: #64748b; font-size: 13px; margin: 10px 0; }
#transcript { width: 100%; height: 280px; resize: vertical; border: 1px solid #d7deea; border-radius: 10px; padding: 14px; font: inherit; font-size: 15px; line-height: 1.7; color: #172033; background: #fbfcff; }
.note, .help { color: #64748b; font-size: 12px; line-height: 1.5; }
.field { margin-bottom: 13px; }
label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 6px; }
input[type="text"], textarea.field-input { width: 100%; padding: 11px 12px; border: 1px solid #d7deea; border-radius: 8px; font: inherit; font-size: 14px; background: white; }
textarea.field-input { min-height: 78px; resize: vertical; }
.help { margin-top: 5px; }
.message { font-size: 13px; margin-top: 10px; min-height: 18px; }
.error { color: #b42318; }
.success { color: #067647; }
.search-row { display: flex; gap: 8px; margin: 20px 0 12px; }
.search-row input { flex: 1; min-width: 0; }
.term-list { display: flex; flex-direction: column; gap: 10px; }
.term { border: 1px solid #e2e8f0; border-radius: 10px; padding: 13px; overflow-wrap: anywhere; }
.term-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.term-name { font-weight: 700; }
.term-variations { color: #64748b; font-size: 12px; margin-top: 6px; }
.term-actions { display: flex; gap: 6px; flex-shrink: 0; }
.badge { display: inline-block; border-radius: 20px; padding: 4px 8px; background: #e8edf6; font-size: 11px; margin-top: 7px; }
.empty { color: #64748b; font-size: 13px; padding: 14px 0; }
@media (max-width: 850px) { .layout, .grid { grid-template-columns: 1fr; } main { margin-top: 16px; padding: 0 12px 25px; } header { padding: 20px 16px; } }
</style>
</head>
<body>
<header>
    <h1>Speech-to-Text Dashboard</h1>
    <p>Real-time transcription and custom vocabulary management</p>
</header>
<main>
    <section class="grid">
        <div class="card"><div class="status-label">API status</div><div class="status-value" id="apiStatus">Checking...</div></div>
        <div class="card"><div class="status-label">Parakeet Redux model</div><div class="status-value" id="modelStatus">Checking...</div></div>
        <div class="card"><div class="status-label">Vocabulary terms</div><div class="status-value" id="termCount">—</div></div>
    </section>
    <section class="layout">
        <div class="card">
            <h2>Live transcription</h2>
            <p class="subheading">Live partial text appears while you speak; finalized text remains below it.</p>
            <div class="controls">
                <button class="primary" id="startButton">Start microphone</button>
                <button class="secondary" id="stopButton" disabled>Stop microphone</button>
                <button class="secondary" id="clearButton">Clear text</button>
            </div>
            <div id="connectionStatus">Microphone stopped</div>
            <textarea id="transcript" readonly aria-label="Live and finalized transcript" placeholder="Your speech will appear here as you speak..."></textarea>
            <p class="note">Finalized text stays visible when the microphone stops. Starting a new session clears the box.</p>
        </div>
        <div class="card">
            <h2 id="formTitle">Add custom vocabulary</h2>
            <p class="subheading">Manage vocabulary without editing Python code.</p>
            <form id="vocabularyForm">
                <div class="field"><label for="correctTerm">Correct Term *</label><input id="correctTerm" type="text" maxlength="200" required placeholder="e.g. LexisNexis"></div>
                <div class="field">
                    <label for="variations">Recognized Variations (optional)</label>
                    <textarea id="variations" class="field-input" placeholder="Enter one variation per line"></textarea>
                    <div class="help">Enter one variation per line or separate variations with commas. When editing, keep the variations you want to retain, add new ones, and remove any you no longer want.</div>
                </div>
                <div class="actions">
                    <button class="primary" id="saveButton" type="submit">Save term</button>
                    <button class="secondary" id="cancelEditButton" type="button" hidden>Cancel edit</button>
                </div>
                <div id="formMessage" class="message" role="status"></div>
            </form>
            <div class="search-row"><input type="text" id="searchInput" placeholder="Search terms and variations..." aria-label="Search vocabulary"><button class="secondary" id="searchButton" type="button">Search</button></div>
            <div id="termList" class="term-list"><div class="empty">Loading vocabulary...</div></div>
        </div>
    </section>
</main>
<script>
const $ = id => document.getElementById(id);
let socket = null;
let audioContext = null;
let microphoneStream = null;
let sourceNode = null;
let processor = null;
let isStopping = false;
let editingId = null;
let searchTimer = null;
let finalizedTranscript = "";
let partialTranscript = "";

function setConnectionStatus(message) { $("connectionStatus").textContent = message; }
function showFormMessage(message, type = "") {
    const element = $("formMessage");
    element.textContent = message;
    element.className = "message " + type;
}
async function apiRequest(url, options = {}) {
    const response = await fetch(url, {
        credentials: "same-origin",
        ...options,
        headers: { ...(options.body ? {"Content-Type": "application/json"} : {}), ...(options.headers || {}) }
    });
    if (response.status === 401) throw new Error("Authentication failed. Reload the page and sign in.");
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "Request failed.");
    return data;
}
async function refreshStatus() {
    try {
        const data = await apiRequest("/api/status");
        $("apiStatus").textContent = data.api_status === "online" ? "Online" : "Offline";
        $("modelStatus").textContent = data.model_status === "loaded" ? "Loaded" : "Unavailable";
        $("termCount").textContent = data.vocabulary_count;
    } catch (error) {
        $("apiStatus").textContent = "Unavailable";
        $("modelStatus").textContent = "Unknown";
        setConnectionStatus(error.message);
    }
}
function renderTranscript() {
    const box = $("transcript");
    const finalText = finalizedTranscript.trim();
    const partialText = partialTranscript.trim();
    box.value = finalText
        ? (partialText ? finalText + "\n" + partialText : finalText)
        : partialText;
    box.scrollTop = box.scrollHeight;
}

function appendFinalTranscript(text) {
    if (!text || !text.trim()) return;
    const cleanText = text.trim();
    finalizedTranscript = finalizedTranscript
        ? finalizedTranscript + "\n" + cleanText
        : cleanText;
    partialTranscript = "";
    renderTranscript();
}
function connectWebSocket() {
    return new Promise((resolve, reject) => {
        const scheme = location.protocol === "https:" ? "wss:" : "ws:";
        const ws = new WebSocket(scheme + "//" + location.host + "/ws");
        socket = ws;
        let settled = false;
        ws.onopen = () => { settled = true; setConnectionStatus("Connected — listening for speech"); resolve(); };
        ws.onmessage = event => {
            let message;
            try { message = JSON.parse(event.data); } catch { return; }
            if (message.type === "status") setConnectionStatus(message.text || "Connected");
            else if (message.type === "partial") {
                partialTranscript = (message.text || "").trim();
                renderTranscript();
            }
            else if (message.type === "final") appendFinalTranscript(message.text);
            else if (message.type === "error") setConnectionStatus(message.text || message.message || "Transcription error");
        };
        ws.onerror = () => {
            setConnectionStatus("WebSocket connection error");
            if (!settled) { settled = true; reject(new Error("Could not connect to the WebSocket API.")); }
        };
        ws.onclose = () => {
            if (!isStopping) setConnectionStatus("WebSocket disconnected");
            if (!settled) { settled = true; reject(new Error("WebSocket connection closed before opening.")); }
        };
    });
}
function resampleTo16k(samples, inputRate) {
    const outputRate = 16000;
    if (inputRate === outputRate) return samples;
    const ratio = inputRate / outputRate;
    const outputLength = Math.floor(samples.length / ratio);
    const output = new Float32Array(outputLength);
    for (let i = 0; i < outputLength; i++) {
        const start = Math.floor(i * ratio);
        const end = Math.min(Math.floor((i + 1) * ratio), samples.length);
        let sum = 0, count = 0;
        for (let j = start; j < end; j++) { sum += samples[j]; count++; }
        output[i] = count ? sum / count : 0;
    }
    return output;
}
function floatToPCM16(samples) {
    const pcm = new Int16Array(samples.length);
    for (let i = 0; i < samples.length; i++) {
        const value = Math.max(-1, Math.min(1, samples[i]));
        pcm[i] = value < 0 ? value * 32768 : value * 32767;
    }
    return pcm;
}
async function startMicrophone() {
    if (microphoneStream) return;
    if (!navigator.mediaDevices?.getUserMedia) { setConnectionStatus("Microphone access requires HTTPS or localhost."); return; }
    $("startButton").disabled = true;
    isStopping = false;
    finalizedTranscript = "";
    partialTranscript = "";
    renderTranscript();
    try {
        microphoneStream = await navigator.mediaDevices.getUserMedia({audio: {channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true}});
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        audioContext = new AudioContextClass();
        if (audioContext.state === "suspended") await audioContext.resume();
        await connectWebSocket();
        sourceNode = audioContext.createMediaStreamSource(microphoneStream);
        processor = audioContext.createScriptProcessor(4096, 1, 1);
        processor.onaudioprocess = event => {
            if (!socket || socket.readyState !== WebSocket.OPEN) return;
            const samples = event.inputBuffer.getChannelData(0);
            const pcm = floatToPCM16(resampleTo16k(samples, audioContext.sampleRate));
            socket.send(pcm.buffer);
        };
        sourceNode.connect(processor);
        processor.connect(audioContext.destination);
        $("stopButton").disabled = false;
        setConnectionStatus("Microphone active");
    } catch (error) {
        setConnectionStatus("Could not start microphone: " + error.message);
        await stopMicrophone(false);
    } finally { $("startButton").disabled = false; }
}
function delay(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }
async function stopMicrophone(updateStatus = true) {
    isStopping = true;
    if (socket && socket.readyState === WebSocket.OPEN && audioContext) {
        try {
            for (let i = 0; i < 12; i++) {
                if (!socket || socket.readyState !== WebSocket.OPEN) break;
                socket.send(new Int16Array(1600).buffer);
                await delay(100);
            }
            await delay(250);
        } catch (error) { console.warn("Could not flush final audio:", error); }
    }
    if (processor) { processor.onaudioprocess = null; try { processor.disconnect(); } catch {} processor = null; }
    if (sourceNode) { try { sourceNode.disconnect(); } catch {} sourceNode = null; }
    if (microphoneStream) { microphoneStream.getTracks().forEach(track => track.stop()); microphoneStream = null; }
    if (audioContext) { try { await audioContext.close(); } catch {} audioContext = null; }
    if (socket) {
        const oldSocket = socket; socket = null;
        if (oldSocket.readyState === WebSocket.OPEN || oldSocket.readyState === WebSocket.CONNECTING) { try { oldSocket.close(); } catch {} }
    }
    $("stopButton").disabled = true;
    if (updateStatus) setConnectionStatus("Microphone stopped. Finalized text is preserved.");
}

// Accept comma-separated and newline-separated variations, trim whitespace,
// and remove duplicates without considering capitalization.
function parseVariations(value) {
    const seen = new Set();
    const variations = [];
    for (const rawItem of value.split(/[\n,]+/)) {
        const item = rawItem.trim();
        if (!item || item.length > 200) continue;
        const key = item.toLocaleLowerCase();
        if (seen.has(key)) continue;
        seen.add(key);
        variations.push(item);
    }
    return variations;
}
function resetForm() {
    editingId = null;
    $("vocabularyForm").reset();
    $("formTitle").textContent = "Add custom vocabulary";
    $("saveButton").textContent = "Save term";
    $("cancelEditButton").hidden = true;
    showFormMessage("");
}
async function loadVocabulary() {
    const search = $("searchInput").value.trim();
    $("termList").replaceChildren();
    try {
        const data = await apiRequest("/api/vocabulary?search=" + encodeURIComponent(search));
        $("termCount").textContent = data.count;
        if (!data.items.length) {
            const empty = document.createElement("div"); empty.className = "empty"; empty.textContent = "No vocabulary terms found."; $("termList").appendChild(empty); return;
        }
        for (const item of data.items) {
            const card = document.createElement("div"); card.className = "term";
            const head = document.createElement("div"); head.className = "term-head";
            const info = document.createElement("div");
            const name = document.createElement("div"); name.className = "term-name"; name.textContent = item.correct_term; info.appendChild(name);
            const variations = document.createElement("div"); variations.className = "term-variations";
            variations.textContent = item.recognized_variations.length ? "Variations: " + item.recognized_variations.join(", ") : "No explicit variations — fuzzy matching only"; info.appendChild(variations);
            const badge = document.createElement("span"); badge.className = "badge"; badge.textContent = "Correction enabled"; info.appendChild(badge);
            const actions = document.createElement("div"); actions.className = "term-actions";
            const edit = document.createElement("button"); edit.className = "secondary small"; edit.textContent = "Edit"; edit.addEventListener("click", () => editVocabulary(item));
            const remove = document.createElement("button"); remove.className = "danger small"; remove.textContent = "Delete"; remove.addEventListener("click", () => deleteVocabulary(item));
            actions.append(edit, remove); head.append(info, actions); card.appendChild(head); $("termList").appendChild(card);
        }
    } catch (error) {
        const message = document.createElement("div"); message.className = "empty"; message.textContent = error.message; $("termList").appendChild(message);
    }
}
function editVocabulary(item) {
    editingId = item.id;
    $("correctTerm").value = item.correct_term;
    // Show the existing list so users can add to it or edit it.
    $("variations").value = Array.isArray(item.recognized_variations) ? item.recognized_variations.join("\n") : "";
    $("formTitle").textContent = "Edit custom vocabulary";
    $("saveButton").textContent = "Update term";
    $("cancelEditButton").hidden = false;
    showFormMessage("");
    $("correctTerm").focus();
}
async function deleteVocabulary(item) {
    if (!confirm('Delete "' + item.correct_term + '"?')) return;
    try {
        await apiRequest("/api/vocabulary/" + encodeURIComponent(item.id), {method: "DELETE"});
        showFormMessage("Vocabulary term deleted.", "success");
        await loadVocabulary(); await refreshStatus();
    } catch (error) { showFormMessage(error.message, "error"); }
}
$("vocabularyForm").addEventListener("submit", async event => {
    event.preventDefault();
    const correctTerm = $("correctTerm").value.trim();
    if (!correctTerm) { showFormMessage("Correct Term is required.", "error"); return; }

    // When editing, editVocabulary() loads the saved variations into this
    // textarea. Parse the complete current contents so existing and newly
    // added variations are submitted together. Newlines and commas both work.
    const variations = parseVariations($("variations").value);

    const payload = {correct_term: correctTerm, recognized_variations: variations};
    const editing = Boolean(editingId);
    const url = editing ? "/api/vocabulary/" + encodeURIComponent(editingId) : "/api/vocabulary";
    const saveButton = $("saveButton");
    saveButton.disabled = true;
    try {
        await apiRequest(url, {method: editing ? "PUT" : "POST", body: JSON.stringify(payload)});
        resetForm();
        showFormMessage(editing ? "Vocabulary term updated." : "Vocabulary term added.", "success");
        await loadVocabulary(); await refreshStatus();
    } catch (error) { showFormMessage(error.message, "error"); }
    finally { saveButton.disabled = false; }
});
$("cancelEditButton").addEventListener("click", resetForm);
$("startButton").addEventListener("click", startMicrophone);
$("stopButton").addEventListener("click", () => stopMicrophone());
$("clearButton").addEventListener("click", () => { finalizedTranscript = ""; partialTranscript = ""; renderTranscript(); });
$("searchButton").addEventListener("click", loadVocabulary);
$("searchInput").addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(loadVocabulary, 250); });
window.addEventListener("beforeunload", () => {
    if (microphoneStream) microphoneStream.getTracks().forEach(track => track.stop());
    if (socket) socket.close();
});
refreshStatus();
loadVocabulary();
setInterval(refreshStatus, 15000);
</script>
</body>
</html>
"""
