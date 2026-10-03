// Placeholder page: it only proves that the data file loads. The next plan replaces it with the charts.
const status = document.getElementById("status");

async function main() {
  const response = await fetch("data.json", { cache: "no-cache" });
  if (!response.ok) throw new Error(`data.json answered ${response.status}`);
  const data = await response.json();
  const tenYear = data.yields.tenors.findIndex((tenor) => tenor.label === "10Y");
  const latest = data.yields.values[tenYear].at(-1);
  const { cut, hold, hike } = data.odds.summary;
  status.textContent =
    `Snapshot ${data.snapshot_id}. 10-year yield ${latest.toFixed(2)}% on ${data.yields.as_of}. ` +
    `Odds for ${data.odds.meeting}: cut ${cut}%, hold ${hold}%, hike ${hike}%.`;
}

main().catch((error) => {
  status.textContent = `The data could not be loaded: ${error.message}`;
});
