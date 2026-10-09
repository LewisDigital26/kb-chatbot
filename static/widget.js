/*
 * widget.js - the chat widget. Add it to any website with one line:
 *   <script src="https://your-server/widget.js" data-name="Bloom & Blade"></script>
 * Everything (styles included) lives in this file.
 */
(function () {
  const script = document.currentScript;
  const API = new URL("/api/chat", script.src).href;
  const NAME = script.dataset.name || "us";
  const SUGGESTIONS = ["What are your opening hours?", "How much is balayage?", "Do I need a patch test?"];

  const css = `
  .bb-chat, .bb-chat * { box-sizing: border-box; font-family: "Inter", system-ui, sans-serif; }
  .bb-launch { position: fixed; right: 20px; bottom: 20px; z-index: 9999; height: 56px; padding: 0 22px;
    border: 0; border-radius: 28px; background: #3b1f3a; color: #fff; font-size: 15px; font-weight: 600;
    box-shadow: 0 8px 24px rgba(59,31,58,.35); cursor: pointer; display: flex; align-items: center; gap: 10px; }
  .bb-launch:hover { background: #52294f; }
  .bb-panel { position: fixed; right: 20px; bottom: 88px; z-index: 9999; width: 370px; max-width: calc(100vw - 32px);
    height: 540px; max-height: calc(100vh - 120px); background: #fffaf7; border-radius: 18px;
    box-shadow: 0 18px 50px rgba(30,15,30,.28); display: none; flex-direction: column; overflow: hidden; }
  .bb-panel.open { display: flex; }
  .bb-head { background: #3b1f3a; color: #fff; padding: 16px 18px; }
  .bb-head b { display: block; font-size: 16px; }
  .bb-head span { font-size: 12.5px; opacity: .8; }
  .bb-log { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 10px; }
  .bb-msg { max-width: 85%; padding: 10px 13px; border-radius: 14px; font-size: 14px; line-height: 1.45; white-space: pre-wrap; }
  .bb-bot { align-self: flex-start; background: #fff; border: 1px solid #f0dfe4; color: #2a1a29; border-bottom-left-radius: 4px; }
  .bb-user { align-self: flex-end; background: #c75b7a; color: #fff; border-bottom-right-radius: 4px; }
  .bb-handoff { background: #fff4e5; border-color: #f3d3a5; }
  .bb-src { margin-top: 7px; font-size: 11.5px; color: #8a6b80; }
  .bb-typing { align-self: flex-start; color: #8a6b80; font-size: 13px; font-style: italic; }
  .bb-chips { display: flex; flex-wrap: wrap; gap: 6px; padding: 0 16px 10px; }
  .bb-chip { border: 1px solid #e3c4cf; background: #fff; color: #3b1f3a; border-radius: 16px; padding: 6px 11px;
    font-size: 12.5px; cursor: pointer; }
  .bb-chip:hover { background: #fbeef2; }
  .bb-form { display: flex; gap: 8px; padding: 12px; border-top: 1px solid #f0dfe4; background: #fff; }
  .bb-form input { flex: 1; border: 1px solid #e3c4cf; border-radius: 22px; padding: 10px 14px; font-size: 14px; outline: none; }
  .bb-form input:focus { border-color: #c75b7a; }
  .bb-form button { border: 0; border-radius: 22px; background: #c75b7a; color: #fff; padding: 0 16px; font-weight: 600; cursor: pointer; }
  .bb-form button:disabled { opacity: .5; cursor: default; }
  .bb-note { text-align: center; font-size: 11px; color: #a08a99; padding: 0 0 8px; background: #fff; }`;

  const style = document.createElement("style");
  style.textContent = css;
  document.head.appendChild(style);

  const root = document.createElement("div");
  root.className = "bb-chat";
  root.innerHTML = `
    <button class="bb-launch" aria-label="Open chat">💬 Ask us a question</button>
    <div class="bb-panel" role="dialog" aria-label="Chat">
      <div class="bb-head"><b></b><span>Answers come from our salon info. Usually instant.</span></div>
      <div class="bb-log" aria-live="polite"></div>
      <div class="bb-chips"></div>
      <form class="bb-form"><input maxlength="500" placeholder="Type your question…" aria-label="Your question">
        <button type="submit">Send</button></form>
      <div class="bb-note">AI assistant · for anything else, our team is happy to help</div>
    </div>`;
  document.body.appendChild(root);

  const $ = (sel) => root.querySelector(sel);
  const panel = $(".bb-panel"), log = $(".bb-log"), form = $(".bb-form");
  const input = $("input"), send = $(".bb-form button"), chips = $(".bb-chips");
  $(".bb-head b").textContent = `Chat with ${NAME}`;

  function add(text, who, extra) {
    const div = document.createElement("div");
    div.className = `bb-msg bb-${who}` + (extra ? ` ${extra}` : "");
    div.textContent = text; // textContent, never innerHTML, so replies can't inject code
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
    return div;
  }

  function addSources(div, sources) {
    if (!sources || !sources.length) return;
    const names = [...new Set(sources.map((s) => s.split(" > ").pop()))];
    const src = document.createElement("div");
    src.className = "bb-src";
    src.textContent = "Source: " + names.join(" · ");
    div.appendChild(src);
  }

  async function ask(question) {
    chips.style.display = "none";
    add(question, "user");
    input.value = "";
    send.disabled = input.disabled = true;
    const typing = document.createElement("div");
    typing.className = "bb-typing";
    typing.textContent = "Checking our salon info…";
    log.appendChild(typing);
    log.scrollTop = log.scrollHeight;
    try {
      const res = await fetch(API, { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }) });
      const data = await res.json();
      typing.remove();
      if (!res.ok) { add(data.error || "Sorry, something went wrong.", "bot", "bb-handoff"); return; }
      const div = add(data.answer, "bot", data.answered ? "" : "bb-handoff");
      addSources(div, data.sources);
    } catch (e) {
      typing.remove();
      add("Sorry, I can't connect right now. Please try again shortly.", "bot", "bb-handoff");
    } finally {
      send.disabled = input.disabled = false;
      input.focus();
    }
  }

  SUGGESTIONS.forEach((q) => {
    const b = document.createElement("button");
    b.type = "button"; b.className = "bb-chip"; b.textContent = q;
    b.onclick = () => ask(q);
    chips.appendChild(b);
  });

  $(".bb-launch").onclick = () => {
    panel.classList.toggle("open");
    if (panel.classList.contains("open")) input.focus();
  };
  form.onsubmit = (e) => { e.preventDefault(); const q = input.value.trim(); if (q) ask(q); };
  add(`Hi! I can answer questions about prices, opening hours, bookings and more at ${NAME}. What would you like to know?`, "bot");
})();
