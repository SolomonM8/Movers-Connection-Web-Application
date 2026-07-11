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
  const searchHint = document.getElementById("search-hint");
  const searchHintClose = document.getElementById("search-hint-close");

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
  const stateClipPath = svg.append("defs").append("clipPath").attr("id", "state-clip");
  const stateClipShape = stateClipPath.append("path");
  const regionLayer = svg.append("g").attr("class", "region-layer");
  const roadLayer = svg.append("g").attr("class", "road-layer");
  const roadClipGroup = roadLayer.append("g").attr("class", "road-clip");
  const stateLabelLayer = svg.append("g").attr("class", "state-label-layer");
  const cityLayer = svg.append("g").attr("class", "city-layer");
  const path = d3.geoPath();

  const tooltip = document.createElement("div");
  tooltip.className = "map-tooltip hidden";
  mapContainer.appendChild(tooltip);

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
    tooltip.classList.add("hidden");
  }

  let statesFC, countiesFC, allCities, countyInfo, interstatesFC;
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
    d3.json("/static/coverage/data/interstates.json"),
  ])
    .then(([us, cities, counties, interstates]) => {
      statesFC = topojson.feature(us, us.objects.states);
      countiesFC = topojson.feature(us, us.objects.counties);
      allCities = cities;
      countyInfo = {};
      counties.forEach((c) => {
        countyInfo[c.fips] = c;
      });
      interstatesFC = interstates;
      interstatesFC.features.forEach((f) => {
        f.bbox = d3.geoBounds(f);
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
    roadLayer.attr("transform", null);
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
        roadLayer.attr("transform", event.transform);
        cityLayer.attr("transform", event.transform);
        cityLayer.selectAll("circle").attr("r", 2.5 / event.transform.k);
        cityLayer.selectAll("text").style("font-size", 10 / event.transform.k + "px");
      });
    svg.call(zoom);
    zoomControls.classList.remove("hidden");
  }

  function drawRoads(features) {
    roadClipGroup
      .selectAll("path.interstate")
      .data(features || [])
      .join("path")
      .attr("class", "interstate")
      .attr("d", path);
  }

  const STATE_BBOX_PAD = 1.5;

  function roadsNearState(stateFeature) {
    if (!interstatesFC) return [];
    const bounds = d3.geoBounds(stateFeature);
    const minLon = bounds[0][0] - STATE_BBOX_PAD;
    const minLat = bounds[0][1] - STATE_BBOX_PAD;
    const maxLon = bounds[1][0] + STATE_BBOX_PAD;
    const maxLat = bounds[1][1] + STATE_BBOX_PAD;
    return interstatesFC.features.filter((f) => {
      const b = f.bbox;
      return !(b[1][0] < minLon || b[0][0] > maxLon || b[1][1] < minLat || b[0][1] > maxLat);
    });
  }

  function drawStateLabels(features) {
    stateLabelLayer
      .selectAll("text.state-abbr-label")
      .data(features, (d) => d.id)
      .join("text")
      .attr("class", "state-abbr-label")
      .attr("transform", (d) => {
        const c = path.centroid(d);
        return `translate(${c[0]},${c[1]})`;
      })
      .text((d) => STATE_FIPS_TO_ABBR[String(d.id).padStart(2, "0")] || "");
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
    hideTooltip();
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

    roadClipGroup.attr("clip-path", null);
    roadClipGroup.selectAll("path.interstate").remove();
    drawStateLabels(statesFC.features);
    drawCities(allCities.filter((c) => c.major), projection);
  }

  function drawState(abbr, stateFipsId) {
    closePanel();
    hideTooltip();
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
      })
      .on("mouseenter", (event, d) => showCountyTooltip(event, d, abbr))
      .on("mousemove", moveTooltip)
      .on("mouseleave", hideTooltip);

    stateLabelLayer.selectAll("text.state-abbr-label").remove();

    const stateFeature = statesFC.features.find((f) => String(f.id).padStart(2, "0") === stateFipsStr);
    if (stateFeature) {
      stateClipShape.attr("d", path(stateFeature));
      roadClipGroup.attr("clip-path", "url(#state-clip)");
      drawRoads(roadsNearState(stateFeature));
    } else {
      roadClipGroup.attr("clip-path", null);
      drawRoads([]);
    }
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
            const avatar = laborer.avatar_url
              ? `<img class="avatar-circle avatar-circle--lg" src="${escapeHtml(laborer.avatar_url)}" alt="">`
              : `<span class="avatar-circle avatar-circle--lg" style="background: ${escapeHtml(laborer.avatar_color)}">${escapeHtml(laborer.avatar_initial)}</span>`;
            const actions = IS_DRIVER
              ? `
                <div class="job-actions">
                  ${
                    laborer.is_friend
                      ? '<span class="county-slot-badge">FRIEND</span>'
                      : `<button type="button" class="inline-friend-btn" data-add-friend="${laborer.laborer_id}">+ Add Friend</button>`
                  }
                  <a class="btn-primary btn-inline" href="/jobs/invite/${laborer.laborer_id}/">Invite to Job &rarr;</a>
                </div>
              `
              : "";
            return `
              <div class="laborer-card">
                <div class="laborer-card-top">
                  ${avatar}
                  <div>
                    <div>${badge}</div>
                    <strong>${name}</strong>
                  </div>
                </div>
                <p>${city ? city + ", " + state : ""}</p>
                <p>${phone}</p>
                ${actions}
              </div>
            `;
          })
          .join("");
        panelContent.innerHTML = `${header}${cards}`;
        if (IS_DRIVER) bindAddFriendButtons();
      })
      .catch(() => {
        panelContent.innerHTML = `${header}<p>Couldn't load labor groups for this county. Please try again.</p>`;
      });
  }

  function bindAddFriendButtons() {
    const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
    panelContent.querySelectorAll("[data-add-friend]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const laborerId = btn.dataset.addFriend;
        fetch(`/accounts/friends/add/laborer/${laborerId}/`, {
          method: "POST",
          headers: csrfInput ? { "X-CSRFToken": csrfInput.value } : {},
        })
          .then(() => {
            btn.outerHTML = '<span class="county-slot-badge">FRIEND</span>';
          })
          .catch(() => {});
      });
    });
  }

  backButton.addEventListener("click", drawNation);

  let debounceTimer = null;

  if (addressInput) {
    addressInput.addEventListener("input", () => {
      dismissSearchHint();
      clearTimeout(debounceTimer);
      const query = addressInput.value.trim();
      if (query.length < 3) {
        hideSuggestions();
        return;
      }
      debounceTimer = setTimeout(() => fetchSuggestions(query), 350);
    });

    addressInput.addEventListener("focus", dismissSearchHint);

    document.addEventListener("click", (event) => {
      if (!addressInput.contains(event.target) && !suggestionsList.contains(event.target)) {
        hideSuggestions();
      }
    });
  }

  const SEARCH_HINT_KEY = "mc_search_hint_seen";

  function dismissSearchHint() {
    if (!searchHint) return;
    searchHint.classList.add("hidden");
    try {
      window.localStorage.setItem(SEARCH_HINT_KEY, "1");
    } catch (e) {
      /* localStorage unavailable; hint will just reappear next visit */
    }
  }

  if (searchHint) {
    let alreadySeen = false;
    try {
      alreadySeen = window.localStorage.getItem(SEARCH_HINT_KEY) === "1";
    } catch (e) {
      alreadySeen = false;
    }
    if (!alreadySeen) {
      searchHint.classList.remove("hidden");
    }
  }

  if (searchHintClose) {
    searchHintClose.addEventListener("click", dismissSearchHint);
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
