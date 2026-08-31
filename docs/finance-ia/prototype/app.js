const roles = {
  requesting: {
    office: "General Services Office",
    eyebrow: "Requesting-office workspace",
    title: "Good morning, requesting-office maker",
    intro: "Prepare funded requests, respond to returns, and follow the same case after Finance takes responsibility.",
    primary: "Open My Work",
    metrics: [["Ready for me", "2", "1 returned request"], ["My open cases", "7", "Across authorized phases"], ["Waiting on Finance", "4", "No action required"], ["Due this week", "1", "Local target"]]
  },
  budget_maker: {
    office: "Budget Office",
    eyebrow: "Budget preparation workspace",
    title: "Good morning, Budget maker",
    intro: "Prepare authority movements, classify obligations, and send versioned work for independent approval.",
    primary: "Open Budget queue",
    metrics: [["Ready for me", "4", "2 due today"], ["Returned", "2", "Classification work"], ["Waiting approval", "6", "Prepared by Budget"], ["Blocking decisions", "2", "Affected scope stopped"]]
  },
  budget_approver: {
    office: "Budget Office",
    eyebrow: "Budget authority workspace",
    title: "Good morning, Budget approver",
    intro: "Review authority movements and certify obligations without losing the complete case history.",
    primary: "Review ready work",
    metrics: [["Ready to review", "3", "1 due today"], ["Returned to makers", "2", "Reasons recorded"], ["Waiting evidence", "4", "No approval available"], ["Blocking decisions", "2", "Affected scope stopped"]]
  },
  accounting_maker: {
    office: "Accounting Office",
    eyebrow: "Accounting preparation workspace",
    title: "Good morning, Accounting maker",
    intro: "Validate claims, prepare controlled vouchers and JEVs, and preserve every print and correction version.",
    primary: "Open Accounting queue",
    metrics: [["Ready for me", "5", "2 claim reviews"], ["Signed packets back", "2", "Validation ready"], ["JEVs for review", "3", "Prepared independently"], ["Returned", "1", "Evidence incomplete"]]
  },
  accounting_reviewer: {
    office: "Accounting Office",
    eyebrow: "Accounting review and posting",
    title: "Good morning, Accounting reviewer",
    intro: "Independently review, post, reconcile, and correct through reversal—not silent rewriting.",
    primary: "Review posting work",
    metrics: [["For posting", "3", "Balanced drafts"], ["Voucher reviews", "4", "Current period"], ["Differences", "1", "Unresolved schedule"], ["Period close", "6/9", "Checklist complete"]]
  },
  treasury_maker: {
    office: "Treasury Office",
    eyebrow: "Treasury preparation workspace",
    title: "Good morning, Treasury maker",
    intro: "Check cash authority, prepare instruments and advice, and retain cancellation and replacement lineage.",
    primary: "Open Treasury queue",
    metrics: [["Ready for preparation", "4", "Cash check passed"], ["For advice", "3", "Prepared instruments"], ["Exceptions", "2", "Human review"], ["Unreconciled", "5", "August statement"]]
  },
  treasury_releaser: {
    office: "Treasury Office",
    eyebrow: "Treasury release workspace",
    title: "Good morning, Treasury releaser",
    intro: "Release only eligible, advised instruments to authorized claimants and retain acknowledgement evidence.",
    primary: "Review release queue",
    metrics: [["Ready for release", "3", "Advice finalized"], ["Awaiting claimant", "4", "No action available"], ["Stale/unclaimed", "1", "Decision required"], ["Released today", "6", "Acknowledged"]]
  },
  setup_approver: {
    office: "Finance Administration",
    eyebrow: "Setup and control workspace",
    title: "Good morning, setup approver",
    intro: "Independently approve effective-dated rules, templates, numbering, periods, and readiness evidence.",
    primary: "Review setup changes",
    metrics: [["Ready to review", "2", "Prepared by managers"], ["Readiness blockers", "3", "FY 2027 draft"], ["Active releases", "1", "FY 2026"], ["Recovery checks", "All pass", "28 Aug · 09:00"]]
  },
  auditor: {
    office: "Finance oversight",
    eyebrow: "Read-only audit and UAT view",
    title: "Finance oversight",
    intro: "Inspect authorized case lineage, control evidence, and gaps without receiving transaction authority.",
    primary: "Browse authorized cases",
    metrics: [["Open cases", "21", "Authorized scope"], ["Blocking exceptions", "2", "Decision owners named"], ["Reconciled", "18", "Current pilot set"], ["UAT coverage", "7/10", "Synthetic scenarios"]]
  }
};

