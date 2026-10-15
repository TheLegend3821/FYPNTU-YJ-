const BACKEND_URL = "http://localhost:8000";
const IMAGE_EXTENSIONS = ["png", "jpg", "jpeg", "webp", "bmp", "gif"];

const chat = document.getElementById("chat");
const emptyState = document.getElementById("empty-state");
const statusLine = document.getElementById("status-line");

const form = document.getElementById("ask-form");
const composer = document.querySelector(".composer");
const questionInput = document.getElementById("question");
const attachBtn = document.getElementById("attach-btn");
const fileInput = document.getElementById("image");
const attachmentPreview = document.getElementById("attachment-preview");
const imagePreviewImg = document.getElementById("image-preview-img");
const fileChip = document.getElementById("file-chip");
const fileChipName = document.getElementById("file-chip-name");
const removeAttachmentBtn = document.getElementById("remove-image-btn");
const submitBtn = document.getElementById("submit-btn");

function escapeHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function isImageFile(file) {
  const ext = file.name.split(".").pop().toLowerCase();
  return IMAGE_EXTENSIONS.includes(ext);
}

// Minimal markdown: **bold**, `code`, [text](url) links, newlines already preserved via CSS white-space.
function renderMarkdown(text) {
  let safe = escapeHtml(text);
  safe = safe.replace(/`([^`]+)`/g, "<code>$1</code>");
  safe = safe.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  // The model sometimes cites sources as markdown links despite being asked not to.
  // A real http(s) link is kept clickable; anything else (e.g. a bare "#") is flattened to plain text.
  safe = safe.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  safe = safe.replace(/\[([^\]]+)\]\([^)]*\)/g, "$1");
  return safe;
}

function scrollToBottom() {
  chat.scrollTop = chat.scrollHeight;
}

function sourceLocationLabel(s) {
  if (s.page) return `page ${s.page}`;
  if (s.slide) return `slide ${s.slide}`;
  if (s.sheet) return `${s.sheet}, row ${s.row}`;
  return null;
}

function addUserMessage(question, file, imageDataUrl) {
  emptyState.hidden = true;
  const row = document.createElement("div");
  row.className = "msg-row user";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (file) {
    if (imageDataUrl) {
      const img = document.createElement("img");
      img.src = imageDataUrl;
      img.className = "attached-thumb";
      bubble.appendChild(img);
    } else {
      const chip = document.createElement("div");
      chip.className = "file-chip";
      chip.style.marginBottom = "0.4rem";
      chip.innerHTML = `<span class="file-chip-icon">&#128196;</span><span class="file-chip-name">${escapeHtml(file.name)}</span>`;
      bubble.appendChild(chip);
    }
  }
  const textNode = document.createElement("div");
  textNode.textContent = question;
  bubble.appendChild(textNode);
  row.appendChild(bubble);
  chat.appendChild(row);
  scrollToBottom();
}

function addTypingIndicator() {
  const row = document.createElement("div");
  row.className = "msg-row assistant";
  row.id = "typing-row";
  row.innerHTML = `<div class="bubble"><div class="typing-dots"><span></span><span></span><span></span></div></div>`;
  chat.appendChild(row);
  scrollToBottom();
  return row;
}

function removeTypingIndicator() {
  document.getElementById("typing-row")?.remove();
}

function buildSourcesDisclosure(sources) {
  const details = document.createElement("details");
  details.className = "sources";
  const summary = document.createElement("summary");
  summary.textContent = `Matched context (${sources.length})`;
  details.appendChild(summary);
  const ul = document.createElement("ul");
  sources.forEach((s) => {
    const li = document.createElement("li");
    const snippet = document.createElement("div");
    snippet.textContent = s.text.slice(0, 200) + (s.text.length > 200 ? "..." : "");
    li.appendChild(snippet);

    if (s.file) {
      const loc = sourceLocationLabel(s);
      const sourceLine = document.createElement("div");
      sourceLine.className = "source-file";
      if (s.download_url) {
        const a = document.createElement("a");
        a.href = `${BACKEND_URL}${s.download_url}`;
        a.textContent = `${s.file}${loc ? " (" + loc + ")" : ""} — Download`;
        a.target = "_blank";
        a.rel = "noopener";
        sourceLine.appendChild(a);
      } else {
        sourceLine.textContent = `${s.file}${loc ? " (" + loc + ")" : ""}`;
      }
      li.appendChild(sourceLine);
    }
    ul.appendChild(li);
  });
  details.appendChild(ul);
  return details;
}

function buildPrimarySourceCallout(primary) {
  const loc = sourceLocationLabel(primary);
  const box = document.createElement("div");
  box.className = "primary-source";
  box.innerHTML = `
    <span class="ps-icon">&#128196;</span>
    <span class="ps-text">
      <div class="ps-label">This looks like it's from</div>
      <div class="ps-file">${escapeHtml(primary.file)}${loc ? " (" + escapeHtml(loc) + ")" : ""}</div>
    </span>
  `;
  if (primary.download_url) {
    const a = document.createElement("a");
    a.className = "ps-download";
    a.href = `${BACKEND_URL}${primary.download_url}`;
    a.textContent = "Download";
    a.target = "_blank";
    a.rel = "noopener";
    box.appendChild(a);
  }
  return box;
}

function addPlainAssistantMessage(text, isError) {
  const row = document.createElement("div");
  row.className = "msg-row assistant";
  const bubble = document.createElement("div");
  bubble.className = "bubble" + (isError ? " error" : "");
  bubble.innerHTML = renderMarkdown(text);
  row.appendChild(bubble);
  chat.appendChild(row);
  scrollToBottom();
  return bubble;
}

