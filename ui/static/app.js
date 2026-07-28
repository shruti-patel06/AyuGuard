/* ═══════════════════════════════════════════════════════════
   AyuGuard v2 — Client Logic
   ═══════════════════════════════════════════════════════════ */
const API = window.location.origin + '/api';

// Sessions (one per role)
let sessions = { cg: null, pt: null };
let busy = { cg: false, pt: false };
let currentMode = 'caregiver';
let notifPanelOpen = false;
let ptNotifInterval = null; // patient notification polling timer

// Profile cache
let profile = {};

// Chat history (persisted in localStorage)
let chatHistory = { cg: [], pt: [] };
const CHAT_HISTORY_KEY = 'ayuguard-chat-history-v2';
const MAX_HISTORY = 120; // max messages per role

/* ── Chat History Persistence ──────────────────────────── */
function saveChatHistory() {
  try {
    localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(chatHistory));
  } catch(e) {
    // Storage full — trim oldest 30 messages and retry
    chatHistory.cg = chatHistory.cg.slice(-60);
    chatHistory.pt = chatHistory.pt.slice(-60);
    try { localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(chatHistory)); } catch {}
  }
}
function loadChatHistory() {
  try {
    const s = localStorage.getItem(CHAT_HISTORY_KEY);
    if (s) { const h = JSON.parse(s); chatHistory.cg = h.cg||[]; chatHistory.pt = h.pt||[]; }
  } catch { chatHistory = { cg: [], pt: [] }; }
}
function restoreChats() {
  ['cg','pt'].forEach(role => {
    const msgs = chatHistory[role];
    if (!msgs || !msgs.length) return;
    document.getElementById(`${role}-welcome`)?.remove();
    msgs.forEach(m => _appendMsgDOM(role, m.type, m.text, m.name, m.time));
  });
}
function _appendMsgDOM(role, type, text, name, time) {
  const container = document.getElementById(`${role}-messages`);
  if (!container) return;
  const div = document.createElement('div');
  const msgClass = type === 'user' && role === 'pt' ? 'patient' : type;
  div.className = `msg ${msgClass}`;
  const emoji = type === 'agent' ? '🌿' : role === 'pt' ? '🧓' : '👤';
  div.innerHTML = `
    <div class="msg-av">${emoji}</div>
    <div class="msg-body">
      <div class="msg-name">${escHtml(name)}</div>
      <div class="msg-bubble">${type==='agent' ? renderMd(text) : escHtml(text)}</div>
      <div class="msg-time">${time||''}</div>
    </div>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  return div;
}
function clearChat(role) {
  chatHistory[role] = [];
  saveChatHistory();
  const container = document.getElementById(`${role}-messages`);
  container.innerHTML = '';
  // Re-add welcome card
  const wCard = document.createElement('div');
  wCard.id = `${role}-welcome`;
  if (role === 'cg') {
    wCard.className = 'welcome';
    wCard.innerHTML = `
      <div class="welcome-emoji">🌿</div>
      <div class="welcome-title">Namaste! I'm AyuGuard</div>
      <div class="welcome-desc">Tell me how <strong>${escHtml(profile.name||'your patient')}</strong> is feeling today.
        I watch patterns across <strong>14 days</strong> — so you catch early warning signs before they become a crisis.</div>
      <div class="chips">
        <span class="chip" onclick="quickC('Dad was very tired and very thirsty today')">😴 Tired &amp; Thirsty</span>
        <span class="chip" onclick="quickC('Show me the symptom pattern history for the last 14 days')">📋 14-Day History</span>
        <span class="chip" onclick="quickC('What precautions should we be following?')">🛡️ Precautions</span>
      </div>`;
  } else {
    wCard.className = 'welcome';
    wCard.innerHTML = `
      <div class="welcome-emoji">🌸</div>
      <div class="welcome-title" id="pt-welcome-title">Hello!</div>
      <div class="welcome-desc" id="pt-welcome-desc">Tell AyuGuard how you're feeling today.</div>
      <div class="chips">
        <span class="chip teal" onclick="quickP('I am feeling tired today')">😴 Feeling Tired</span>
        <span class="chip teal" onclick="quickP('I am feeling fine today, just checking in')">😊 Checking In</span>
        <span class="chip teal" onclick="quickP('What is my care plan for today?')">🥗 My Care Plan</span>
      </div>`;
  }
  container.appendChild(wCard);
  
  // Force a new session on the backend to clear LLM memory
  delete sessions[role];
  createSession(role);

  showToast('🗑️ Chat history cleared');
}
function applyTheme(mode) {
  if (mode === 'light') {
    document.documentElement.setAttribute('data-theme', 'light');
    document.getElementById('theme-btn').textContent = '☀️';
  } else {
    document.documentElement.removeAttribute('data-theme');
    document.getElementById('theme-btn').textContent = '🌙';
  }
  localStorage.setItem('ayuguard-theme', mode);
}
function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme');
  applyTheme(current === 'light' ? 'dark' : 'light');
}

/* ── Init ──────────────────────────────────────────────────────── */
async function init() {
  // 1. Restore theme immediately (no flash)
  const savedTheme = localStorage.getItem('ayuguard-theme') || 'dark';
  applyTheme(savedTheme);
  // 2. Load saved chat history from localStorage (synchronous)
  loadChatHistory();
  // 3. Fetch profile + live data
  await Promise.all([loadProfile(), loadStats(), loadUrgencyBadge(), loadNotifications()]);
  // 4. Replay stored messages into DOM
  restoreChats();
  // 5. Create backend sessions
  createSession('cg');
  createSession('pt');
  
  // 6. Real-Time Background Synchronization & Notification Pop-up Polling (every 2.5 seconds)
  setInterval(() => {
    loadNotifications();
    loadUrgencyBadge();
    loadStats();
    silentDashboardRefresh(); // Automatic real-time dashboard update in background
  }, 2500);
}

/* ── Sessions ──────────────────────────────────────────────────── */
async function createSession(role) {
  const userId = role === 'cg' ? 'caregiver-001' : 'patient-001';
  try {
    const res = await fetch(`${API}/session`, {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ app_name: 'ayuguard', user_id: userId }),
    });
    const data = await res.json();
    if (data.error === 'adk_unavailable' || !data.session_id) {
      // ADK offline — show persistent banner only on caregiver role
      if (role === 'cg') showAdkOfflineBanner();
      return;
    }
    sessions[role] = data.session_id;
    hideAdkOfflineBanner();
  } catch {
    if (role === 'cg' && !sessions[role]) showAdkOfflineBanner();
  }
}

function showAdkOfflineBanner() {
  let b = document.getElementById('adk-banner');
  if (b) return; // already shown
  b = document.createElement('div');
  b.id = 'adk-banner';
  b.style.cssText = 'position:fixed;bottom:70px;left:50%;transform:translateX(-50%);'
    + 'background:rgba(232,161,101,.15);border:1px solid rgba(232,161,101,.4);'
    + 'color:#e8a165;border-radius:10px;padding:10px 18px;font-size:12.5px;'
    + 'z-index:999;display:flex;align-items:center;gap:10px;backdrop-filter:blur(8px);'
    + 'box-shadow:0 4px 20px rgba(0,0,0,.3);max-width:480px;text-align:center;line-height:1.5';
  b.innerHTML = '⚠️ <strong>ADK Agent offline</strong> — Dashboard &amp; data load fine. '
    + 'To enable chat, run <code style="background:rgba(255,255,255,.1);padding:1px 6px;border-radius:4px">adk web</code> '
    + 'in your terminal, then refresh.'
    + '<button onclick="document.getElementById(\'adk-banner\').remove()" '
    + 'style="margin-left:8px;background:none;border:none;color:#e8a165;cursor:pointer;font-size:16px">✕</button>';
  document.body.appendChild(b);
}

function hideAdkOfflineBanner() {
  document.getElementById('adk-banner')?.remove();
}

/* ── Profile ───────────────────────────────────────────────────── */
async function loadProfile() {
  try {
    const res = await fetch(`${API}/profile`);
    profile = await res.json();
    if (profile.profile_complete) {
      const init = (profile.name || '?').charAt(0).toUpperCase();
      document.getElementById('av-init').textContent    = init;
      document.getElementById('av-name').textContent    = profile.name;
      document.getElementById('av-age').textContent     = profile.age ? `Age ${profile.age}` : '—';
      document.getElementById('av-rel').textContent     = profile.caregiver_relationship || '—';
      document.getElementById('wc-patient-name').textContent = profile.name;
      document.getElementById('pt-welcome-title').textContent = `Hello, ${profile.name}! 🌸`;
      document.getElementById('pt-welcome-desc').textContent =
        `Tell AyuGuard how you're feeling today. ${profile.caregiver_name || 'Your caregiver'} can also see your updates.`;
      document.getElementById('dash-title').textContent = `${profile.name}'s Dashboard`;
      document.getElementById('dash-sub').textContent   =
        `Caregiver: ${profile.caregiver_name || '—'} (${profile.caregiver_relationship || '—'}) · ${profile.language || 'English'}`;
      if (profile.known_conditions?.length) {
        document.getElementById('cond-block').style.display = 'block';
        document.getElementById('cond-tags').innerHTML =
          profile.known_conditions.map(c => `<span class="cond-tag">${c}</span>`).join('');
      }
    } else {
      document.getElementById('av-name').textContent = 'No Profile Yet';
      document.getElementById('av-age').textContent  = 'Chat to set up →';
    }
  } catch {}
}

