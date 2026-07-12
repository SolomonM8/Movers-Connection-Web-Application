(function () {
  const form = document.getElementById("job-form");
  const countyInput = document.querySelector('input[name="county"]');
  const readout = document.getElementById("job-location-readout");

  const tabButtons = document.querySelectorAll(".location-tab-btn");
  const tabPanels = document.querySelectorAll(".location-tab-panel");

  const addressInput = document.getElementById("job-address-search");
  const addressSuggestions = document.getElementById("job-address-suggestions");

  const stateSearch1 = document.getElementById("job-state-search-1");
  const stateSuggestions1 = document.getElementById("job-state-suggestions-1");
  const countySelect = document.getElementById("job-county-select");

  const stateSearch2 = document.getElementById("job-state-search-2");
  const stateSuggestions2 = document.getElementById("job-state-suggestions-2");
  const citySearch = document.getElementById("job-city-search");
  const citySuggestions = document.getElementById("job-city-suggestions");

  if (!form || !countyInput) return;

  const STATE_ABBR_TO_NAME = {};
  (STATES || []).forEach(([abbr, name]) => {
    STATE_ABBR_TO_NAME[abbr] = name;
  });

  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value == null ? "" : String(value);
    return div.innerHTML;
  }

  function hideSuggestions(list) {
    list.classList.add("hidden");
    list.innerHTML = "";
  }

  function renderSuggestions(list, results, labelFor, onSelect) {
    if (!results || !results.length) {
      hideSuggestions(list);
      return;
    }
    list.innerHTML = results
      .map((result, index) => `<li class="address-suggestion" data-index="${index}">${escapeHtml(labelFor(result))}</li>`)
      .join("");
    list.classList.remove("hidden");
    list.querySelectorAll(".address-suggestion").forEach((li) => {
      li.addEventListener("click", () => {
        hideSuggestions(list);
        onSelect(results[Number(li.dataset.index)]);
      });
    });
  }

  // ---- Lazy-loaded geocoding libraries + data (only fetched once actually needed) ----
  // The "Select State & County" tab never needs any of this: it only needs the
  // small counties.json list. Only the address tab and the "type a city" tab need
  // the full county topology + d3/topojson, so those are deferred until first use
  // instead of being loaded unconditionally on every job-form page view.
  const loadedScripts = {};
  function loadScript(src) {
    if (loadedScripts[src]) return loadedScripts[src];
    loadedScripts[src] = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = src;
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
    return loadedScripts[src];
  }

  function ensureGeoLibs() {
    return Promise.all([
      loadScript("https://d3js.org/d3.v7.min.js"),
      loadScript("https://unpkg.com/topojson-client@3"),
    ]);
  }

  let countiesListPromise = null;
  function loadCountiesList() {
    if (!countiesListPromise) {
      countiesListPromise = fetch("/static/coverage/data/counties.json")
        .then((response) => response.json())
        .then((counties) => {
          const countyByFips = {};
          counties.forEach((c) => {
            countyByFips[c.fips] = c;
          });
          return { countiesList: counties, countyByFips };
        });
    }
    return countiesListPromise;
  }

  let topologyPromise = null;
  function loadCountyTopology() {
    if (!topologyPromise) {
      topologyPromise = ensureGeoLibs().then(() =>
        fetch("https://cdn.jsdelivr.net/npm/us-atlas@3/counties-10m.json")
          .then((response) => response.json())
          .then((us) => topojson.feature(us, us.objects.counties))
      );
    }
    return topologyPromise;
  }

  function resolveCountyFromPoint(lat, lon) {
    Promise.all([loadCountyTopology(), loadCountiesList()]).then(([countiesFC, { countyByFips }]) => {
      const point = [lon, lat];
      const match = countiesFC.features.find((feature) => d3.geoContains(feature, point));
      const fips = match ? String(match.id).padStart(5, "0") : null;
      const info = fips ? countyByFips[fips] : null;
      if (!info) {
        showLocationError("Couldn't match that location to a county. Try a different search.");
        return;
      }
      setLocation(fips, info.name, info.state);
    });
  }

  // ---- Shared location state ----
  function setLocation(fips, name, state) {
    countyInput.value = fips;
    readout.textContent = `This job will be posted for ${name}, ${state}.`;
    readout.classList.remove("hidden", "is-error");
  }

  function showLocationError(message) {
    readout.textContent = message;
    readout.classList.remove("hidden");
    readout.classList.add("is-error");
  }

  function clearLocation() {
    countyInput.value = "";
    readout.textContent = "";
    readout.classList.add("hidden");
    readout.classList.remove("is-error");
  }

  if (INITIAL_COUNTY) {
    setLocation(INITIAL_COUNTY.fips, INITIAL_COUNTY.name, INITIAL_COUNTY.state);
  }

  // ---- Tabs: switching sections discards whatever was picked in the old one ----
  function resetAddressPanel() {
    if (!addressInput) return;
    addressInput.value = "";
    hideSuggestions(addressSuggestions);
  }

  function resetStateCountyPanel() {
    if (!stateSearch1) return;
    stateSearch1.value = "";
    stateSearch1.dataset.value = "";
    hideSuggestions(stateSuggestions1);
    countySelect.innerHTML = '<option value="">Select a state first…</option>';
    countySelect.disabled = true;
  }

  function resetStateCityPanel() {
    if (!stateSearch2) return;
    stateSearch2.value = "";
    stateSearch2.dataset.value = "";
    hideSuggestions(stateSuggestions2);
    citySearch.value = "";
    citySearch.disabled = true;
    citySearch.placeholder = "Select a state, then type a city…";
    hideSuggestions(citySuggestions);
  }

  function resetAllPanels() {
    resetAddressPanel();
    resetStateCountyPanel();
    resetStateCityPanel();
    clearLocation();
  }

  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.classList.contains("active")) return;
      tabButtons.forEach((b) => b.classList.toggle("active", b === btn));
      tabPanels.forEach((p) => p.classList.toggle("hidden", p.dataset.panel !== btn.dataset.tab));
      resetAllPanels();
    });
  });

  // ---- State autocomplete (local filter, no network — instant) ----
  function setupStateAutocomplete(input, suggestions, onSelect) {
    if (!input) return;
    input.addEventListener("input", () => {
      input.dataset.value = "";
      const query = input.value.trim().toLowerCase();
      if (!query) {
        hideSuggestions(suggestions);
        return;
      }
      const matches = (STATES || [])
        .filter(([abbr, name]) => name.toLowerCase().includes(query) || abbr.toLowerCase() === query)
        .slice(0, 8);
      renderSuggestions(suggestions, matches, ([, name]) => name, ([abbr, name]) => {
        input.value = name;
        input.dataset.value = abbr;
        onSelect(abbr, name);
      });
    });
    document.addEventListener("click", (event) => {
      if (!input.contains(event.target) && !suggestions.contains(event.target)) {
        hideSuggestions(suggestions);
      }
    });
  }

  // ---- Tab 1: free-form address search ----
  let addressDebounce = null;

  if (addressInput) {
    addressInput.addEventListener("input", () => {
      clearTimeout(addressDebounce);
      const query = addressInput.value.trim();
      if (query.length < 3) {
        hideSuggestions(addressSuggestions);
        return;
      }
      addressDebounce = setTimeout(() => {
        const url =
          "https://nominatim.openstreetmap.org/search?format=json&addressdetails=0&countrycodes=us&limit=6&q=" +
          encodeURIComponent(query);
        fetch(url)
          .then((response) => response.json())
          .then((results) =>
            renderSuggestions(addressSuggestions, results, (r) => r.display_name, (result) => {
              addressInput.value = result.display_name;
              const lat = parseFloat(result.lat);
              const lon = parseFloat(result.lon);
              if (Number.isNaN(lat) || Number.isNaN(lon)) return;
              resolveCountyFromPoint(lat, lon);
            })
          )
          .catch(() => hideSuggestions(addressSuggestions));
      }, 350);
    });

    document.addEventListener("click", (event) => {
      if (!addressInput.contains(event.target) && !addressSuggestions.contains(event.target)) {
        hideSuggestions(addressSuggestions);
      }
    });
  }

  // ---- Tab 2: state -> county dropdown (no d3/topojson/topology needed at all) ----
  setupStateAutocomplete(stateSearch1, stateSuggestions1, (abbr) => {
    countySelect.innerHTML = '<option value="">Loading counties…</option>';
    countySelect.disabled = true;
    loadCountiesList().then(({ countiesList }) => {
      const inState = countiesList
        .filter((c) => c.state === abbr)
        .sort((a, b) => a.name.localeCompare(b.name));
      countySelect.innerHTML = '<option value="">Select a county…</option>';
      inState.forEach((c) => {
        const option = document.createElement("option");
        option.value = c.fips;
        option.textContent = c.name;
        countySelect.appendChild(option);
      });
      countySelect.disabled = false;
    });
  });

  if (countySelect) {
    countySelect.addEventListener("change", () => {
      const fips = countySelect.value;
      if (!fips) return;
      loadCountiesList().then(({ countyByFips }) => {
        const info = countyByFips[fips];
        if (info) setLocation(fips, info.name, info.state);
      });
    });
  }

  // ---- Tab 3: state -> typed city, resolved via geocoding ----
  let cityDebounce = null;

  setupStateAutocomplete(stateSearch2, stateSuggestions2, (abbr) => {
    citySearch.disabled = false;
    citySearch.value = "";
    citySearch.placeholder = "Start typing a city…";
    hideSuggestions(citySuggestions);
  });

  if (citySearch) {
    citySearch.addEventListener("input", () => {
      clearTimeout(cityDebounce);
      const query = citySearch.value.trim();
      const abbr = stateSearch2.dataset.value;
      if (!abbr || query.length < 2) {
        hideSuggestions(citySuggestions);
        return;
      }
      cityDebounce = setTimeout(() => {
        const stateName = STATE_ABBR_TO_NAME[abbr] || abbr;
        const url =
          "https://nominatim.openstreetmap.org/search?format=json&addressdetails=0&limit=6&country=us&city=" +
          encodeURIComponent(query) +
          "&state=" +
          encodeURIComponent(stateName);
        fetch(url)
          .then((response) => response.json())
          .then((results) =>
            renderSuggestions(citySuggestions, results, (r) => r.display_name, (result) => {
              citySearch.value = result.display_name;
              const lat = parseFloat(result.lat);
              const lon = parseFloat(result.lon);
              if (Number.isNaN(lat) || Number.isNaN(lon)) return;
              resolveCountyFromPoint(lat, lon);
            })
          )
          .catch(() => hideSuggestions(citySuggestions));
      }, 350);
    });

    document.addEventListener("click", (event) => {
      if (!citySearch.contains(event.target) && !citySuggestions.contains(event.target)) {
        hideSuggestions(citySuggestions);
      }
    });
  }

  // ---- Submit guard ----
  form.addEventListener("submit", (event) => {
    if (!countyInput.value) {
      event.preventDefault();
      showLocationError("Please choose a location for this job before posting.");
      readout.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  });

  // ---- Pricing model field toggle ----
  const pricingSelect = document.getElementById("id_pricing_model");
  const flatField = document.querySelector('[data-pricing-field="flat_rate"]');
  const hourlyField = document.querySelector('[data-pricing-field="hourly"]');
  if (pricingSelect && flatField && hourlyField) {
    function updatePricingVisibility() {
      const isFlat = pricingSelect.value === "flat_rate";
      flatField.classList.toggle("hidden", !isFlat);
      hourlyField.classList.toggle("hidden", isFlat);
    }
    pricingSelect.addEventListener("change", updatePricingVisibility);
    updatePricingVisibility();
  }

  // ---- Packing-skill checkbox: only relevant when job type is Load ----
  const jobTypeSelect = document.getElementById("id_job_type");
  const packingField = document.querySelector('[data-job-type-field="packing"]');
  const packingCheckbox = document.getElementById("id_needs_packing_skill");
  if (jobTypeSelect && packingField) {
    function updatePackingVisibility() {
      const isLoad = jobTypeSelect.value === "load";
      packingField.classList.toggle("hidden", !isLoad);
      if (!isLoad && packingCheckbox) packingCheckbox.checked = false;
    }
    jobTypeSelect.addEventListener("change", updatePackingVisibility);
    updatePackingVisibility();
  }
})();
