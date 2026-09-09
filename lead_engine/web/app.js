const state = {
  snapshot: null,
  hits: [],
  selectedHits: new Set(),
  selectedLeads: new Set(),
};

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (path.endsWith(".csv") && response.ok) {
    return response.text();
  }
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || response.statusText);
  }
  return payload;
}

function toast(node, message) {
  if (node) node.textContent = message;
}

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((el) => el.classList.remove("on"));
    btn.classList.add("on");
    document.querySelectorAll(".view").forEach((view) => view.classList.add("hidden"));
    document.getElementById(`view-${btn.dataset.tab}`).classList.remove("hidden");
  });
});

document.querySelectorAll("[data-preset]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const presets = {
      pm: { title: "Property Manager", loc: "Jacksonville" },
      hoa: { title: "Community Manager", loc: "First Coast" },
      fac: { title: "Facilities Director", loc: "Jacksonville" },
    };
    const preset = presets[btn.dataset.preset];
    $("hunt-title").value = preset.title;
    $("hunt-location").value = preset.loc;
  });
});

async function refresh() {
  state.snapshot = await api("/api/snapshot");
  renderStats();
  renderLeads();
  renderGates();
  renderInbox();
  renderDeliver();
  renderMap(state.snapshot.leads, "lead");
}

function renderStats() {
  const s = state.snapshot.status;
  $("stats").innerHTML = [
    ["Leads", s.leads],
    ["Hot ≥ 75", s.hot],
    ["Safe to email", s.safe_to_email],
    ["Accounts", s.accounts],
  ]
    .map(([label, value]) => `<div class="stat"><b>${value}</b><span>${label}</span></div>`)
    .join("");
}

function renderHits(payload) {
  state.hits = payload.hits || [];
  state.selectedHits = new Set(state.hits.map((hit) => hit.id));
  toast($("hunt-meta"), `${payload.count} targets · ${payload.note}`);
  $("hunt-hits").innerHTML = state.hits
    .map(
      (hit) => `<li>
        <input type="checkbox" data-hit="${hit.id}" checked />
        <div>
          <strong>${hit.full_name}</strong>
          <span class="co">${hit.title} · ${hit.company} · ${hit.county} · ${hit.origin}</span>
          <span class="co">${hit.email || "no printed email"} · ${hit.phone || "no phone"}</span>
        </div>
        <span class="temp">${hit.source}</span>
      </li>`
    )
    .join("");
  $("hunt-hits").querySelectorAll("input[data-hit]").forEach((box) => {
    box.addEventListener("change", () => {
      if (box.checked) state.selectedHits.add(box.dataset.hit);
      else state.selectedHits.delete(box.dataset.hit);
    });
  });
  renderMap(state.hits, "hunt");
}

function renderLeads() {
  const temp = $("temp-filter").value;
  const leads = (state.snapshot.leads || []).filter((lead) => !temp || lead.lead_temperature === temp);
  $("lead-body").innerHTML = leads
    .map((lead) => {
      const safe = lead.is_safe_to_email;
      return `<tr>
        <td><input type="checkbox" data-lead="${lead.id}" /></td>
        <td>${lead.full_name}</td>
        <td>${lead.title}<span class="co">${lead.company || "—"} · ${lead.county}</span></td>
        <td class="${safe ? "safe" : "unsafe"}">${lead.email || "—"}<span class="co">${lead.email_status}${safe ? " · safe" : " · do not email"}</span></td>
        <td><span class="temp ${lead.lead_temperature}">${lead.lead_score} ${lead.lead_temperature}</span></td>
        <td>${lead.status}<span class="co">${lead.last_action || ""}</span></td>
      </tr>`;
    })
    .join("");
  $("lead-body").querySelectorAll("input[data-lead]").forEach((box) => {
    box.addEventListener("change", () => {
      if (box.checked) state.selectedLeads.add(box.dataset.lead);
      else state.selectedLeads.delete(box.dataset.lead);
    });
  });
}

function renderGates() {
  const stages = state.snapshot.status.stages || [];
  const counts = state.snapshot.status.pipeline || {};
  $("gates").innerHTML = stages
    .map(
      (stage) => `<li class="gate"><b>${counts[stage.id] ?? 0}</b><strong>${stage.label}</strong><span>${stage.hint}</span></li>`
    )
    .join("");
}

function renderInbox() {
  $("captures").innerHTML = (state.snapshot.captures || [])
    .map(
      (cap) => `<li>
        <strong>${cap.name}</strong> · urgency ${cap.urgency}
        <span class="co">${cap.service}</span>
        <span class="co">${cap.message}</span>
        <span class="co">${cap.response_draft}</span>
      </li>`
    )
    .join("");
}