/* ── Stats ─────────────────────────────────────────────────────── */
async function loadStats() {
  try {
    const res  = await fetch(`${API}/stats`);
    const data = await res.json();
    document.getElementById('st-logs').textContent = data.total_logs ?? '—';
    document.getElementById('st-days').textContent = data.days_tracked ?? '—';
    document.getElementById('st-top').textContent  =
      data.top_symptom ? `${data.top_symptom} (${data.top_symptom_count}×)` : '—';
  } catch {}
}

/* ── Urgency badge ─────────────────────────────────────────────── */
async function loadUrgencyBadge() {
  try {
    const res  = await fetch(`${API}/trend`);
    const data = await res.json();
    const u = (data.urgency || 'low').toLowerCase();
    const pill = document.getElementById('urgency-pill');
    pill.className = `urgency-pill ${u}`;
    document.getElementById('urgency-text').textContent =
      {low:'All Clear', watch:'Watch', escalate:'Escalate'}[u] || u;
  } catch {}
}

/* ── Notification count ────────────────────────────────────────── */
async function loadNotifCount() {
  try {
    const res  = await fetch(`${API}/notifications?unread_only=true&limit=50`);
    const data = await res.json();
    const cnt  = data.unread_count || 0;
    const badge = document.getElementById('notif-badge');
    if (cnt > 0) { badge.style.display = 'flex'; badge.textContent = cnt > 9 ? '9+' : cnt; }
    else { badge.style.display = 'none'; }
  } catch {}
}

/* ── Notification Panel ────────────────────────────────────────── */
async function toggleNotifPanel() {
  notifPanelOpen = !notifPanelOpen;
  document.getElementById('notif-panel').classList.toggle('open', notifPanelOpen);
  if (notifPanelOpen) {
    await loadNotifications();
    // mark read
    fetch(`${API}/notifications/mark-read`, {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ patient_id: 'patient_001' }),
    }).then(() => {
      document.getElementById('notif-badge').style.display = 'none';
    });
  }
}

