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
  const ABBR_TO_STATE_FIPS = {};
  Object.keys(STATE_FIPS_TO_ABBR).forEach((fips) => {
    ABBR_TO_STATE_FIPS[STATE_FIPS_TO_ABBR[fips]] = fips;
  });

  const FIT_PADDING = 24;

  const mapContainer = document.getElementById("map-container");
  const statusEl = document.getElementById("map-status");
  const slotsContainer = document.getElementById("county-slots");
  const countEl = document.getElementById("service-count");
  const zoomControls = document.getElementById("zoom-controls");
  const zoomInBtn = document.getElementById("zoom-in-btn");
  const zoomOutBtn = document.getElementById("zoom-out-btn");
  const defaultStatus = SELECTED_STATE ? `Click counties in ${SELECTED_STATE} to add or remove them.` : "";

  let selectedCounties = SELECTED_COUNTIES.slice();
  let countiesFC = null;
  let allCities = null;
  let countyInfo = null;
  let zoom = null;
  let svg, regionLayer, cityLayer, path, tooltip;
  const cityLabelCache = {};

  if (mapContainer) {
    svg = d3.select(mapContainer).append("svg");
    regionLayer = svg.append("g").attr("class", "region-layer");
    cityLayer = svg.append("g").attr("class", "city-layer");
    path = d3.geoPath();
    tooltip = document.createElement("div");
    tooltip.className = "map-tooltip hidden";
    mapContainer.appendChild(tooltip);
  }

  function moveTooltip(event) {
    const rect = mapContainer.getBoundingClientRect();
    tooltip.style.left = event.clientX - rect.left + "px";
    tooltip.style.top = event.clientY - rect.top + "px";
  }

  function showCountyTooltip(event, feature, stateAbbr) {
    const fips = String(feature.id).padStart(5, "0");
    const info = countyInfo ? countyInfo[fips] : null;
    const countyName = info ? info.name : "";
    const cityName = findRepresentativeCity(feature, stateAbbr);
    tooltip.textContent = cityName ? `${countyName} (${cityName})` : countyName;
    tooltip.classList.remove("hidden");
    moveTooltip(event);
  }

  function hideTooltip() {
    if (tooltip) tooltip.classList.add("hidden");
  }

  Promise.all([
    d3.json("https://cdn.jsdelivr.net/npm/us-atlas@3/counties-10m.json"),
    d3.json("/static/coverage/data/cities.json"),
    d3.json("/static/coverage/data/counties.json"),
  ])
    .then(([us, cities, counties]) => {
      countiesFC = topojson.feature(us, us.objects.counties);
      allCities = cities;
      countyInfo = {};
      counties.forEach((c) => {
        countyInfo[c.fips] = c;
      });
      renderSlots();
      if (SELECTED_STATE && mapContainer) {
        drawState(SELECTED_STATE);
      }
    })
    .catch(() => {
      if (statusEl) {
        statusEl.textContent = "Sorry, the map couldn't be loaded. Please refresh to try again.";
      }
      renderSlots();
    });

  if (mapContainer) {
    window.addEventListener("resize", () => {
      if (countiesFC && SELECTED_STATE) drawState(SELECTED_STATE);
    });
  }

  function containerSize() {
    const rect = mapContainer.getBoundingClientRect();
    return { width: rect.width || 900, height: rect.height || 550 };
  }

  function findCountyFeature(fips) {
    if (!countiesFC) return null;
    return countiesFC.features.find((f) => String(f.id).padStart(5, "0") === fips);
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

  function renderSlots() {
    const slots = [];
    for (let i = 0; i < MAX_COUNTIES; i++) {
      const county = selectedCounties[i];
      if (county) {
        const feature = findCountyFeature(county.fips);
        const cityName = findRepresentativeCity(feature, county.state);
        const cityPart = cityName ? ` (${escapeHtml(cityName)})` : "";
        const badge = county.is_primary ? '<span class="county-slot-badge">HOME</span>' : "";
        const starBtn = county.is_primary
          ? ""
          : `<button type="button" class="county-slot-star" data-fips="${escapeHtml(county.fips)}" aria-label="Set ${escapeHtml(county.name)} as your home county">&#9733;</button>`;
        slots.push(`
          <div class="county-slot filled${county.is_primary ? " primary" : ""}">
            <span class="county-slot-name">${badge}${escapeHtml(county.name)}${cityPart}, ${escapeHtml(county.state)}</span>
            <div class="county-slot-actions">
              ${starBtn}
              <button type="button" class="county-slot-remove" data-fips="${escapeHtml(county.fips)}" aria-label="Remove ${escapeHtml(county.name)}">&times;</button>
            </div>
          </div>
        `);
      } else {
        slots.push('<div class="county-slot empty">Empty</div>');
      }
    }
    slotsContainer.innerHTML = slots.join("");
    slotsContainer.querySelectorAll(".county-slot-remove").forEach((btn) => {
      btn.addEventListener("click", () => toggleCounty(btn.dataset.fips, null));
    });
    slotsContainer.querySelectorAll(".county-slot-star").forEach((btn) => {
      btn.addEventListener("click", () => setPrimaryCounty(btn.dataset.fips));
    });
  }

  function setPrimaryCounty(fips) {
    fetch(`/coverage/api/service-areas/${fips}/set-primary/`, {
      method: "POST",
      headers: { "X-CSRFToken": CSRF_TOKEN },
    })
      .then((response) => response.json())
      .then((data) => {
        selectedCounties = data.selected_counties;
        renderSlots();
        if (SELECTED_STATE) drawState(SELECTED_STATE);
      })
      .catch(() => {
        if (statusEl) statusEl.textContent = "Couldn't update your home county. Please try again.";
      });
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

  if (zoomInBtn) {
    zoomInBtn.addEventListener("click", () => {
      if (zoom) svg.transition().duration(200).call(zoom.scaleBy, 1.6);
    });
  }
  if (zoomOutBtn) {
    zoomOutBtn.addEventListener("click", () => {
      if (zoom) svg.transition().duration(200).call(zoom.scaleBy, 1 / 1.6);
    });
  }

  function drawState(abbr) {
    disableZoom();
    hideTooltip();
    const stateFipsStr = ABBR_TO_STATE_FIPS[abbr];
    const stateCounties = {
      type: "FeatureCollection",
      features: countiesFC.features.filter(
        (f) => String(f.id).padStart(5, "0").slice(0, 2) === stateFipsStr
      ),
    };

    const size = containerSize();
    svg.attr("viewBox", `0 0 ${size.width} ${size.height}`);
    const projection = d3.geoMercator().fitExtent(
      [
        [FIT_PADDING, FIT_PADDING],
        [size.width - FIT_PADDING, size.height - FIT_PADDING],
      ],
      stateCounties
    );
    path.projection(projection);

    const selectedSet = new Set(selectedCounties.map((c) => c.fips));

    regionLayer
      .selectAll("path.region")
      .data(stateCounties.features, (d) => d.id)
      .join("path")
      .attr(
        "class",
        (d) => "region county" + (selectedSet.has(String(d.id).padStart(5, "0")) ? " selected" : "")
      )
      .attr("d", path)
      .on("click", function (event, d) {
        const fips = String(d.id).padStart(5, "0");
        toggleCounty(fips, this);
      })
      .on("mouseenter", (event, d) => showCountyTooltip(event, d, abbr))
      .on("mousemove", moveTooltip)
      .on("mouseleave", hideTooltip);

    drawCities(getCountyCityLabels(abbr, stateCounties.features), projection);

    enableZoom(size);
  }

  function drawCities(cities, projection) {
    const groups = cityLayer.selectAll("g.city").data(cities, (d) => d.name + d.state);
    groups.exit().remove();
    const entered = groups.enter().append("g").attr("class", "city");
    entered.append("circle").attr("r", 2.5);
    entered.append("text").attr("x", 5).attr("y", 3);
    const merged = entered.merge(groups);
    merged.attr("transform", (d) => {
      const coords = projection([d.lon, d.lat]);
      return coords ? `translate(${coords[0]},${coords[1]})` : "translate(-1000,-1000)";
    });
    merged.select("text").text((d) => d.name);
  }

  function toggleCounty(fips, element) {
    const isSelected = selectedCounties.some((c) => c.fips === fips);
    if (!isSelected && selectedCounties.length >= MAX_COUNTIES) {
      if (statusEl) {
        statusEl.textContent = `You can only select a home county plus up to ${MAX_COUNTIES - 1} more. Remove one to add another.`;
      }
      return;
    }

    fetch(`/coverage/api/service-areas/${fips}/toggle/`, {
      method: "POST",
      headers: { "X-CSRFToken": CSRF_TOKEN },
    })
      .then((response) => response.json().then((data) => ({ ok: response.ok, data })))
      .then(({ ok, data }) => {
        if (!ok) {
          if (statusEl) statusEl.textContent = data.message || "Something went wrong. Please try again.";
          return;
        }
        selectedCounties = data.selected_counties;
        countEl.textContent = data.total_count;

        const dashboardLink = document.getElementById("proceed-dashboard-link");
        if (dashboardLink) dashboardLink.classList.toggle("hidden", data.total_count === 0);

        if (element) {
          d3.select(element).classed("selected", data.status === "added");
        } else if (mapContainer) {
          const el = Array.from(document.querySelectorAll(".region.county")).find(
            (candidate) => candidate.__data__ && String(candidate.__data__.id).padStart(5, "0") === fips
          );
          if (el) d3.select(el).classed("selected", false);
        }

        if (statusEl) statusEl.textContent = defaultStatus;
        renderSlots();
      })
      .catch(() => {
        if (statusEl) statusEl.textContent = "Couldn't save your change. Please try again.";
      });
  }
})();