function addStandaloneActionRow(buttons) {
  const row = document.createElement("div");
  row.className = "action-row";
  row.style.marginLeft = "0.2rem";
  buttons.forEach(({ label, primary, onClick }) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "action-btn" + (primary ? " primary" : "");
    btn.textContent = label;
    btn.addEventListener("click", onClick);
    row.appendChild(btn);
  });
  chat.appendChild(row);
  scrollToBottom();
  return row;
}

function addContinueOrEndRow() {
  const row = addStandaloneActionRow([
    {
      label: "Ask another question",
      primary: true,
      onClick: () => {
        row.remove();
        questionInput.focus();
      },
    },
    {
      label: "End session",
      onClick: () => {
        row.remove();
        endSession();
      },
    },
  ]);
}

async function handleExplainRequest(question, sources, actionRow) {
  actionRow.remove();
  removeTypingIndicator();
  addTypingIndicator();

  try {
    const res = await fetch(`${BACKEND_URL}/explain`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, chunks: sources }),
    });
    removeTypingIndicator();
    if (!res.ok) throw new Error(`Backend returned ${res.status}`);
    const data = await res.json();
    addPlainAssistantMessage(data.explanation, false);
  } catch (err) {
    removeTypingIndicator();
    addPlainAssistantMessage(`Error getting explanation: ${err.message}`, true);
  }
  addContinueOrEndRow();
}

function endSession() {
  addPlainAssistantMessage("Session ended. Thanks for the questions!", false);
  const closingRow = addStandaloneActionRow([
    {
      label: "Start new session",
      primary: true,
      onClick: () => startNewSession(closingRow),
    },
  ]);
  composer.classList.add("disabled");
  questionInput.disabled = true;
  submitBtn.disabled = true;
}

function startNewSession(closingRow) {
  closingRow?.remove();
  chat.innerHTML = "";
  chat.appendChild(emptyState);
  emptyState.hidden = false;
  composer.classList.remove("disabled");
  questionInput.disabled = false;
  submitBtn.disabled = false;
  questionInput.focus();
}

function addAssistantAnswer(question, answer, sources, primarySource, isError) {
  const row = document.createElement("div");
  row.className = "msg-row assistant";
  const bubble = document.createElement("div");
  bubble.className = "bubble" + (isError ? " error" : "");
  bubble.innerHTML = renderMarkdown(answer);

  if (primarySource) {
    bubble.appendChild(buildPrimarySourceCallout(primarySource));
  }
  if (sources && sources.length > 0) {
    bubble.appendChild(buildSourcesDisclosure(sources));
  }

  row.appendChild(bubble);
  chat.appendChild(row);
  scrollToBottom();

  if (isError) return;

  if (sources && sources.length > 0) {
    const actionRow = addStandaloneActionRow([
      {
        label: "Explain the working",
        primary: true,
        onClick: () => handleExplainRequest(question, sources, actionRow),
      },
      {
        label: "No thanks",
        onClick: () => {
          actionRow.remove();
          addContinueOrEndRow();
        },
      },
    ]);
  } else {
    addContinueOrEndRow();
  }
}

function fileToDataUrl(file) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.readAsDataURL(file);
  });
}

attachBtn.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", async () => {
  const file = fileInput.files[0];
  if (!file) return;

  if (isImageFile(file)) {
    imagePreviewImg.src = await fileToDataUrl(file);
    imagePreviewImg.hidden = false;
    fileChip.hidden = true;
  } else {
    fileChipName.textContent = file.name;
    fileChip.hidden = false;
    imagePreviewImg.hidden = true;
  }
  attachmentPreview.hidden = false;
});

removeAttachmentBtn.addEventListener("click", () => {
  fileInput.value = "";
  attachmentPreview.hidden = true;
});

questionInput.addEventListener("input", () => {
  questionInput.style.height = "auto";
  questionInput.style.height = Math.min(questionInput.scrollHeight, 120) + "px";
});

questionInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    form.requestSubmit();
  }
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = questionInput.value.trim();
  if (!question) return;

  // A pending "Explain / Continue / End" row from the previous turn is stale once a
  // new question is asked — drop it so the chat doesn't accumulate dead controls.
  document.querySelectorAll(".action-row").forEach((el) => el.remove());

  const file = fileInput.files[0];
  const imageDataUrl = file && isImageFile(file) ? imagePreviewImg.src : null;

  addUserMessage(question, file, imageDataUrl);
  questionInput.value = "";
  questionInput.style.height = "auto";
  attachmentPreview.hidden = true;
  submitBtn.disabled = true;
  addTypingIndicator();

  try {
    let res;
    if (file) {
      const formData = new FormData();
      formData.append("question", question);
      formData.append("file", file);
      res = await fetch(`${BACKEND_URL}/ask-file`, { method: "POST", body: formData });
    } else {
      res = await fetch(`${BACKEND_URL}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
    }
    fileInput.value = "";

    if (!res.ok) throw new Error(`Backend returned ${res.status}`);
    const data = await res.json();

    removeTypingIndicator();
    addAssistantAnswer(question, data.answer, data.sources, data.primary_source, false);
  } catch (err) {
    removeTypingIndicator();
    addAssistantAnswer(question, `Error: ${err.message}`, [], null, true);
  } finally {
    submitBtn.disabled = false;
    questionInput.focus();
  }
});

async function checkStatus() {
  try {
    const res = await fetch(`${BACKEND_URL}/status`);
    const data = await res.json();
    statusLine.textContent = `Connected · ${data.ingested_chunks} chunks indexed`;
  } catch {
    statusLine.textContent = "Backend unreachable";
  }
}

checkStatus();