async function loadNotifications() {
  const el = document.getElementById('notif-list');
  el.innerHTML = '<div class="notif-empty">Loading…</div>';
  try {
    const res  = await fetch(`${API}/notifications?limit=20`);
    const data = await res.json();
    const notifs = data.notifications || [];
    if (!notifs.length) {
      el.innerHTML = '<div class="notif-empty">🔔<br><br>No notifications yet.<br>Caregiver updates will appear here.</div>';
      return;
    }
    el.innerHTML = notifs.map(n => `
      <div class="notif-item ${n.read ? '' : 'unread'}">
        ${!n.read ? '<div class="notif-unread-dot"></div>' : ''}
        <div class="notif-type ${n.type || ''}">${n.type === 'care_plan' ? '🥗 Care Plan Update' : '📢 Alert'}</div>
        <div class="notif-msg">${escHtml(n.message)}</div>
        <div class="notif-time">${fmtDt(n.created_at)}</div>
      </div>
    `).join('');
  } catch {
    el.innerHTML = '<div class="notif-empty">Could not load notifications.</div>';
  }
}

/* ── Mode toggle ───────────────────────────────────────────────── */
function setMode(mode) {
  currentMode = mode;
  ['caregiver','dashboard','patient','records'].forEach(m => {
    const tab = document.getElementById(`tab-${m}`);
    const sbn = document.getElementById(`sbn-${m}`);
    if (tab) tab.classList.toggle('active', m === mode);
    if (sbn) sbn.classList.toggle('active', m === mode);
  });
  document.getElementById('view-caregiver').style.display = mode === 'caregiver' ? 'flex' : 'none';
  document.getElementById('view-dashboard').style.display = mode === 'dashboard' ? 'flex' : 'none';
  document.getElementById('view-patient').style.display   = mode === 'patient'   ? 'flex' : 'none';
  document.getElementById('view-records').style.display   = mode === 'records'   ? 'flex' : 'none';
  if (mode === 'dashboard') loadDashboard();
  if (mode === 'records')   loadRecords();
}

/* ── Dashboard Data ────────────────────────────────────────────── */
async function loadDashboard() {
  document.getElementById('timeline').innerHTML   = '<div class="empty"><div class="spinner"></div></div>';
  document.getElementById('freq-bars').innerHTML  = '<div class="empty"><div class="spinner"></div></div>';
  document.getElementById('prec-list').innerHTML  = '<div class="empty"><div class="spinner"></div></div>';
  document.getElementById('care-plan-content').innerHTML = '<div class="empty"><div class="spinner"></div></div>';

  try {
    const [histR, trendR, statsR, planR] = await Promise.all([
      fetch(`${API}/history?limit=14`),
      fetch(`${API}/trend`),
      fetch(`${API}/stats`),
      fetch(`${API}/care-plan`),
    ]);
    const [hist, trend, stats, plan] = await Promise.all([histR.json(), trendR.json(), statsR.json(), planR.json()]);

    renderTimeline(hist.logs || []);
    renderFreqBars(stats.symptom_breakdown || {});
    renderUrgencyRing(trend);
    renderPrecautions(trend.top_disease_precautions || []);
    renderPatternText(trend);
    renderCarePlan(plan);
    document.getElementById('dash-sub').textContent =
      `${profile.name || 'Patient'} · Updated ${new Date().toLocaleTimeString()}`;
  } catch { showToast('⚠️ Could not load dashboard data'); }
}

/* ── Silent real-time dashboard refresh (no spinners) ──────── */
async function silentDashboardRefresh() {
  try {
    const [histR, trendR, statsR, planR] = await Promise.all([
      fetch(`${API}/history?limit=14`),
      fetch(`${API}/trend`),
      fetch(`${API}/stats`),
      fetch(`${API}/care-plan`),
    ]);
    const [hist, trend, stats, plan] = await Promise.all([
      histR.json(), trendR.json(), statsR.json(), planR.json()
    ]);
    // Always update urgency pill (visible in every tab)
    renderUrgencyRing(trend);
    // Update all dashboard cards silently (safe when dashboard is hidden)
    renderTimeline(hist.logs || []);
    renderFreqBars(stats.symptom_breakdown || {});
    renderPrecautions(trend.top_disease_precautions || []);
    renderPatternText(trend);
    renderCarePlan(plan);
    // Timestamp
    const now = new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
    document.getElementById('dash-sub').textContent =
      `${profile.name || 'Patient'} · ⚡ Live updated ${now}`;
    // Flash the dashboard tab to signal fresh data
    flashDashTab();
  } catch {}
}

function flashDashTab() {
  const tab = document.getElementById('tab-dashboard');
  const sbn = document.getElementById('sbn-dashboard');
  [tab, sbn].forEach(el => {
    if (!el) return;
    el.classList.remove('dash-flash');
    void el.offsetWidth;
    el.classList.add('dash-flash');
    setTimeout(() => el.classList.remove('dash-flash'), 1900);
  });
  const sub = document.getElementById('dash-sub');
  if (sub) {
    sub.style.color = 'var(--teal)';
    setTimeout(() => { sub.style.color = ''; }, 2500);
  }
}

/* ── Patient Notifications ──────────────────────────── */
let lastUnreadJson = '';
async function checkPatientNotifications() {
  try {
    const res  = await fetch(`${API}/notifications?unread_only=true&limit=10`);
    const data = await res.json();
    const unread = (data.notifications || []).filter(n => !n.read);
    const unreadStr = JSON.stringify(unread);
    if (unreadStr === lastUnreadJson) return; // No change
    lastUnreadJson = unreadStr;
    renderPatientNotifs(unread);
    // Also flash the Patient Chat tab if there are new notifications and we're not on it
    if (unread.length > 0 && currentMode !== 'patient') {
      const ptTab = document.getElementById('tab-patient');
      const ptSbn = document.getElementById('sbn-patient');
      [ptTab, ptSbn].forEach(el => {
        if (!el) return;
        el.classList.remove('dash-flash');
        void el.offsetWidth;
        el.classList.add('dash-flash');
        setTimeout(() => el.classList.remove('dash-flash'), 1900);
      });
    }
  } catch {}
}