const tasks = [
  { id: "TASK-0418", caseId: "GF-2026-00418", title: "Correct obligation classification", state: "returned", roles: ["requesting", "budget_maker"], office: "Budget Office", gate: "Returned with reason · no balance reserved", due: "Today · 16:00" },
  { id: "TASK-0421", caseId: "GF-2026-00421", title: "Review obligation certification", state: "ready", roles: ["budget_approver"], office: "Budget Office", gate: "Maker submitted · balance check current", due: "Today · 15:30" },
  { id: "TASK-0412", caseId: "GF-2026-00412", title: "Classify obligation request", state: "ready", roles: ["budget_maker"], office: "Budget Office", gate: "Request endorsed · documents present", due: "Tomorrow" },
  { id: "TASK-0397", caseId: "GF-2026-00397", title: "Validate signed voucher packet", state: "ready", roles: ["accounting_maker"], office: "Accounting Office", gate: "Signed packet returned · custody verified", due: "Today · 14:00" },
  { id: "TASK-0402", caseId: "GF-2026-00402", title: "Prepare recognition JEV", state: "ready", roles: ["accounting_maker"], office: "Accounting Office", gate: "Payable recognized · period open", due: "Tomorrow" },
  { id: "TASK-0389", caseId: "GF-2026-00389", title: "Post balanced recognition JEV", state: "ready", roles: ["accounting_reviewer"], office: "Accounting Office", gate: "Independent draft · balanced lines", due: "Today · 13:00" },
  { id: "TASK-0384", caseId: "GF-2026-00384", title: "Resolve subsidiary schedule difference", state: "returned", roles: ["accounting_maker", "accounting_reviewer"], office: "Accounting Office", gate: "₱500.00 unexplained difference", due: "Blocking close" },
  { id: "TASK-0378", caseId: "GF-2026-00378", title: "Prepare payment instrument", state: "ready", roles: ["treasury_maker"], office: "Treasury Office", gate: "Posted payment JEV · cash check passed", due: "Today · 15:00" },
  { id: "TASK-0351", caseId: "GF-2026-00351", title: "Release advised instrument", state: "ready", roles: ["treasury_releaser"], office: "Treasury Office", gate: "Advice finalized · claimant authority verified", due: "Today · 16:30" },
  { id: "TASK-0354", caseId: "GF-2026-00354", title: "Await bank acknowledgement", state: "waiting", roles: ["treasury_maker", "treasury_releaser"], office: "Treasury Office", gate: "External acknowledgement pending", due: "No local action" },
  { id: "TASK-SETUP-17", caseId: "SETUP-FY2027-04", title: "Review FY 2027 numbering policy", state: "ready", roles: ["setup_approver"], office: "Finance Administration", gate: "Prepared by setup manager · synthetic preview passed", due: "30 Aug" },
  { id: "TASK-REQ-22", caseId: "GF-2026-00422", title: "Submit supporting references", state: "ready", roles: ["requesting"], office: "General Services Office", gate: "Own-office draft · required references missing", due: "Tomorrow" },
  { id: "TASK-AUDIT-01", caseId: "REPLAY-007", title: "Review synthetic complete-cycle replay", state: "ready", roles: ["auditor"], office: "Finance oversight", gate: "Read-only UAT scope", due: "Review target · 31 Aug" }
];

