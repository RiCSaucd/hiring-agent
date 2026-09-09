const state = {
  selectedJobId: null,
  applicationId: null,
  jobs: [],
};

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || response.statusText);
  }
  return payload;
}

function setText(id, value) {
  $(id).textContent = value;
}

async function refreshLedger() {
  const data = await api("/api/applications");
  const body = $("ledger-body");
  if (!data.applications.length) {
    body.innerHTML = "<tr><td colspan='5'>No applications yet.</td></tr>";
    return;
  }
  body.innerHTML = data.applications
    .map((row) => {
      const job = row.job || {};
      const fit = (row.fit && row.fit.score) ?? "—";
      return `<tr>
        <td>${row.id}</td>
        <td>${job.title || row.job_id}</td>
        <td>${job.company || ""}</td>
        <td>${fit}</td>
        <td>${row.status}</td>
      </tr>`;
    })
    .join("");
}

function renderPerson(resume, review) {
  const person = $("person");
  person.hidden = false;
  const contact = [resume.email || "no email", resume.phone, resume.location || "location unknown"]
    .filter(Boolean)
    .join(" · ");
  person.innerHTML = `<strong>${resume.name || "Candidate"}</strong>
    <div>${contact}</div>
    <div>${(resume.skills || []).slice(0, 8).join(" · ")}</div>`;

  $("score-row").hidden = false;
  const stamp = $("stamp");
  stamp.textContent = String(review.overall);
  stamp.className = "stamp" + (review.overall >= 70 ? "" : review.overall >= 50 ? " warn" : " fail");
  $("score-caption").textContent = review.llm_used
    ? `ATS-style review ${review.overall}/100 · recruiter model ${review.recruiter_score}`
    : `ATS-style review ${review.overall}/100 · no LLM configured, heuristic only`;

  $("findings").innerHTML = review.findings
    .map(
      (item) =>
        `<li><span class="sev ${item.severity}">${item.severity}</span><strong>${item.title}.</strong> ${item.detail}</li>`
    )
    .join("");
}

function renderJobs(payload) {
  state.jobs = payload.jobs || [];
  const skipped = (payload.skipped_sources || []).join(", ") || "none";
  $("search-meta").textContent =
    `${payload.count} matches · live ${payload.live_count} · skipped sources: ${skipped}`;
  $("jobs").innerHTML = state.jobs
    .map((job) => {
      const fit = job.fit ? job.fit.score : "—";
      return `<li data-id="${job.id}">
        <span class="fit">${fit}</span>
        <strong>${job.title}</strong>
        <span class="co">${job.company} · ${job.location || (job.remote ? "Remote" : "")}</span>
      </li>`;
    })
    .join("");
}

function selectedJob() {
  return state.jobs.find((job) => job.id === state.selectedJobId) || null;
}

function showPacketShell(job) {
  $("packet-empty").hidden = true;
  $("packet-body").hidden = false;
  $("packet-job").textContent = `${job.title} · ${job.company}`;
  const fit = job.fit;
  $("packet-fit").textContent = fit
    ? `Fit ${fit.score}/100. ${ (fit.reasons || []).join(" ") }`
    : "Prepare a packet to score this listing against your resume.";
  $("apply-btn").disabled = true;
  $("apply-note").textContent = "";
  state.applicationId = null;
}

async function preparePacket() {
  if (!state.selectedJobId) return;
  const application = await api("/api/applications", {
    method: "POST",
    body: JSON.stringify({ job_id: state.selectedJobId }),
  });
  state.applicationId = application.id;
  $("cover").textContent = application.packet.cover_letter;
  $("bullets").innerHTML = application.packet.tailored_bullets
    .map((item) => `<li>${item}</li>`)
    .join("");
  $("checklist").innerHTML = application.packet.paste_checklist
    .map((item) => `<li>${item}</li>`)
    .join("");
  $("apply-btn").disabled = false;
  $("apply-note").textContent = `Draft #${application.id} ready. Confirm apply after you submit on the employer site, or to open their form.`;
  await refreshLedger();
}

async function confirmApply() {
  if (!state.applicationId) return;
  const ok = window.confirm(
    "This marks the job applied in your ledger and opens the employer page. It does not auto-fill their form. Continue?"
  );
  if (!ok) return;
  const application = await api(`/api/applications/${state.applicationId}/apply`, {
    method: "POST",
    body: JSON.stringify({ confirm: true }),
  });
  const applyUrl = (application.job && application.job.apply_url) || "";
  const note = $("apply-note");
  note.textContent = "Logged as applied. ";
  if (applyUrl) {
    const link = document.createElement("a");
    link.href = applyUrl;
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = "Open employer application";
    note.appendChild(link);
    window.open(applyUrl, "_blank", "noopener");
  }
  await refreshLedger();
}

