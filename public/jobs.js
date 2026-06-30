const jobsTable = document.querySelector("#jobsTable");
const refreshJobs = document.querySelector("#refreshJobs");

if (refreshJobs && jobsTable) {
  refreshJobs.addEventListener("click", loadJobs);
  document.addEventListener("DOMContentLoaded", loadJobs);
}

async function loadJobs() {
  try {
    const response = await fetch("/api/jobs");
    const payload = await response.json();
    renderJobs(payload.jobs || []);
  } catch (error) {
    jobsTable.replaceChildren(rowWithText(error.message, 6));
  }
}

function renderJobs(jobs) {
  jobsTable.replaceChildren();
  if (!jobs.length) {
    jobsTable.appendChild(rowWithText("暂无任务", 6));
    return;
  }
  for (const job of jobs.slice(0, 20)) {
    const statement = job.statement || {};
    const row = document.createElement("tr");
    appendCell(row, job.file_name || "-");
    appendCell(row, job.status || "-");
    appendCell(row, statement.transaction_count || 0);
    appendCell(row, (job.findings || []).length);
    appendCell(row, job.created_at || job.updated_at || "-");
    const action = document.createElement("td");
    if (job.export_url) {
      const link = document.createElement("a");
      link.href = job.export_url;
      link.textContent = "下载";
      link.className = "mini-link";
      action.appendChild(link);
    } else {
      action.textContent = "-";
    }
    row.appendChild(action);
    jobsTable.appendChild(row);
  }
}

function appendCell(row, value) {
  const cell = document.createElement("td");
  cell.textContent = value;
  row.appendChild(cell);
}

function rowWithText(text, colspan) {
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.colSpan = colspan;
  cell.className = "muted";
  cell.textContent = text;
  row.appendChild(cell);
  return row;
}