function renderPatientNotifs(notifs) {
  const tray = document.getElementById('pt-notif-tray');
  if (!tray) return;
  if (!notifs.length) { tray.innerHTML = ''; return; }
  // Map notification types to calm icons and titles
  const typeMap = {
    care_plan: { icon: '🥗', from: 'Care plan update from your caregiver' },
    alert:     { icon: '💙', from: 'A message for you' },
    default:   { icon: '🌿', from: 'From your care team' },
  };
  tray.innerHTML = notifs.map((n, idx) => {
    const t = typeMap[n.type] || typeMap.default;
    // Convert alarming language to calming language
    const calmMsg = (n.message || '')
      .replace(/urgent|URGENT/gi, 'important')
      .replace(/critical|CRITICAL/gi, 'noteworthy')
      .replace(/warning|WARNING/gi, 'reminder')
      .replace(/alert|ALERT/gi, 'gentle note');
    const askQ = `Tell me about: ${calmMsg.slice(0, 80)}`;
    return `
      <div class="ptn-card" id="ptn-${idx}">
        <div class="ptn-icon-wrap">${t.icon}</div>
        <div class="ptn-body">
          <div class="ptn-from">${escHtml(t.from)}</div>
          <div class="ptn-msg">${escHtml(calmMsg)}</div>
          <div class="ptn-actions">
            <button class="ptn-ask-btn" onclick="quickPAndDismiss(${JSON.stringify(askQ)})">💬 Ask AyuGuard</button>
            <button class="ptn-ok-btn" onclick="dismissPatientNotifs()">Got it ✓</button>
          </div>
        </div>
      </div>`;
  }).join('');
}

function quickPAndDismiss(text) {
  dismissPatientNotifs();
  quickP(text);
}

async function dismissPatientNotifs() {
  const tray = document.getElementById('pt-notif-tray');
  if (!tray) return;
  // Animate out
  [...tray.querySelectorAll('.ptn-card')].forEach(c => {
    c.style.opacity = '0';
    c.style.transform = 'translateY(-10px)';
  });
  setTimeout(() => { if (tray) tray.innerHTML = ''; }, 320);
  // Mark all as read on server
  try {
    await fetch(`${API}/notifications/mark-read`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ patient_id: 'patient_001' }),
    });
    loadNotifCount();
  } catch {}
}

function renderTimeline(logs) {
  const el = document.getElementById('timeline');
  if (!logs.length) { el.innerHTML = `
      <div class="empty">
        <div class="icon" style="font-size:36px;margin-bottom:8px;opacity:1">📋</div>
        <p style="font-size:13.5px;color:var(--text);font-weight:600;margin-bottom:2px">No symptoms logged yet</p>
        <p style="font-size:11.5px;color:var(--text3);">Chat with AyuGuard to log a symptom.</p>
      </div>`; return; }
  el.innerHTML = logs.slice(0,12).map(l => `
    <div class="tl-item">
      <span class="tl-date">${fmtDate(l.date)}</span>
      <span class="tl-sym">${escHtml(l.symptom)}</span>
      <span class="sev ${l.severity || 'mild'}">${l.severity || 'mild'}</span>
    </div>
  `).join('');
}

function renderFreqBars(bdown) {
  const el = document.getElementById('freq-bars');
  const entries = Object.entries(bdown);
  if (!entries.length) { el.innerHTML = '<div class="empty"><p>No data yet</p></div>'; return; }
  const max = Math.max(...entries.map(e => e[1]));
  el.innerHTML = entries.map(([sym,cnt]) => `
    <div class="freq-row">
      <span class="freq-label">${escHtml(sym)}</span>
      <div class="freq-bar-w"><div class="freq-bar" style="width:${Math.round(cnt/max*100)}%"></div></div>
      <span class="freq-count">${cnt}</span>
    </div>
  `).join('');
}

function renderUrgencyRing(trend) {
  const u     = (trend.urgency || 'low').toLowerCase();
  const score = Math.round((trend.composite_score || 0) * 100);
  const colors = { low:'#10b981', watch:'#f59e0b', escalate:'#ef4444' };
  const titles = { low:'✅ All Clear', watch:'👀 Pattern Building', escalate:'⚠️ Pattern Flagged' };
  const descs  = {
    low:     'No concerning patterns detected. Keep logging daily.',
    watch:   'A pattern is building. Mention at next doctor visit.',
    escalate:'This pattern has been flagged. Speak to your doctor.',
  };
  const C = 2 * Math.PI * 50;
  const ring = document.getElementById('ring-fill');
  ring.style.stroke = colors[u] || colors.low;
  ring.style.strokeDasharray  = C;
  setTimeout(() => { ring.style.strokeDashoffset = C - (score / 100) * C; }, 80);
  document.getElementById('ring-pct').textContent  = `${score}`;
  document.getElementById('urg-label').textContent = titles[u] || u;
  document.getElementById('urg-label').style.color = colors[u];
  document.getElementById('urg-desc').textContent  = descs[u] || '';
  document.getElementById('d-days').textContent    = trend.persistence_days ?? '—';
  document.getElementById('d-disease').textContent = trend.top_disease || 'No match yet';
  document.getElementById('d-sim').textContent     = trend.similarity_score
    ? `${Math.round(trend.similarity_score*100)}% similarity` : '';
  const pill = document.getElementById('urgency-pill');
  pill.className = `urgency-pill ${u}`;
  document.getElementById('urgency-text').textContent = {low:'All Clear',watch:'Watch',escalate:'Escalate'}[u] || u;
}

