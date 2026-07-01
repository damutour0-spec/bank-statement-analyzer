const fs = require("fs");

async function main() {
  const path = process.argv[2] || "samples/sample_statement.csv";
  const baseUrl = process.env.BASE_URL || "http://127.0.0.1:8765";
  const boundary = `----codex${Date.now()}`;
  const body = Buffer.concat([
    Buffer.from(
      `--${boundary}\r\n` +
        `Content-Disposition: form-data; name="file"; filename="${path.split(/[\\/]/).pop()}"\r\n` +
        `Content-Type: application/octet-stream\r\n\r\n`,
    ),
    fs.readFileSync(path),
    Buffer.from(`\r\n--${boundary}--\r\n`),
  ]);

  const response = await fetch(`${baseUrl.replace(/\/$/, "")}/api/upload`, {
    method: "POST",
    headers: {
      "Content-Type": `multipart/form-data; boundary=${boundary}`,
      "Content-Length": String(body.length),
    },
    body,
  });
  const payload = await response.json();
  console.log(JSON.stringify({
    status: payload.status,
    transactionCount: payload.statement?.transaction_count,
    findingCount: payload.findings?.length,
    exportUrl: payload.export_url,
    error: payload.error,
  }, null, 2));
  if (!response.ok || payload.status !== "done") {
    process.exit(1);
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
