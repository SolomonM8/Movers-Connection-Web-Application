(function () {
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

  const mapContainer = document.getElementById("map-container");
  const backButton = document.getElementById("back-button");
  const statusEl = document.getElementById("map-status");
  const panel = document.getElementById("county-panel");

  const width = mapContainer.clientWidth || 900;
  const height = 550;

  const svg = d3
    .select(mapContainer)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`);

  const regionLayer = svg.append("g").attr("class", "region-layer");
  const cityLayer = svg.append("g").attr("class", "city-layer");
  const path = d3.geoPath();

  let statesFC, countiesFC, allCities;

  Promise.all([
    d3.json("https://cdn.jsdelivr.net/npm/us-atlas@3/counties-10m.json"),
    d3.json("/static/coverage/data/cities.json"),
  ])
    .then(([us, cities]) => {
      statesFC = topojson.feature(us, us.objects.states);
      countiesFC = topojson.feature(us, us.objects.counties);
      allCities = cities;
      drawNation();
    })
    .catch(() => {
      statusEl.textContent = "Sorry, the map data couldn't be loaded. Please refresh to try again.";
    });

  function fitProjection(featureCollection, useAlbersUsa) {
    const projection = useAlbersUsa
      ? d3.geoAlbersUsa().fitSize([width, height], featureCollection)
      : d3.geoMercator().fitSize([width, height], featureCollection);
    path.projection(projection);
    return projection;
  }

  function drawNation() {
    backButton.classList.add("hidden");
    panel.classList.add("hidden");
    statusEl.textContent = "Click a state to see its counties.";

    const projection = fitProjection(statesFC, true);

    regionLayer
      .selectAll("path.region")
      .data(statesFC.features, (d) => d.id)
      .join("path")
      .attr("class", "region state")
      .attr("d", path)
      .on("click", (event, d) => {
        const abbr = STATE_FIPS_TO_ABBR[String(d.id).padStart(2, "0")];
        if (abbr) drawState(abbr, d.id);
      });

    drawCities(allCities.filter((c) => c.major), projection);
  }

  function drawState(abbr, stateFipsId) {
    panel.classList.add("hidden");
    backButton.classList.remove("hidden");
    statusEl.textContent = `${STATE_NAMES[abbr] || abbr}: click a county to see labor groups serving that area.`;

    const stateFipsStr = String(stateFipsId).padStart(2, "0");
    const stateCounties = {
      type: "FeatureCollection",
      features: countiesFC.features.filter(
        (f) => String(f.id).padStart(5, "0").slice(0, 2) === stateFipsStr
      ),
    };

    const projection = fitProjection(stateCounties, false);

    regionLayer
      .selectAll("path.region")
      .data(stateCounties.features, (d) => d.id)
      .join("path")
      .attr("class", "region county")
      .attr("d", path)
      .on("click", (event, d) => {
        const fips = String(d.id).padStart(5, "0");
        showCountyLaborers(fips);
      });

    drawCities(
      allCities.filter((c) => c.state === abbr && c.population >= 50000),
      projection
    );
  }

  function drawCities(cities, projection) {
    const groups = cityLayer
      .selectAll("g.city")
      .data(cities, (d) => d.name + d.state);

    groups.exit().remove();

    const entered = groups
      .enter()
      .append("g")
      .attr("class", "city");
    entered.append("circle").attr("r", 2.5);
    entered.append("text").attr("x", 5).attr("y", 3);

    const merged = entered.merge(groups);
    merged.attr("transform", (d) => {
      const coords = projection([d.lon, d.lat]);
      return coords ? `translate(${coords[0]},${coords[1]})` : "translate(-1000,-1000)";
    });
    merged.select("text").text((d) => d.name);
  }

  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value == null ? "" : String(value);
    return div.innerHTML;
  }

  function showCountyLaborers(fips) {
    panel.classList.remove("hidden");
    panel.innerHTML = "<p>Loading&hellip;</p>";
    fetch(`/coverage/api/counties/${fips}/laborers/`)
      .then((response) => response.json())
      .then((data) => {
        const countyName = escapeHtml(data.county_name);
        const stateAbbr = escapeHtml(data.state);
        if (!data.laborers.length) {
          panel.innerHTML = `<h3>${countyName}, ${stateAbbr}</h3><p>No labor groups have registered coverage for this county yet.</p>`;
          return;
        }
        const cards = data.laborers
          .map((laborer) => {
            const name = escapeHtml(laborer.display_name);
            const city = escapeHtml(laborer.city);
            const state = escapeHtml(laborer.state);
            const phone = escapeHtml(laborer.phone_number);
            return `
              <div class="laborer-card">
                <strong>${name}</strong>
                <p>${city ? city + ", " + state : ""}</p>
                <p>${phone}</p>
              </div>
            `;
          })
          .join("");
        panel.innerHTML = `<h3>${countyName}, ${stateAbbr}</h3>${cards}`;
      })
      .catch(() => {
        panel.innerHTML = "<p>Couldn't load labor groups for this county. Please try again.</p>";
      });
  }

  backButton.addEventListener("click", drawNation);
})();