const events = [
  { type: "authority", time: "Today · 10:24", title: "Obligation proposal returned", copy: "Budget approver returned expense object 50203010 for correction. No allotment was consumed.", meta: "Event v1 · state 11 → 12 · DEC-004" },
  { type: "technical", time: "Today · 10:24", title: "Task reassigned to Budget maker", copy: "The original approval task was completed as returned; a new correction task was created.", meta: "Idempotency receipt · synthetic" },
  { type: "authority", time: "Today · 09:48", title: "Obligation submitted for certification", copy: "Budget maker submitted ₱48,750.00 against ARO-2026-0082 using configuration release v4.", meta: "State 10 → 11 · EV-UAT-014" },
  { type: "authority", time: "Yesterday · 15:12", title: "Request endorsed by requesting office", copy: "General Services Office endorsed the synthetic office-supplies request and its safe document references.", meta: "State 7 → 8 · TASK-REQ-18" },
  { type: "custody", time: "Yesterday · 14:50", title: "Document references verified", copy: "Three Records references were checked. No physical Finance packet exists at this phase.", meta: "Records links · no approval implied" },
  { type: "technical", time: "26 Aug · 11:03", title: "Case opened", copy: "Stable case GF-2026-00418 created in shadow mode with synthetic identifiers.", meta: "Case UUID retained · source GRAND" }
];

const caseResults = [
  { id: "GF-2026-00418", type: "Ordinary supplier", summary: "Office supplies · General Services Office", phase: "Obligation control", office: "Budget Office", fund: "General Fund", fy: "2026", roles: Object.keys(roles) },
  { id: "GF-2026-00397", type: "Utility bill", summary: "Electric service · Municipal Hall", phase: "Voucher and signatures", office: "Accounting Office", fund: "General Fund", fy: "2026", roles: ["accounting_maker", "accounting_reviewer", "budget_approver", "auditor"] },
  { id: "GF-2026-00351", type: "Ordinary supplier", summary: "Network equipment · synthetic pilot", phase: "Payment", office: "Treasury Office", fund: "Trust Fund", fy: "2026", roles: ["treasury_maker", "treasury_releaser", "accounting_reviewer", "auditor"] },
  { id: "GF-2026-00422", type: "Request draft", summary: "Repair materials · General Services Office", phase: "Request preparation", office: "General Services Office", fund: "General Fund", fy: "2026", roles: ["requesting", "budget_maker", "auditor"] }
];

let currentRole = "budget_approver";
let currentTaskFilter = "ready";
let toastTimer;
const mobileNavigation = window.matchMedia("(max-width: 820px)");

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.hidden = true; }, 4200);
}

function setView(view, updateHash = true) {
  $$("[data-view-panel]").forEach(panel => {
    const active = panel.dataset.viewPanel === view;
    panel.hidden = !active;
    panel.classList.toggle("is-active", active);
  });
  $$(".primary-nav [data-view]").forEach(button => {
    const active = button.dataset.view === view;
    button.classList.toggle("is-active", active);
    if (active) button.setAttribute("aria-current", "page"); else button.removeAttribute("aria-current");
  });
  if (updateHash) history.replaceState(null, "", `#${view}`);
  $("#main-content").focus({ preventScroll: true });
  window.scrollTo({ top: 0, behavior: "smooth" });
  closeMenu();
}

function roleTasks(role = currentRole) {
  return tasks.filter(task => task.roles.includes(role));
}

function renderRole() {
  const role = roles[currentRole];
  $("#office-context").textContent = role.office;
  $("#overview-eyebrow").textContent = role.eyebrow;
  $("#overview-title").textContent = role.title;
  $("#overview-intro").textContent = role.intro;
  $("#overview-primary-action").textContent = role.primary;
  $("#metrics").innerHTML = role.metrics.map(([label, value, note]) => `<article class="metric"><span>${label}</span><strong>${value}</strong><small>${note}</small></article>`).join("");

  const visible = roleTasks();
  const ready = visible.filter(task => task.state === "ready");
  $("#nav-work-count").textContent = ready.length;
  $("#priority-list").innerHTML = (visible.slice(0, 3).map(task => priorityMarkup(task)).join("") || `<div class="empty-state">No synthetic priority work for this role.</div>`);
  $("#queue-reason").textContent = currentRole === "auditor"
    ? "This preview role receives read-only review tasks. It cannot perform a consequential Finance action."
    : "Your role, department scope, enabled fund/year, case state, and explicit permission all match.";
  $("#task-state-note").textContent = currentRole === "auditor"
    ? "Inspection does not move the case or complete an operational task. Acceptance is captured separately as evidence."
    : "Completing one task moves the shared case only through an authorized, version-checked service action.";
  $("#work-intro").textContent = currentRole === "auditor"
    ? "Read-only review items appear here without mutation controls."
    : "Tasks are shown because this preview role can act or is accountable for the next gate.";

  renderTasks();
  renderCaseAction();
  renderSearch();
}