function renderDeliver() {
  $("batches").innerHTML = (state.snapshot.batches || [])
    .map((batch) => `<li><strong>${batch.client_name}</strong><span class="co">${(batch.lead_ids || []).length} leads · ${batch.notes || ""}</span></li>`)
    .join("");
  $("activity").innerHTML = (state.snapshot.activity || [])
    .map((item) => `<li><strong>${item.title}</strong><span class="co">${item.detail}</span></li>`)
    .join("");
}

function renderMap(items, kind) {
  const map = $("map");
  map.querySelectorAll(".pin").forEach((pin) => pin.remove());
  for (const item of items || []) {
    const point = item.map;
    if (!point) continue;
    const pin = document.createElement("div");
    pin.className = `pin ${item.lead_temperature || "hunt"}`;
    pin.style.left = `${point.x}%`;
    pin.style.top = `${point.y}%`;
    pin.title = item.full_name || item.company;
    map.appendChild(pin);
  }
}

$("hunt-run").addEventListener("click", async () => {
  try {
    const payload = await api("/api/hunt", {
      method: "POST",
      body: JSON.stringify({
        query: $("hunt-query").value,
        title: $("hunt-title").value,
        location: $("hunt-location").value,
      }),
    });
    renderHits(payload);
  } catch (err) {
    toast($("hunt-meta"), err.message);
  }
});

$("hunt-import").addEventListener("click", async () => {
  try {
    const result = await api("/api/hunt/import", {
      method: "POST",
      body: JSON.stringify({ ids: [...state.selectedHits] }),
    });
    toast($("hunt-meta"), `${result.created} added · ${result.updated} merged`);
    await refresh();
  } catch (err) {
    toast($("hunt-meta"), err.message);
  }
});

$("scrape-btn").addEventListener("click", async () => {
  $("scrape-out").textContent = "Extracting printed contacts…";
  try {
    const result = await api("/api/enrich", {
      method: "POST",
      body: JSON.stringify({ url: $("scrape-url").value }),
    });
    const scrape = result.scrape;
    $("scrape-out").textContent = [
      scrape.note,
      `emails: ${scrape.emails.join(", ") || "(none printed)"}`,
      `phones: ${scrape.phones.join(", ") || "(none)"}`,
      `socials: ${JSON.stringify(scrape.socials)}`,
      scrape.text.slice(0, 600),
    ].join("\n");
  } catch (err) {
    $("scrape-out").textContent = err.message;
  }
});

$("pipeline-run").addEventListener("click", async () => {
  try {
    const result = await api("/api/pipeline", { method: "POST", body: "{}" });
    toast(
      $("pipeline-meta"),
      `${result.updated} scored · ${result.invalid} dropped · hot ${result.hot_ids.length}`
    );
    await refresh();
  } catch (err) {
    toast($("pipeline-meta"), err.message);
  }
});

$("temp-filter").addEventListener("change", renderLeads);

async function downloadCsv(safe) {
  const text = await api(safe ? "/api/export.csv?safe=1" : "/api/export.csv");
  const blob = new Blob([text], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = safe ? "nexus-leads-safe.csv" : "nexus-leads.csv";
  a.click();
  URL.revokeObjectURL(url);
}

$("export-csv").addEventListener("click", () => downloadCsv(false));
$("export-safe").addEventListener("click", () => downloadCsv(true));

$("csv-sample").addEventListener("click", async () => {
  const sample = await api("/api/sample.csv");
  $("csv-text").value = sample.csv.trim();
});

$("csv-import").addEventListener("click", async () => {
  const result = await api("/api/import-csv", {
    method: "POST",
    body: JSON.stringify({ csv: $("csv-text").value }),
  });
  await refresh();
  alert(`${result.created} created · ${result.updated} merged`);
});

$("cap-add").addEventListener("click", async () => {
  await api("/api/captures", {
    method: "POST",
    body: JSON.stringify({
      name: $("cap-name").value,
      email: $("cap-email").value,
      service: $("cap-service").value,
      message: $("cap-message").value,
    }),
  });
  $("cap-name").value = "";
  $("cap-email").value = "";
  $("cap-message").value = "";
  await refresh();
});

$("deliver-btn").addEventListener("click", async () => {
  const ids = [...state.selectedLeads];
  if (!ids.length) {
    alert("Select leads in the ledger first.");
    return;
  }
  await api("/api/deliver", {
    method: "POST",
    body: JSON.stringify({
      ids,
      client_name: $("client-name").value,
      notes: $("client-notes").value,
    }),
  });
  state.selectedLeads.clear();
  await refresh();
});

$("reset-demo").addEventListener("click", async () => {
  if (!confirm("Reset the demo desk?")) return;
  await api("/api/reset", { method: "POST", body: "{}" });
  await refresh();
});

$("hunt-location").addEventListener("input", async () => {
  const data = await api(`/api/autocomplete?input=${encodeURIComponent($("hunt-location").value)}`);
  $("city-list").innerHTML = (data.predictions || [])
    .map((city) => `<option value="${city.name}, ${city.state}"></option>`)
    .join("");
});

refresh().catch((err) => {
  $("stats").textContent = err.message;
});
