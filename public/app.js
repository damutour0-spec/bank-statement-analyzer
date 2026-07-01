const form = document.querySelector("#uploadForm");
const fileInput = document.querySelector("#fileInput");
const statusText = document.querySelector("#statusText");
const result = document.querySelector("#result");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!fileInput.files.length) {
    statusText.textContent = "请先选择文件";
    return;
  }
  const data = new FormData();
  data.append("file", fileInput.files[0]);
  statusText.textContent = "正在上传并解析...";
  try {
    const response = await apiFetch("/api/upload", {
      method: "POST",
      body: data,
    });
    const payload = await response.json();
    if (!response.ok || payload.status === "failed") {
      throw new Error(payload.error || "解析失败");
    }
    renderJob(payload);
    statusText.textContent = "解析完成";
  } catch (error) {
    statusText.textContent = error.message;
  }
});

function renderJob(job) {
  result.classList.remove("hidden");
  const statement = job.statement || {};
  document.querySelector("#bankName").textContent = statement.bank_name || "-";
  document.querySelector("#txnCount").textContent = statement.transaction_count || 0;
  document.querySelector("#findingCount").textContent = (job.findings || []).length;
  document.querySelector("#confidence").textContent = statement.confidence ? `${Math.round(statement.confidence * 100)}%` : "-";
  const exportLink = document.querySelector("#exportLink");
  exportLink.href = job.export_url ? apiUrl(job.export_url) : "#";

  const findings = document.querySelector("#findings");
  findings.innerHTML = "";
  if (!job.findings || !job.findings.length) {
    findings.innerHTML = "<p class=\"label\">暂无异常提示</p>";
  } else {
    for (const finding of job.findings.slice(0, 30)) {
      const item = document.createElement("article");
      item.className = `finding ${finding.severity}`;
      item.innerHTML = `
        <strong>${escapeHtml(finding.title)}</strong>
        <p>${escapeHtml(finding.description || "")}</p>
        <p>${escapeHtml(finding.suggestion || "")}</p>
      `;
      findings.appendChild(item);
    }
  }

  const transactions = document.querySelector("#transactions");
  transactions.innerHTML = "";
  for (const txn of (job.transactions || []).slice(0, 100)) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${escapeHtml(txn.transaction_date || "")}</td>
      <td>${escapeHtml(txn.summary || "")}</td>
      <td>${escapeHtml(txn.counterparty_name || "")}</td>
      <td>${escapeHtml(txn.income_amount || "0")}</td>
      <td>${escapeHtml(txn.expense_amount || "0")}</td>
      <td>${escapeHtml(txn.balance || "")}</td>
    `;
    transactions.appendChild(row);
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