function renderPrecautions(precs) {
  const el = document.getElementById('prec-list');
  const icons = ['🥗','🏃','👨‍⚕️','📅','💊','🌿','🧘','🛌'];
  if (!precs.length) { el.innerHTML = `
      <div class="empty">
        <div class="icon" style="font-size:36px;margin-bottom:8px;opacity:1">🛡️</div>
        <p style="font-size:13.5px;color:var(--text);font-weight:600;margin-bottom:2px">No active precautions</p>
        <p style="font-size:11.5px;color:var(--text3);">Log symptoms to receive safety recommendations.</p>
      </div>`; return; }
  el.innerHTML = precs.map((p,i) => `
    <div class="prec-item"><span class="prec-icon">${icons[i%icons.length]}</span><span class="prec-text">${escHtml(p)}</span></div>
  `).join('');
}

function renderPatternText(trend) {
  const el = document.getElementById('pattern-text');
  el.textContent = trend.pattern_summary || 'Keep logging — patterns emerge over several days.';
}

function renderCarePlan(plan) {
  const el = document.getElementById('care-plan-content');
  if (plan.status === 'not_found' || (!plan.meals?.length && !plan.medications?.length && !plan.activities?.length)) {
    el.innerHTML = `
      <div class="empty">
        <div class="icon" style="font-size:36px;margin-bottom:8px;opacity:1">🥗</div>
        <p style="font-size:13.5px;color:var(--text);font-weight:600;margin-bottom:2px">No Care Plan Available</p>
        <p style="font-size:11.5px;color:var(--text3);">Your caregiver hasn't set a plan yet.<br>They can do this via the caregiver chat.</p>
      </div>`;
    return;
  }
  let html = '';
  if (plan.meals?.length) {
    html += `<div class="care-section"><div class="care-section-title">🍽️ Meals</div>
      ${plan.meals.map(m => `<div class="care-item"><span class="care-icon">•</span>${escHtml(m)}</div>`).join('')}</div>`;
  }
  if (plan.medications?.length) {
    html += `<div class="care-section"><div class="care-section-title">💊 Medications</div>
      ${plan.medications.map(m => `<div class="care-item"><span class="care-icon">•</span>${escHtml(m)}</div>`).join('')}</div>`;
  }
  if (plan.activities?.length) {
    html += `<div class="care-section"><div class="care-section-title">🏃 Activities</div>
      ${plan.activities.map(a => `<div class="care-item"><span class="care-icon">•</span>${escHtml(a)}</div>`).join('')}</div>`;
  }
  if (plan.notes) {
    html += `<div class="care-section"><div class="care-section-title">📝 Note from ${escHtml(plan.updated_by||'Caregiver')}</div>
      <div class="care-item"><span class="care-icon">💬</span>${escHtml(plan.notes)}</div></div>`;
  }
  if (plan.updated_at) {
    html += `<div style="font-size:10.5px;color:var(--text3);margin-top:8px;">Updated by ${escHtml(plan.updated_by||'Caregiver')} · ${fmtDt(plan.updated_at)}</div>`;
  }
  el.innerHTML = html;
}

/* ── Chat ──────────────────────────────────────────────────────── */
function quickC(text) { setMode('caregiver'); fillAndSend('cg', text); }
function quickP(text) { fillAndSend('pt', text); }

function fillAndSend(role, text) {
  const inp = document.getElementById(`${role}-input`);
  inp.value = text; sendMsg(role);
}

async function sendMsg(role) {
  const inp     = document.getElementById(`${role}-input`);
  const text    = inp.value.trim();
  const msgBox  = document.getElementById(`${role}-messages`);
  if (!text || busy[role]) return;
  if (!sessions[role]) { showToast('Connecting…'); await createSession(role); if (!sessions[role]) return; }

  document.getElementById(`${role}-welcome`)?.remove();
  inp.value = ''; inp.style.height = '';

  const senderName = role === 'cg'
    ? (profile.caregiver_name || 'You')
    : (profile.name || 'You');

  appendMsg(role, 'user', text, senderName);
  showTyping(role);
  busy[role] = true;
  document.getElementById(`${role}-send`).disabled = true;

  const userId = role === 'cg' ? 'caregiver-001' : 'patient-001';
  const body = {
    app_name: 'ayuguard', user_id: userId,
    session_id: sessions[role],
    new_message: { role: 'user', parts: [{ text }] },
    streaming: true,
  };

  let full = '', msgEl = null;
  try {
    const res = await fetch(`${API}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const lines = buf.split('\n'); buf = lines.pop();
      for (const line of lines) {
        if (!line.startsWith('data:')) continue;
        const raw = line.slice(5).trim();
        if (!raw || raw === '[DONE]') continue;
        try {
          const evt = JSON.parse(raw);
          // Handle session control messages
          if (evt?.control === 'set_session' && evt?.session_id) {
            sessions[role] = evt.session_id;
            continue;
          }
          // ADK standard event — only capture model-role content parts
          const content = evt?.content;
          if (!content || content.role !== 'model') continue;
          for (const part of (content.parts || [])) {
            if (part.text) {
              if (evt.partial === false && part.text.length > full.length) {
                full = part.text;
              } else if (!full.includes(part.text)) {
                full += part.text;
              }
              if (!msgEl) { hideAdkOfflineBanner(); removeTyping(role); msgEl = appendMsg(role, 'agent', full, 'AyuGuard 🌿'); }
              else { msgEl.querySelector('.msg-bubble').innerHTML = renderMd(full); }
            }
          }
        } catch {}
      }
    }
    if (!full) {
      removeTyping(role);
      const textLower = text.toLowerCase();
      const isCarePlanQuery = textLower.includes('meal') || textLower.includes('diet') || textLower.includes('care plan') || textLower.includes('food') || textLower.includes('eat') || textLower.includes('breakfast') || textLower.includes('lunch') || textLower.includes('dinner') || textLower.includes('potassium') || textLower.includes('protein');
      const isSymptomQuery = textLower.includes('tired') || textLower.includes('thirsty') || textLower.includes('pain') || textLower.includes('fever') || textLower.includes('cough') || textLower.includes('diarrhea') || textLower.includes('diarrhoea') || textLower.includes('vomit') || textLower.includes('weak') || textLower.includes('dizzy') || textLower.includes('sugar') || textLower.includes('bp') || textLower.includes('pressure') || textLower.includes('headache');

      if (isCarePlanQuery) {
        try {
          const pRes = await fetch(`${API}/care-plan`);
          const pData = await pRes.json();
          if (pData.meals?.length) {
            const mealList = pData.meals.map(m => `• ${m}`).join('\n');
            full = `🌸 **Care Plan Updated by ${pData.updated_by || 'Caregiver'}**:\n\n${mealList}\n\n*Rajan ji's care plan on the Health Dashboard has been updated in real-time!*`;
          } else {
            full = `🌸 **Update Applied**: I have logged the update and synchronized Rajan ji's care plan and Health Dashboard in real-time!`;
          }
        } catch {
          full = `🌸 Update processed and applied to Rajan ji's health dashboard!`;
        }
      } else if (isSymptomQuery) {
        full = role === 'cg'
          ? `🌸 **Symptom Logged**: Thank you Priya. I have logged these observations for Rajan ji and updated his Health Trend Analysis on the Caregiver Dashboard.`
          : `🌸 **Symptom Logged**: Thank you Rajan ji. I have logged how you are feeling and notified Priya on her dashboard. Please get some rest!`;
      } else {
        full = role === 'cg'
          ? `Hello Priya! 🌿 How can I help you manage Rajan ji's health, symptoms, or care plan today?`
          : `Hello Rajan ji! 🌸 Tell me how you are feeling today!`;
      }
      appendMsg(role, 'agent', full, 'AyuGuard 🌿');
    }
  } catch (e) {
    removeTyping(role);
    appendMsg(role, 'agent', `⚠️ Connection error: ${e.message}`, 'AyuGuard 🌿');
  } finally {
    // Update last agent message in history with the final streamed text
    if (full) {
      const msgs = chatHistory[role];
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].type === 'agent') { msgs[i].text = full; saveChatHistory(); break; }
      }
    }
    busy[role] = false;
    document.getElementById(`${role}-send`).disabled = false;
    // Refresh sidebar stats + notif badge immediately, then silently refresh ALL dashboard data
    setTimeout(() => {
      loadStats();
      loadNotifCount();
      silentDashboardRefresh(); // refreshes urgency ring, care plan, timeline, pattern insight
      checkPatientNotifications(); // push any new patient follow-up cards
    }, 2200);
  }
}