async function uploadText(filename, text) {
  const payload = await api("/api/resume", {
    method: "POST",
    body: JSON.stringify({
      filename,
      text,
      target_role: $("target-role").value,
      target_location: $("target-location").value,
      remote_only: $("remote-only").checked,
    }),
  });
  renderPerson(payload.resume, payload.review);
}

async function handleFile(file) {
  if (file.name.toLowerCase().endsWith(".pdf")) {
    const buffer = await file.arrayBuffer();
    const bytes = new Uint8Array(buffer);
    let binary = "";
    bytes.forEach((b) => {
      binary += String.fromCharCode(b);
    });
    const content_b64 = btoa(binary);
    const payload = await api("/api/resume", {
      method: "POST",
      body: JSON.stringify({
        filename: file.name,
        content_b64,
        target_role: $("target-role").value,
        target_location: $("target-location").value,
        remote_only: $("remote-only").checked,
      }),
    });
    renderPerson(payload.resume, payload.review);
    return;
  }
  await uploadText(file.name, await file.text());
}

async function searchJobs() {
  const payload = await api("/api/jobs/search", {
    method: "POST",
    body: JSON.stringify({
      query: $("query").value,
      include_live: true,
      remote_only: $("remote-only").checked,
      location: $("target-location").value,
    }),
  });
  renderJobs(payload);
}

$("file").addEventListener("change", (event) => {
  const file = event.target.files && event.target.files[0];
  if (file) handleFile(file).catch((err) => alert(err.message));
});

const drop = $("drop");
drop.addEventListener("dragover", (event) => {
  event.preventDefault();
  drop.classList.add("hot");
});
drop.addEventListener("dragleave", () => drop.classList.remove("hot"));
drop.addEventListener("drop", (event) => {
  event.preventDefault();
  drop.classList.remove("hot");
  const file = event.dataTransfer.files && event.dataTransfer.files[0];
  if (file) handleFile(file).catch((err) => alert(err.message));
});

$("load-sample").addEventListener("click", async () => {
  const sample = await api("/api/sample-resume");
  if (!$("target-role").value) {
    $("target-role").value = sample.target_role || "Senior backend engineer";
  }
  await uploadText(sample.filename, sample.text);
  await searchJobs();
});

$("save-prefs").addEventListener("click", async () => {
  await api("/api/preferences", {
    method: "POST",
    body: JSON.stringify({
      target_role: $("target-role").value,
      target_location: $("target-location").value,
      remote_only: $("remote-only").checked,
    }),
  });
});

$("search-btn").addEventListener("click", () => searchJobs().catch((err) => alert(err.message)));

$("jobs").addEventListener("click", (event) => {
  const item = event.target.closest("li[data-id]");
  if (!item) return;
  state.selectedJobId = item.getAttribute("data-id");
  for (const node of $("jobs").querySelectorAll("li")) node.classList.remove("active");
  item.classList.add("active");
  const job = selectedJob();
  if (job) showPacketShell(job);
});

$("prepare-btn").addEventListener("click", () => preparePacket().catch((err) => alert(err.message)));
$("apply-btn").addEventListener("click", () => confirmApply().catch((err) => alert(err.message)));

$("paste-btn").addEventListener("click", async () => {
  const payload = await api("/api/jobs/paste", {
    method: "POST",
    body: JSON.stringify({
      title: $("paste-title").value,
      company: $("paste-company").value,
      apply_url: $("paste-url").value,
      url: $("paste-url").value,
      description: $("paste-desc").value,
      remote: true,
    }),
  });
  state.jobs = [payload.job, ...state.jobs.filter((job) => job.id !== payload.job.id)];
  if (payload.fit) payload.job.fit = payload.fit;
  renderJobs({ jobs: state.jobs, count: state.jobs.length, live_count: 0, skipped_sources: [] });
});

async function restoreDesk() {
  const profile = await api("/api/profile");
  if (profile.target_role) $("target-role").value = profile.target_role;
  if (profile.target_location) $("target-location").value = profile.target_location;
  $("remote-only").checked = !!profile.remote_only;
  if (profile.has_resume) {
    const reviewed = await api("/api/review");
    renderPerson(reviewed.resume, reviewed.review);
    await searchJobs();
  }
  await refreshLedger();
}

restoreDesk().catch(() => refreshLedger().catch(() => {}));