function priorityMarkup(task) {
  return `<article class="priority-item ${task.state}"><span class="priority-bar" aria-hidden="true"></span><div><strong>${task.title}</strong><p>${task.caseId} · ${task.gate}</p></div><button type="button" data-open-case="${task.caseId}">${task.state === "waiting" ? "Inspect" : "Open"} <span aria-hidden="true">→</span></button></article>`;
}

function renderTasks() {
  const visible = roleTasks();
  const counts = state => visible.filter(task => task.state === state).length;
  $("#ready-count").textContent = counts("ready");
  $("#waiting-count").textContent = counts("waiting");
  $("#returned-count").textContent = counts("returned");
  const filtered = currentTaskFilter === "all" ? visible : visible.filter(task => task.state === currentTaskFilter);
  $("#task-result-count").textContent = `${filtered.length} ${filtered.length === 1 ? "task" : "tasks"}`;
  $("#task-list").innerHTML = filtered.length ? filtered.map(task => `
    <article class="task-item">
      <div><span class="eyebrow">${task.id} · ${task.caseId}</span><h3>${task.title}</h3><p>${task.gate}</p></div>
      <div class="task-meta"><span class="task-state ${task.state}">Task · ${task.state[0].toUpperCase() + task.state.slice(1)}</span><span><strong>${task.office}</strong></span><span>${task.due}</span></div>
      <button class="button button-secondary" type="button" data-open-case="${task.caseId}">${currentRole === "auditor" || task.state === "waiting" ? "Inspect" : "Open task"}</button>
    </article>`).join("") : `<div class="empty-state"><strong>No ${currentTaskFilter} tasks</strong><p>Try another task state. Hidden or unauthorized tasks do not affect this count.</p></div>`;
}

function renderCaseAction() {
  const actions = {
    requesting: ["Follow case", "The case is currently owned by Budget."],
    budget_maker: ["Correct classification", "Prototype · no balance movement"],
    budget_approver: ["Waiting for resubmission", "No approval action is currently available"],
    accounting_maker: ["Follow case", "Accounting has no task at this phase"],
    accounting_reviewer: ["Follow case", "Accounting has no task at this phase"],
    treasury_maker: ["Follow case", "Treasury has no task at this phase"],
    treasury_releaser: ["Follow case", "Treasury has no task at this phase"],
    setup_approver: ["View pinned setup", "Read-only case context"],
    auditor: null
  };
  const target = $("#case-action");
  const action = actions[currentRole];
  if (!action) {
    target.innerHTML = `<div class="read-only-note"><strong>Read-only Finance UAT viewer</strong><br>No submit, approve, post, issue, advise, release, or setup action is available.</div>`;
    return;
  }
  const disabled = action[0].startsWith("Waiting");
  target.innerHTML = `<button class="button ${disabled ? "button-secondary" : "button-primary"}" type="button" ${disabled ? "disabled" : "data-demo-message=\"This is a synthetic prototype action; no record or authority changes.\""}>${action[0]}</button><small>${action[1]}</small>`;
}

function renderTimeline(filter = "all") {
  const filtered = filter === "all" ? events : events.filter(event => event.type === filter);
  $("#timeline").innerHTML = filtered.length ? filtered.map(event => `<article class="timeline-event ${event.type}"><time class="event-time">${event.time}</time><span class="event-dot" aria-hidden="true"></span><div class="event-copy"><strong>${event.title}</strong><p>${event.copy}</p><small>${event.meta}</small></div></article>`).join("") : `<div class="empty-state">No ${filter} events in this synthetic case.</div>`;
}

function renderSearch() {
  const query = $("#case-search").value.trim().toLowerCase();
  const phase = $("#phase-filter").value;
  const fund = $("#fund-filter").value;
  const results = caseResults.filter(item => item.roles.includes(currentRole))
    .filter(item => !query || `${item.id} ${item.type} ${item.summary}`.toLowerCase().includes(query))
    .filter(item => phase === "all" || item.phase === phase)
    .filter(item => fund === "all" || item.fund === fund);
  $("#search-count").textContent = results.length;
  $("#search-results").innerHTML = results.length ? results.map(item => `
    <button class="search-result" type="button" data-open-case="${item.id}">
      <div><span class="eyebrow">Finance case · ${item.type}</span><h3>${item.id}</h3><p>${item.summary}</p></div>
      <div><span>Case phase</span><strong>${item.phase}</strong></div>
      <div><span>Responsible / scope</span><strong>${item.office}</strong><p>${item.fund} · FY ${item.fy}</p></div>
      <span class="result-arrow" aria-hidden="true">→</span>
    </button>`).join("") : `<div class="empty-state"><strong>No authorized results</strong><p>Reset safe filters or check the reference. Hidden cases do not affect suggestions or counts.</p></div>`;
}