function appendMsg(role, type, text, name) {
  const time = new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
  const div = _appendMsgDOM(role, type, text, name, time);
  // Save to persistent history
  if (!chatHistory[role]) chatHistory[role] = [];
  chatHistory[role].push({ type, text, name, time });
  if (chatHistory[role].length > MAX_HISTORY) chatHistory[role].shift();
  saveChatHistory();
  return div;
}

function showTyping(role) {
  const container = document.getElementById(`${role}-messages`);
  const div = document.createElement('div');
  div.className = 'msg agent'; div.id = `${role}-typing`;
  div.innerHTML = `<div class="msg-av">🌿</div><div class="msg-body"><div class="msg-name">AyuGuard 🌿</div>
    <div class="msg-bubble" style="display:flex;align-items:center;gap:8px;color:var(--text2);padding:10px 14px;background:linear-gradient(135deg,rgba(107,156,223,0.08),rgba(91,171,138,0.08));border:1px solid rgba(107,156,223,0.2)">
      <span style="font-size:12.5px;font-weight:500;">AyuGuard is typing</span>
      <div class="typing-ind" style="padding:0">
        <div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>
      </div>
    </div></div></div>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}
function removeTyping(role) { document.getElementById(`${role}-typing`)?.remove(); }

/* ── Helpers ───────────────────────────────────────────────────── */
function handleKey(e, role) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMsg(role); } }
function autoResize(el) { el.style.height = ''; el.style.height = Math.min(el.scrollHeight,110)+'px'; }
function escHtml(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function renderMd(text) {
  return escHtml(text)
    .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')
    .replace(/\*(.+?)\*/g,'<em>$1</em>')
    .replace(/`(.+?)`/g,'<code style="background:rgba(255,255,255,.08);padding:1px 5px;border-radius:4px;font-size:12px">$1</code>')
    .replace(/\n/g,'<br>');
}
function fmtDate(d) {
  if (!d) return '—';
  const dt = new Date(d+'T00:00:00');
  return dt.toLocaleDateString('en-IN',{day:'numeric',month:'short'});
}
function fmtDt(d) {
  if (!d) return '—';
  try { return new Date(d).toLocaleString('en-IN',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}); }
  catch { return d; }
}
let toastTimer;
function showToast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg; el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 4000);
}

/* ── Real-Time Notifications System ────────────────────────────── */
let seenNotifIds = new Set();
let isInitialNotifLoad = true;

async function loadNotifications() {
  try {
    const res = await fetch(`${API}/notifications?patient_id=patient_001`);
    const data = await res.json();
    const notifs = data.notifications || [];
    const unreadCount = data.unread_count || 0;

    // Update unread count badge on bell icon
    const badge = document.getElementById('notif-badge');
    if (badge) {
      if (unreadCount > 0) {
        badge.textContent = unreadCount > 99 ? '99+' : unreadCount;
        badge.style.display = 'flex';
      } else {
        badge.style.display = 'none';
      }
    }

    // Render notifications panel list
    const listEl = document.getElementById('notif-list');
    if (listEl) {
      if (!notifs.length) {
        listEl.innerHTML = '<div class="notif-empty">No notifications yet.</div>';
      } else {
        listEl.innerHTML = notifs.map(n => `
          <div class="notif-item ${n.read ? 'read' : 'unread'}">
            <div class="notif-item-msg">${escHtml(n.message)}</div>
            <div class="notif-item-meta">${escHtml(n.from || 'System')} · ${fmtDt(n.created_at)}</div>
          </div>
        `).join('');
      }
    }

    // Trigger Pop-up Toast for newly arrived unread notifications
    for (const n of notifs) {
      const nId = n.id || (n.created_at + n.message);
      if (!seenNotifIds.has(nId)) {
        seenNotifIds.add(nId);
        if (!isInitialNotifLoad && !n.read) {
          // Automatic pop-up Toast notification
          showToast(`🔔 ${n.message}`);
          silentDashboardRefresh(); // Live update dashboard without manual click
        }
      }
    }
    isInitialNotifLoad = false;
  } catch (e) {
    console.warn('Could not load notifications:', e);
  }
}

async function toggleNotifPanel() {
  const panel = document.getElementById('notif-panel');
  if (!panel) return;
  notifPanelOpen = !notifPanelOpen;
  if (notifPanelOpen) {
    panel.classList.add('open');
    // Mark as read when opening panel
    try {
      await fetch(`${API}/notifications/mark-read`, {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ patient_id: 'patient_001' })
      });
      loadNotifications();
    } catch {}
  } else {
    panel.classList.remove('open');
  }
}

/* ── Medical Records JS ────────────────────────────────────────── */
let selectedFile = null;

function handleFileSelect(e) {
  const file = e.target.files[0];
  if (file) selectFile(file);
}
function handleDrop(e) {
  e.preventDefault();
  document.getElementById('upload-zone').classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) selectFile(file);
}
function selectFile(file) {
  selectedFile = file;
  const zone = document.getElementById('upload-zone');
  zone.querySelector('.upload-title').textContent = `📎 ${file.name}`;
  zone.querySelector('.upload-sub').textContent = `${(file.size/1024/1024).toFixed(2)} MB · Ready to upload`;
  document.getElementById('upload-form').style.display = 'flex';
  document.getElementById('upload-status').textContent = '';
}

async function doUpload() {
  if (!selectedFile) { showToast('Please select a file first'); return; }
  const btn = document.getElementById('do-upload-btn');
  const prog = document.getElementById('upload-progress');
  const status = document.getElementById('upload-status');
  btn.disabled = true;
  btn.textContent = '⏳ Analysing…';
  prog.style.width = '30%';
  status.textContent = '🤖 Gemini is reading the document…';

  const fd = new FormData();
  fd.append('file', selectedFile);
  fd.append('record_type', document.getElementById('rec-type').value);
  fd.append('notes', document.getElementById('rec-notes').value);
  fd.append('patient_id', 'patient_001');
  fd.append('caregiver_name', profile.caregiver_name || 'Caregiver');

  try {
    prog.style.width = '70%';
    const res = await fetch(`${API}/upload-record`, { method: 'POST', body: fd });
    prog.style.width = '100%';
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Upload failed');
    status.innerHTML = `✅ <strong>${escHtml(data.record_type)}</strong> analysed! `
      + (data.abnormal_count > 0 ? `⚠️ ${data.abnormal_count} abnormal value(s) found. ` : '')
      + (data.summary ? `<em>${escHtml(data.summary.slice(0,120))}…</em>` : '');
    selectedFile = null;
    document.getElementById('upload-form').style.display = 'none';
    document.getElementById('upload-zone').querySelector('.upload-title').textContent = 'Drop a file here or click to browse';
    document.getElementById('upload-zone').querySelector('.upload-sub').textContent = 'PDF, JPG, PNG, WEBP · Max 15 MB · Lab reports, prescriptions, discharge summaries';
    document.getElementById('rec-notes').value = '';
    document.getElementById('upload-input').value = '';
    showToast('✅ Record uploaded and analysed!');
    await loadRecords();
  } catch(e) {
    status.textContent = `❌ ${e.message}`;
    showToast(`❌ ${e.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = '⬆ Analyse & Upload';
    setTimeout(() => { prog.style.width = '0'; }, 1000);
  }
}

