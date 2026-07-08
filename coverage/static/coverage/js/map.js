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

  const FIT_PADDING = 24;

  const mapContainer = document.getElementById("map-container");
  const backButton = document.getElementById("back-button");
  const statusEl = document.getElementById("map-status");
  const panel = document.getElementById("county-panel");
  const panelContent = document.getElementById("county-panel-content");
  const panelClose = document.getElementById("panel-close");
  const zoomControls = document.getElementById("zoom-controls");
  const zoomInBtn = document.getElementById("zoom-in-btn");
  const zoomOutBtn = document.getElementById("zoom-out-btn");
  const addressInput = document.getElementById("address-search");
  const suggestionsList = document.getElementById("address-suggestions");

  function openPanel() {
    panel.classList.remove("hidden");
    document.body.classList.add("panel-open");
  }

  function closePanel() {
    panel.classList.add("hidden");
    document.body.classList.remove("panel-open");
  }

  panelClose.addEventListener("click", closePanel);

  const svg = d3.select(mapContainer).append("svg");
  const regionLayer = svg.append("g").attr("class", "region-layer");
  const cityLayer = svg.append("g").attr("class", "city-layer");
  const path = d3.geoPath();

  let statesFC, countiesFC, allCities, countyInfo;
  let zoom = null;
  const cityLabelCache = {};

  function containerSize() {
    const rect = mapContainer.getBoundingClientRect();
    return { width: rect.width || 900, height: rect.height || 550 };
  }

  Promise.all([
    d3.json("https://cdn.jsdelivr.net/npm/us-atlas@3/counties-10m.json"),
    d3.json("/static/coverage/data/cities.json"),
    d3.json("/static/coverage/data/counties.json"),
  ])
    .then(([us, cities, counties]) => {
      statesFC = topojson.feature(us, us.objects.states);
      countiesFC = topojson.feature(us, us.objects.counties);
      allCities = cities;
      countyInfo = {};
      counties.forEach((c) => {
        countyInfo[c.fips] = c;
      });
      drawNation();
    })
    .catch(() => {
      statusEl.textContent = "Sorry, the map data couldn't be loaded. Please refresh to try again.";
    });

  window.addEventListener("resize", () => {
    if (statesFC) {
      if (backButton.classList.contains("hidden")) {
        drawNation();
      }
    }
  });

  function fitProjection(featureCollection, useAlbersUsa, size) {
    const box = [
      [FIT_PADDING, FIT_PADDING],
      [size.width - FIT_PADDING, size.height - FIT_PADDING],
    ];
    const projection = useAlbersUsa
      ? d3.geoAlbersUsa().fitExtent(box, featureCollection)
      : d3.geoMercator().fitExtent(box, featureCollection);
    path.projection(projection);
    return projection;
  }

  function disableZoom() {
    if (zoom) {
      svg.on(".zoom", null);
      zoom = null;
    }
    regionLayer.attr("transform", null);
    cityLayer.attr("transform", null);
    zoomControls.classList.add("hidden");
  }

  function enableZoom(size) {
    zoom = d3
      .zoom()
      .scaleExtent([1, 10])
      .translateExtent([
        [0, 0],
        [size.width, size.height],
      ])
      .on("zoom", (event) => {
        regionLayer.attr("transform", event.transform);
        cityLayer.attr("transform", event.transform);
        cityLayer.selectAll("circle").attr("r", 2.5 / event.transform.k);
        cityLayer.selectAll("text").style("font-size", 10 / event.transform.k + "px");
      });
    svg.call(zoom);
    zoomControls.classList.remove("hidden");
  }

  zoomInBtn.addEventListener("click", () => {
    if (zoom) svg.transition().duration(200).call(zoom.scaleBy, 1.6);
  });
  zoomOutBtn.addEventListener("click", () => {
    if (zoom) svg.transition().duration(200).call(zoom.scaleBy, 1 / 1.6);
  });

  function drawNation() {
    backButton.classList.add("hidden");
    closePanel();
    disableZoom();
    statusEl.textContent = "Click a state to see its counties.";

    const size = containerSize();
    svg.attr("viewBox", `0 0 ${size.width} ${size.height}`);
    const projection = fitProjection(statesFC, true, size);

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
    closePanel();
    backButton.classList.remove("hidden");
    statusEl.textContent = `${STATE_NAMES[abbr] || abbr}: click a county to see labor groups serving that area.`;

    const stateFipsStr = String(stateFipsId).padStart(2, "0");
    const stateCounties = {
      type: "FeatureCollection",
      features: countiesFC.features.filter(
        (f) => String(f.id).padStart(5, "0").slice(0, 2) === stateFipsStr
      ),
    };

    const size = containerSize();
    svg.attr("viewBox", `0 0 ${size.width} ${size.height}`);
    const projection = fitProjection(stateCounties, false, size);

    regionLayer
      .selectAll("path.region")
      .data(stateCounties.features, (d) => d.id)
      .join("path")
      .attr("class", "region county")
      .attr("d", path)
      .on("click", function (event, d) {
        regionLayer.selectAll("path.region.county").classed("selected", false);
        d3.select(this).classed("selected", true);
        const fips = String(d.id).padStart(5, "0");
        showCountyLaborers(fips, d, abbr);
      });

    drawCities(getCountyCityLabels(abbr, stateCounties.features), projection);

    enableZoom(size);
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

  function bestCityInCounty(countyFeature, stateAbbr) {
    if (!countyFeature || !allCities) return null;
    const candidates = allCities.filter((c) => c.state === stateAbbr && c.population >= 50000);
    let best = null;
    for (const city of candidates) {
      if (d3.geoContains(countyFeature, [city.lon, city.lat])) {
        if (!best || city.population > best.population) best = city;
      }
    }
    return best;
  }

  function findRepresentativeCity(countyFeature, stateAbbr) {
    const best = bestCityInCounty(countyFeature, stateAbbr);
    return best ? best.name : null;
  }

  function getCountyCityLabels(stateAbbr, countyFeatures) {
    if (cityLabelCache[stateAbbr]) return cityLabelCache[stateAbbr];
    const labels = [];
    for (const feature of countyFeatures) {
      const best = bestCityInCounty(feature, stateAbbr);
      if (best) labels.push(best);
    }
    cityLabelCache[stateAbbr] = labels;
    return labels;
  }

  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value == null ? "" : String(value);
    return div.innerHTML;
  }

  function showCountyLaborers(fips, feature, stateAbbr) {
    openPanel();

    const info = countyInfo[fips];
    const countyName = escapeHtml(info ? info.name : "");
    const stateAbbrEsc = escapeHtml(info ? info.state : stateAbbr);
    const cityName = findRepresentativeCity(feature, stateAbbr);
    const cityLabel = cityName ? ` (${escapeHtml(cityName)})` : "";
    const header = `<h3>${countyName}${cityLabel}, ${stateAbbrEsc}</h3>`;

    panelContent.innerHTML = `${header}<p>Loading labor groups&hellip;</p>`;

    fetch(`/coverage/api/counties/${fips}/laborers/`)
      .then((response) => response.json())
      .then((data) => {
        if (!data.laborers.length) {
          panelContent.innerHTML = `${header}<p>No labor groups have registered coverage for this county yet.</p>`;
          return;
        }
        const cards = data.laborers
          .map((laborer) => {
            const name = escapeHtml(laborer.display_name);
            const city = escapeHtml(laborer.city);
            const state = escapeHtml(laborer.state);
            const phone = escapeHtml(laborer.phone_number);
            const badge = laborer.is_primary
              ? '<span class="county-slot-badge">BASED HERE</span>'
              : '<span class="county-slot-badge county-slot-badge--muted">ALSO SERVES</span>';
            return `
              <div class="laborer-card">
                <div>${badge}</div>
                <strong>${name}</strong>
                <p>${city ? city + ", " + state : ""}</p>
                <p>${phone}</p>
              </div>
            `;
          })
          .join("");
        panelContent.innerHTML = `${header}${cards}`;
      })
      .catch(() => {
        panelContent.innerHTML = `${header}<p>Couldn't load labor groups for this county. Please try again.</p>`;
      });
  }

  backButton.addEventListener("click", drawNation);

  let debounceTimer = null;

  if (addressInput) {
    addressInput.addEventListener("input", () => {
      clearTimeout(debounceTimer);
      const query = addressInput.value.trim();
      if (query.length < 3) {
        hideSuggestions();
        return;
      }
      debounceTimer = setTimeout(() => fetchSuggestions(query), 350);
    });

    document.addEventListener("click", (event) => {
      if (!addressInput.contains(event.target) && !suggestionsList.contains(event.target)) {
        hideSuggestions();
      }
    });
  }

  function hideSuggestions() {
    suggestionsList.classList.add("hidden");
    suggestionsList.innerHTML = "";
  }

  function fetchSuggestions(query) {
    const url =
      "https://nominatim.openstreetmap.org/search?format=json&addressdetails=0&countrycodes=us&limit=6&q=" +
      encodeURIComponent(query);
    fetch(url)
      .then((response) => response.json())
      .then((results) => renderSuggestions(results))
      .catch(() => hideSuggestions());
  }

  function renderSuggestions(results) {
    if (!results || !results.length) {
      hideSuggestions();
      return;
    }
    suggestionsList.innerHTML = results
      .map((result, index) => `<li class="address-suggestion" data-index="${index}">${escapeHtml(result.display_name)}</li>`)
      .join("");
    suggestionsList.classList.remove("hidden");
    suggestionsList.querySelectorAll(".address-suggestion").forEach((li) => {
      li.addEventListener("click", () => {
        const result = results[Number(li.dataset.index)];
        selectAddress(result);
      });
    });
  }

  function selectAddress(result) {
    hideSuggestions();
    addressInput.value = result.display_name;
    const lat = parseFloat(result.lat);
    const lon = parseFloat(result.lon);
    if (Number.isNaN(lat) || Number.isNaN(lon)) return;
    locateCounty(lat, lon);
  }

  function locateCounty(lat, lon) {
    if (!countiesFC) return;
    const point = [lon, lat];
    const match = countiesFC.features.find((feature) => d3.geoContains(feature, point));
    if (!match) {
      statusEl.textContent = "Couldn't match that address to a county. Try a different search.";
      return;
    }
    const fips = String(match.id).padStart(5, "0");
    const stateFipsStr = fips.slice(0, 2);
    const abbr = STATE_FIPS_TO_ABBR[stateFipsStr];
    if (!abbr) return;

    drawState(abbr, Number(stateFipsStr));

    const el = Array.from(document.querySelectorAll(".region.county")).find(
      (candidate) => candidate.__data__ && String(candidate.__data__.id).padStart(5, "0") === fips
    );
    if (el) {
      regionLayer.selectAll("path.region.county").classed("selected", false);
      d3.select(el).classed("selected", true);
    }
    showCountyLaborers(fips, match, abbr);
  }
})();