function openMenu() {
  $("#sidebar").hidden = false;
  $("#sidebar").classList.add("is-open");
  $("#menu-button").setAttribute("aria-expanded", "true");
  syncMenuAccessibility();
  $("#sidebar-close").focus();
}

function closeMenu(returnFocus = false) {
  $("#sidebar").classList.remove("is-open");
  $("#menu-button").setAttribute("aria-expanded", "false");
  syncMenuAccessibility();
  if (returnFocus) $("#menu-button").focus();
}

function syncMenuAccessibility() {
  const sidebar = $("#sidebar");
  const visuallyClosed = mobileNavigation.matches && !sidebar.classList.contains("is-open");
  sidebar.hidden = visuallyClosed;
  if (visuallyClosed) {
    sidebar.setAttribute("inert", "");
    sidebar.setAttribute("aria-hidden", "true");
  } else {
    sidebar.removeAttribute("inert");
    sidebar.removeAttribute("aria-hidden");
  }
}

document.addEventListener("click", event => {
  const viewButton = event.target.closest("[data-view]");
  if (viewButton) setView(viewButton.dataset.view);
  const caseButton = event.target.closest("[data-open-case]");
  if (caseButton) {
    if (caseButton.dataset.openCase !== "GF-2026-00418") showToast(`Opening ${caseButton.dataset.openCase} is represented by the shared synthetic case layout.`);
    setView("case");
  }
  const messageButton = event.target.closest("[data-demo-message]");
  if (messageButton) showToast(messageButton.dataset.demoMessage);
});

$("#role-select").addEventListener("change", event => {
  currentRole = event.target.value;
  currentTaskFilter = "ready";
  $$("[data-task-filter]").forEach(button => {
    const active = button.dataset.taskFilter === "ready";
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  renderRole();
  showToast(`Preview changed to ${event.target.selectedOptions[0].text}. Data security is not simulated by this static artifact.`);
});

$("#overview-primary-action").addEventListener("click", () => currentRole === "auditor" ? setView("search") : setView("work"));
$$('[data-task-filter]').forEach(button => button.addEventListener("click", () => {
  currentTaskFilter = button.dataset.taskFilter;
  $$('[data-task-filter]').forEach(item => {
    const active = item === button;
    item.classList.toggle("is-active", active);
    item.setAttribute("aria-pressed", String(active));
  });
  renderTasks();
}));
$$('[data-event-filter]').forEach(button => button.addEventListener("click", () => {
  $$('[data-event-filter]').forEach(item => {
    const active = item === button;
    item.classList.toggle("is-active", active);
    item.setAttribute("aria-pressed", String(active));
  });
  renderTimeline(button.dataset.eventFilter);
}));
$("#search-form").addEventListener("submit", event => { event.preventDefault(); renderSearch(); });
$("#phase-filter").addEventListener("change", renderSearch);
$("#fund-filter").addEventListener("change", renderSearch);
$("#reset-search").addEventListener("click", () => {
  $("#case-search").value = "";
  $("#phase-filter").value = "all";
  $("#fund-filter").value = "all";
  renderSearch();
});
$("#menu-button").addEventListener("click", () => $("#sidebar").classList.contains("is-open") ? closeMenu(true) : openMenu());
$("#sidebar-close").addEventListener("click", () => closeMenu(true));
document.addEventListener("keydown", event => { if (event.key === "Escape" && $("#sidebar").classList.contains("is-open")) closeMenu(true); });
mobileNavigation.addEventListener("change", syncMenuAccessibility);

const initialView = location.hash.replace("#", "");
if (["overview", "work", "case", "search"].includes(initialView)) setView(initialView, false);
renderTimeline();
renderRole();
syncMenuAccessibility();
