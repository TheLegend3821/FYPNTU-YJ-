function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

async function loadStatus() {
  const res = await fetch("/admin/api/status", { credentials: "same-origin" });
  if (res.status === 401) {
    window.location.href = "/admin/login";
    return;
  }
  const data = await res.json();

  document.getElementById("stat-chunks").textContent = data.ingested_chunks;
  document.getElementById("stat-files").textContent = data.resource_files.length;
  document.getElementById("model-vision").textContent = data.models.vision;
  document.getElementById("model-embed").textContent = data.models.embedding;
  document.getElementById("model-gen").textContent = data.models.generation;

  const body = document.getElementById("files-body");
  body.innerHTML = "";
  if (data.resource_files.length === 0) {
    body.innerHTML = '<tr><td colspan="2" class="empty-row">No resource files yet. Upload one above, or drop files into backend/resources/.</td></tr>';
  } else {
    data.resource_files.forEach((f) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${f.name}</td><td>${formatSize(f.size_bytes)}</td>`;
      body.appendChild(tr);
    });
  }
}

document.getElementById("logout-btn").addEventListener("click", async () => {
  await fetch("/admin/api/logout", { method: "POST", credentials: "same-origin" });
  window.location.href = "/admin/login";
});

document.getElementById("ingest-btn").addEventListener("click", async () => {
  const btn = document.getElementById("ingest-btn");
  const statusEl = document.getElementById("ingest-status");
  btn.disabled = true;
  statusEl.className = "ingest-status";
  statusEl.innerHTML = '<span class="spinner"></span>Re-ingesting resource pool...';

  try {
    const res = await fetch("/admin/api/ingest", { method: "POST", credentials: "same-origin" });
    if (res.status === 401) {
      window.location.href = "/admin/login";
      return;
    }
    const data = await res.json();
    statusEl.className = "ingest-status ok";
    statusEl.textContent = data.message;
    await loadStatus();
  } catch (err) {
    statusEl.className = "ingest-status err";
    statusEl.textContent = "Ingestion failed: " + err.message;
  } finally {
    btn.disabled = false;
  }
});

document.getElementById("upload-btn").addEventListener("click", async () => {
  const input = document.getElementById("upload-input");
  const statusEl = document.getElementById("upload-status");
  const file = input.files[0];
  if (!file) {
    statusEl.className = "ingest-status err";
    statusEl.textContent = "Choose a file first.";
    return;
  }

  const btn = document.getElementById("upload-btn");
  btn.disabled = true;
  statusEl.className = "ingest-status";
  statusEl.innerHTML = '<span class="spinner"></span>Uploading and ingesting...';

  try {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch("/admin/api/upload", { method: "POST", credentials: "same-origin", body: formData });
    if (res.status === 401) {
      window.location.href = "/admin/login";
      return;
    }
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Upload failed");
    statusEl.className = "ingest-status ok";
    statusEl.textContent = `Uploaded ${data.uploaded}. ${data.message}`;
    input.value = "";
    await loadStatus();
  } catch (err) {
    statusEl.className = "ingest-status err";
    statusEl.textContent = "Upload failed: " + err.message;
  } finally {
    btn.disabled = false;
  }
});

loadStatus();