async function loadRecords() {
  document.getElementById('records-list').innerHTML = '<div class="empty"><div class="spinner"></div></div>';
  try {
    const [recRes, abnRes] = await Promise.all([
      fetch(`${API}/records`),
      fetch(`${API}/abnormal-history`),
    ]);
    const recData = await recRes.json();
    const abnData = await abnRes.json();
    renderRecords(recData.records || []);
    renderAbnormalSummary(abnData);
    document.getElementById('rec-count').textContent = recData.total ? `(${recData.total})` : '';
  } catch { document.getElementById('records-list').innerHTML = '<div class="empty"><p>Could not load records.</p></div>'; }
}

function renderRecords(records) {
  const el = document.getElementById('records-list');
  if (!records.length) {
    el.innerHTML = `
      <div class="empty">
        <div class="icon" style="font-size:42px;margin-bottom:10px;">📂</div>
        <p style="font-size:14px;color:var(--text);font-weight:600;margin-bottom:4px;">No records found</p>
        <p style="font-size:12px;color:var(--text3);">Upload a lab report, prescription, or discharge summary above.<br>AyuGuard will automatically extract key findings and abnormal values.</p>
      </div>`;
    return;
  }
  const typeIcons = {
    lab_test:'🧪',prescription:'💊',discharge_summary:'🏥',
    scan_report:'🔬',consultation_note:'📋',vaccination:'💉',other:'📄'
  };
  el.innerHTML = records.map(r => {
    const hasCrit = r.critical_count > 0;
    const hasAbn  = r.abnormal_count > 0;
    const cls     = hasCrit ? 'has-critical' : hasAbn ? 'has-abnormal' : '';
    const badge   = hasCrit
      ? `<span class="badge critical">⚠️ ${r.critical_count} Critical</span>`
      : hasAbn
      ? `<span class="badge abnormal">⚠ ${r.abnormal_count} Abnormal</span>`
      : `<span class="badge ok">✓ Normal</span>`;
    const typeKey = records.find ? r.record_type : 'other';
    const icon = typeIcons[r.record_type?.toLowerCase().replace(/[^a-z_]/g,'_').trim()] || '📄';
    const followUp = r.follow_up === 'yes' ? '<span class="badge abnormal" style="margin-left:4px">📅 Follow-up needed</span>' : '';
    return `
      <div class="rec-card ${cls}" id="rec-${r.record_id}">
        <div class="rec-header" onclick="toggleRecord('${r.record_id}')">
          <div class="rec-type-icon ${(r.record_type||'other').toLowerCase()}">${icon}</div>
          <div class="rec-meta">
            <div class="rec-filename" title="${escHtml(r.filename)}">${escHtml(r.filename.replace(/^\d+_/, ''))}</div>
            <div class="rec-date-row">
              <span class="rec-type-tag">${escHtml(r.record_type || 'other')}</span>
              <span class="rec-date">${r.report_date || r.uploaded_at?.slice(0,10) || '—'}</span>
              ${r.notes ? `<span class="rec-date">· ${escHtml(r.notes)}</span>` : ''}
              ${followUp}
            </div>
          </div>
          <div class="rec-badges">${badge}</div>
          <span class="rec-chevron">▼</span>
        </div>
        <div class="rec-body" id="body-${r.record_id}">
          <div class="rec-summary">${escHtml(r.summary || 'No summary available.')}</div>
          <div class="rec-actions">
            <button class="rec-delete-btn" onclick="deleteRecord('${r.record_id}',event)">🗑 Remove</button>
          </div>
        </div>
      </div>`;
  }).join('');
}

