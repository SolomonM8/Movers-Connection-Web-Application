(function () {
  if (typeof SELECTED_STATE === "undefined" || !SELECTED_STATE) return;

  const STATE_FIPS_TO_ABBR = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT",
    "10": "DE", "11": "DC", "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL",
    "18": "IN", "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD",
    "25": "MA", "26": "MI", "27": "MN", "28": "MS", "29": "MO", "30": "MT", "31": "NE",
    "32": "NV", "33": "NH", "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND",
    "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD",
    "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA", "54": "WV",
    "55": "WI", "56": "WY",
  };
  const ABBR_TO_STATE_FIPS = {};
  Object.keys(STATE_FIPS_TO_ABBR).forEach((fips) => {
    ABBR_TO_STATE_FIPS[STATE_FIPS_TO_ABBR[fips]] = fips;
  });

  const mapContainer = document.getElementById("map-container");
  const statusEl = document.getElementById("map-status");
  const summaryList = document.getElementById("service-summary-list");
  const countEl = document.getElementById("service-count");
  const defaultStatus = `Click counties in ${SELECTED_STATE} to add or remove them.`;

  let selectedFips = new Set(SELECTED_FIPS);

  const width = mapContainer.clientWidth || 900;
  const height = 550;

  const svg = d3
    .select(mapContainer)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`);
  const regionLayer = svg.append("g");
  const path = d3.geoPath();

  const stateFipsStr = ABBR_TO_STATE_FIPS[SELECTED_STATE];

  d3.json("https://cdn.jsdelivr.net/npm/us-atlas@3/counties-10m.json")
    .then((us) => {
      const countiesFC = topojson.feature(us, us.objects.counties);
      const stateCounties = {
        type: "FeatureCollection",
        features: countiesFC.features.filter(
          (f) => String(f.id).padStart(5, "0").slice(0, 2) === stateFipsStr
        ),
      };

      const projection = d3.geoMercator().fitSize([width, height], stateCounties);
      path.projection(projection);

      regionLayer
        .selectAll("path.region")
        .data(stateCounties.features, (d) => d.id)
        .join("path")
        .attr("class", (d) =>
          "region county" + (selectedFips.has(String(d.id).padStart(5, "0")) ? " selected" : "")
        )
        .attr("d", path)
        .on("click", function (event, d) {
          const fips = String(d.id).padStart(5, "0");
          toggleCounty(fips, this);
        });
    })
    .catch(() => {
      statusEl.textContent = "Sorry, the map couldn't be loaded. Please refresh to try again.";
    });

  function toggleCounty(fips, element) {
    const isSelected = selectedFips.has(fips);
    if (!isSelected && selectedFips.size >= MAX_COUNTIES) {
      statusEl.textContent = `You can only select up to ${MAX_COUNTIES} counties. Remove one to add another.`;
      return;
    }

    fetch(`/coverage/api/service-areas/${fips}/toggle/`, {
      method: "POST",
      headers: { "X-CSRFToken": CSRF_TOKEN },
    })
      .then((response) => response.json().then((data) => ({ ok: response.ok, data })))
      .then(({ ok, data }) => {
        if (!ok) {
          statusEl.textContent = data.message || "Something went wrong. Please try again.";
          return;
        }
        selectedFips = new Set(data.selected_fips);
        d3.select(element).classed("selected", data.status === "added");
        countEl.textContent = data.total_count;
        statusEl.textContent = defaultStatus;
        renderSummary(data.summary);
      })
      .catch(() => {
        statusEl.textContent = "Couldn't save your change. Please try again.";
      });
  }

  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value == null ? "" : String(value);
    return div.innerHTML;
  }

  function renderSummary(summary) {
    const entries = Object.entries(summary || {});
    if (!entries.length) {
      summaryList.innerHTML = "<p>You haven't selected any counties yet.</p>";
      return;
    }
    summaryList.innerHTML = entries
      .map(
        ([state, counties]) =>
          `<p><strong>${escapeHtml(state)}:</strong> ${escapeHtml(counties.join(", "))}</p>`
      )
      .join("");
  }
})();
