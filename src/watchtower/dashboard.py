from __future__ import annotations


def dashboard_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Watchtower</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #07090d;
      --panel: #10141d;
      --panel-2: #151b26;
      --text: #f4f7fb;
      --muted: #8e9bad;
      --border: #263044;
      --accent: #91e2ff;
      --info: #8ab4ff;
      --warning: #ffc56e;
      --critical: #ff7d91;
      --ok: #7de3b2;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: radial-gradient(circle at 18% 0%, rgba(62, 160, 220, .13), transparent 32rem), var(--bg);
      color: var(--text);
    }
    header {
      max-width: 1180px;
      margin: 0 auto;
      padding: 38px 24px 18px;
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 18px;
    }
    .eyebrow { color: var(--accent); text-transform: uppercase; letter-spacing: .16em; font-size: 12px; font-weight: 700; }
    h1 { font-size: clamp(34px, 5vw, 58px); line-height: .96; margin: 9px 0 12px; letter-spacing: -.05em; }
    .subtitle { margin: 0; color: var(--muted); max-width: 700px; line-height: 1.55; }
    .live { display: flex; align-items: center; gap: 8px; color: var(--ok); font-size: 13px; white-space: nowrap; }
    .dot { width: 9px; height: 9px; background: var(--ok); border-radius: 50%; box-shadow: 0 0 0 5px rgba(125, 227, 178, .11); }
    main { max-width: 1180px; margin: 0 auto; padding: 14px 24px 60px; }
    .stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 18px; }
    .stat, .panel { border: 1px solid var(--border); background: rgba(16, 20, 29, .9); border-radius: 16px; }
    .stat { padding: 18px; }
    .stat-label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }
    .stat-value { margin-top: 8px; font-size: 30px; font-weight: 750; letter-spacing: -.04em; }
    .grid { display: grid; grid-template-columns: minmax(0, 1.45fr) minmax(300px, .75fr); gap: 18px; align-items: start; }
    .panel { overflow: hidden; }
    .panel-head { padding: 17px 18px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    .panel-head h2 { margin: 0; font-size: 15px; letter-spacing: -.01em; }
    .panel-head span { color: var(--muted); font-size: 12px; }
    .items { padding: 8px; }
    .empty { color: var(--muted); padding: 36px 20px; text-align: center; line-height: 1.55; }
    .card { background: var(--panel-2); border: 1px solid transparent; border-radius: 12px; padding: 15px; margin: 8px 0; }
    .card:hover { border-color: var(--border); }
    .topline { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 8px; }
    .badge { border-radius: 999px; padding: 4px 8px; text-transform: uppercase; letter-spacing: .07em; font-size: 10px; font-weight: 800; }
    .badge.info { color: var(--info); background: rgba(138, 180, 255, .11); }
    .badge.warning { color: var(--warning); background: rgba(255, 197, 110, .11); }
    .badge.critical { color: var(--critical); background: rgba(255, 125, 145, .11); }
    .time { color: var(--muted); font-size: 11px; }
    .title { font-size: 15px; font-weight: 720; line-height: 1.35; }
    .message { color: #c0c8d5; font-size: 13px; line-height: 1.55; margin-top: 7px; }
    .meta { color: var(--muted); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11px; margin-top: 10px; overflow-wrap: anywhere; }
    .actions { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 12px; }
    button, select { color: var(--text); background: #20293a; border: 1px solid #33405a; border-radius: 8px; padding: 7px 10px; cursor: pointer; font: inherit; font-size: 11px; }
    button:hover, select:hover { border-color: var(--accent); }
    button.selected { border-color: var(--ok); color: var(--ok); }
    button.danger.selected { border-color: var(--critical); color: var(--critical); }
    details { margin-top: 11px; color: var(--muted); font-size: 11px; }
    details summary { cursor: pointer; }
    .event { padding: 12px 10px; border-bottom: 1px solid rgba(38, 48, 68, .65); }
    .event:last-child { border-bottom: 0; }
    .event-kind { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11px; color: var(--accent); overflow-wrap: anywhere; }
    .event-source { color: var(--muted); font-size: 11px; margin-top: 5px; }
    footer { max-width: 1180px; margin: 0 auto; padding: 0 24px 28px; color: var(--muted); font-size: 12px; }
    @media (max-width: 900px) { .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
    @media (max-width: 820px) {
      header { align-items: flex-start; flex-direction: column; }
      .grid { grid-template-columns: 1fr; }
    }
    @media (max-width: 520px) { .stats { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <header>
    <div>
      <div class="eyebrow">Local proactivity control plane</div>
      <h1>Watchtower</h1>
      <p class="subtitle">Observes agent events, detects moments worth interrupting, and leaves execution under human control.</p>
    </div>
    <div class="live"><span class="dot"></span><span id="health">Checking daemon</span></div>
  </header>
  <main>
    <section class="stats">
      <div class="stat"><div class="stat-label">Events observed</div><div class="stat-value" id="event-count">0</div></div>
      <div class="stat"><div class="stat-label">Open interventions</div><div class="stat-value" id="open-count">0</div></div>
      <div class="stat"><div class="stat-label">Useful feedback</div><div class="stat-value" id="useful-rate">—</div></div>
      <div class="stat"><div class="stat-label">Checkpoints</div><div class="stat-value" id="checkpoint-count">0</div></div>
    </section>
    <section class="grid">
      <div class="panel">
        <div class="panel-head"><h2>Interventions</h2><span>Evidence, feedback and confirmed actions</span></div>
        <div class="items" id="interventions"><div class="empty">No interventions yet. Run <code>watchtower demo</code> to exercise the pipeline.</div></div>
      </div>
      <div class="panel">
        <div class="panel-head"><h2>Recent event stream</h2><span>Local SQLite</span></div>
        <div class="items" id="events"><div class="empty">Waiting for agent hooks.</div></div>
      </div>
    </section>
  </main>
  <footer>Feedback and checkpoints stay local. Commands are not stored unless command capture is explicitly enabled.</footer>
  <script>
    const esc = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
    const ago = value => {
      const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
      if (seconds < 60) return `${seconds}s ago`;
      if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
      return `${Math.floor(seconds / 3600)}h ago`;
    };
    let interventionById = {};
    let feedbackByIntervention = {};

    async function setStatus(id, status) {
      await fetch(`/v1/interventions/${encodeURIComponent(id)}/status`, {
        method: 'PATCH', headers: {'content-type':'application/json'}, body: JSON.stringify({status})
      });
      await refresh();
    }
    async function setFeedback(id, rating) {
      if (!rating) return;
      await fetch(`/v1/interventions/${encodeURIComponent(id)}/feedback`, {
        method: 'PUT', headers: {'content-type':'application/json'},
        body: JSON.stringify({rating, channel: 'dashboard'})
      });
      await refresh();
    }
    async function createCheckpoint(id) {
      const item = interventionById[id];
      if (!item) return;
      if (!window.confirm('Create a local Markdown checkpoint from retained Watchtower events?')) return;
      const response = await fetch('/v1/checkpoints', {
        method: 'POST', headers: {'content-type':'application/json'},
        body: JSON.stringify({
          session_id: item.session_id,
          project_path: item.project_path,
          intervention_id: item.id,
          confirmed: true
        })
      });
      const body = await response.json();
      if (!response.ok) {
        window.alert(body.detail || 'Checkpoint creation failed');
        return;
      }
      window.alert(`Checkpoint created locally:\n${body.path}`);
      await refresh();
    }
    function renderInterventions(items) {
      const root = document.getElementById('interventions');
      const open = items.filter(item => item.status === 'new');
      interventionById = Object.fromEntries(items.map(item => [item.id, item]));
      if (!items.length) {
        root.innerHTML = '<div class="empty">No interventions yet. Run <code>watchtower demo</code> to exercise the pipeline.</div>';
        return;
      }
      root.innerHTML = items.map(item => {
        const feedback = feedbackByIntervention[item.id];
        const useful = feedback?.rating === 'useful' ? 'selected' : '';
        const notUseful = feedback?.rating === 'not_useful' ? 'selected' : '';
        const evidence = (item.evidence_event_ids || []).map(id => `<code>${esc(id)}</code>`).join(', ');
        const checkpoint = item.suggested_action === 'create_context_checkpoint'
          ? `<button onclick="createCheckpoint('${esc(item.id)}')">Create checkpoint</button>` : '';
        return `
          <article class="card">
            <div class="topline"><span class="badge ${esc(item.severity)}">${esc(item.severity)}</span><span class="time">${ago(item.created_at)}</span></div>
            <div class="title">${esc(item.title)}</div>
            <div class="message">${esc(item.message)}</div>
            <div class="meta">${esc(item.detector)} · ${esc(item.session_id)}${item.suggested_action ? ` · ${esc(item.suggested_action)}` : ''}</div>
            <details><summary>Evidence (${(item.evidence_event_ids || []).length})</summary><div class="meta">${evidence || 'No evidence IDs retained'}</div></details>
            <div class="actions">
              <button class="${useful}" onclick="setFeedback('${esc(item.id)}','useful')">Useful</button>
              <button class="danger ${notUseful}" onclick="setFeedback('${esc(item.id)}','not_useful')">Not useful</button>
              <select aria-label="Detailed feedback" onchange="setFeedback('${esc(item.id)}', this.value); this.selectedIndex=0">
                <option value="">More feedback…</option>
                <option value="incorrect">Incorrect</option>
                <option value="too_early">Too early</option>
                <option value="too_late">Too late</option>
                <option value="already_known">Already known</option>
                <option value="too_disruptive">Too disruptive</option>
              </select>
              ${checkpoint}
              ${item.status === 'new' ? `<button onclick="setStatus('${esc(item.id)}','acknowledged')">Acknowledge</button><button onclick="setStatus('${esc(item.id)}','dismissed')">Dismiss</button>` : `<button disabled>${esc(item.status)}</button>`}
            </div>
          </article>`;
      }).join('');
    }
    function renderEvents(items) {
      const root = document.getElementById('events');
      if (!items.length) { root.innerHTML = '<div class="empty">Waiting for agent hooks.</div>'; return; }
      root.innerHTML = items.slice(0, 24).map(item => `
        <div class="event"><div class="event-kind">${esc(item.kind)}</div><div class="event-source">${esc(item.source)} · ${esc(item.session_id)} · ${ago(item.occurred_at)}</div></div>`).join('');
    }
    async function refresh() {
      try {
        const [health, interventions, events, feedback, metrics, summary] = await Promise.all([
          fetch('/health').then(r => r.json()),
          fetch('/v1/interventions?limit=50').then(r => r.json()),
          fetch('/v1/events?limit=200').then(r => r.json()),
          fetch('/v1/feedback?limit=1000').then(r => r.json()),
          fetch('/v1/metrics/quality').then(r => r.json()),
          fetch('/v1/metrics/summary').then(r => r.json())
        ]);
        document.getElementById('health').textContent = `Daemon ${health.version} · schema ${health.schema_version}`;
        feedbackByIntervention = Object.fromEntries(feedback.map(item => [item.intervention_id, item]));
        const rate = metrics.overall?.positive_rate;
        document.getElementById('useful-rate').textContent = rate == null ? '—' : `${Math.round(rate * 100)}%`;
        document.getElementById('event-count').textContent = summary.events;
        document.getElementById('open-count').textContent = summary.open_interventions;
        document.getElementById('checkpoint-count').textContent = summary.checkpoints;
        renderInterventions(interventions);
        renderEvents(events);
      } catch (error) {
        document.getElementById('health').textContent = 'Daemon unavailable';
      }
    }
    refresh();
    setInterval(refresh, 4000);
  </script>
</body>
</html>"""