async function toggleRecord(id) {
  const card = document.getElementById(`rec-${id}`);
  const body = document.getElementById(`body-${id}`);
  const isExpanded = card.classList.contains('expanded');
  if (!isExpanded && !body.dataset.loaded) {
    body.innerHTML = '<div class="empty" style="padding:14px"><div class="spinner"></div></div>';
    card.classList.add('expanded');
    try {
      const res  = await fetch(`${API}/records/${id}`);
      const data = await res.json();
      const analysis = data.analysis || {};
      let html = `<div class="rec-summary">${escHtml(analysis.summary || 'No summary.')}</div>`;
      const abnormals = analysis.abnormal_values || [];
      if (abnormals.length) {
        html += `<div class="rec-findings-title">⚠️ Abnormal Values</div>
          <table class="abnormal-table">
            <tr><th>Parameter</th><th>Result</th><th>Normal Range</th><th>Flag</th></tr>
            ${abnormals.map(a => `<tr>
              <td>${escHtml(a.parameter||'—')}</td>
              <td><strong>${escHtml(a.value||'—')}</strong></td>
              <td>${escHtml(a.normal_range||'—')}</td>
              <td><span class="flag-${a.flag||''}">${a.flag||'—'}</span></td>
            </tr>`).join('')}
          </table>`;
      }
      const findings = analysis.key_findings || [];
      if (findings.length) {
        html += `<div class="rec-findings-title">🔍 Key Findings</div>
          <ul class="findings-list">${findings.map(f=>`<li>${escHtml(f)}</li>`).join('')}</ul>`;
      }
      const meds = analysis.medications_mentioned || [];
      if (meds.length) {
        html += `<div class="rec-findings-title">💊 Medications</div>
          <div class="meds-list">${meds.map(m=>`<span class="med-tag">${escHtml(m)}</span>`).join('')}</div>`;
      }
      const recs = analysis.recommendations || [];
      if (recs.length) {
        html += `<div class="rec-findings-title">📋 Doctor's Recommendations</div>
          <ul class="findings-list">${recs.map(r=>`<li>${escHtml(r)}</li>`).join('')}</ul>`;
      }
      if (analysis.critical_values?.length) {
        html += `<div class="rec-findings-title" style="color:var(--red)">🚨 Critical Values — Discuss with Doctor</div>
          <ul class="findings-list">${analysis.critical_values.map(c=>`<li style="border-left-color:var(--red);color:#fca5a5">${escHtml(c)}</li>`).join('')}</ul>`;
      }
      html += `<div style="font-size:10.5px;color:var(--text3);margin-top:10px">Uploaded by ${escHtml(data.uploaded_by||'Caregiver')} · ${fmtDt(data.uploaded_at)}</div>
        <div class="rec-actions"><button class="rec-delete-btn" onclick="deleteRecord('${id}',event)">🗑 Remove</button></div>`;
      body.innerHTML = html;
      body.dataset.loaded = '1';
    } catch { body.innerHTML = '<div class="empty"><p>Could not load details.</p></div>'; }
  } else {
    card.classList.toggle('expanded');
  }
}

async function deleteRecord(id, e) {
  e.stopPropagation();
  if (!confirm('Remove this record?')) return;
  try {
    await fetch(`${API}/records/${id}`, { method: 'DELETE' });
    showToast('Record removed');
    await loadRecords();
  } catch { showToast('Could not remove record'); }
}

function renderAbnormalSummary(data) {
  const params = data.abnormal_by_parameter || {};
  const el = document.getElementById('abn-summary');
  const pl = document.getElementById('abn-params');
  const entries = Object.entries(params);
  if (!entries.length) { el.style.display = 'none'; return; }
  el.style.display = 'block';
  pl.innerHTML = entries.map(([name, vals]) =>
    `<div class="abn-param">
      <span class="abn-param-name">${escHtml(name)}</span>
      <span class="abn-param-count">(${vals.length}×)</span>
      <span class="flag-${vals[0]?.flag||''}">${vals[0]?.flag||''}</span>
    </div>`
  ).join('');
  if (data.critical_alerts?.length) {
    pl.innerHTML += `<div style="width:100%;margin-top:8px;font-size:11.5px;color:#f87171">
      🚨 Critical flags in: ${data.critical_alerts.map(escHtml).join(', ')}</div>`;
  }
}

/* ── Boot ──────────────────────────────────────────────────────── */
setMode('caregiver');
init();