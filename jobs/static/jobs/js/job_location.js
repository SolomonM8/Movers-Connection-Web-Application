(function () {
  const form = document.getElementById("job-form");
  const countyInput = document.querySelector('input[name="county"]');
  const readout = document.getElementById("job-location-readout");

  const tabButtons = document.querySelectorAll(".location-tab-btn");
  const tabPanels = document.querySelectorAll(".location-tab-panel");

  const addressInput = document.getElementById("job-address-search");
  const addressSuggestions = document.getElementById("job-address-suggestions");

  const stateSelect1 = document.getElementById("job-state-select-1");
  const countySelect = document.getElementById("job-county-select");

  const stateSelect2 = document.getElementById("job-state-select-2");
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

  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const tab = btn.dataset.tab;
      tabButtons.forEach((b) => b.classList.toggle("active", b === btn));
      tabPanels.forEach((p) => p.classList.toggle("hidden", p.dataset.panel !== tab));
    });
  });

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

  if (INITIAL_COUNTY) {
    setLocation(INITIAL_COUNTY.fips, INITIAL_COUNTY.name, INITIAL_COUNTY.state);
  }

  // ---- Populate state selects ----
  function populateStateSelect(select) {
    if (!select) return;
    (STATES || []).forEach(([abbr, name]) => {
      const option = document.createElement("option");
      option.value = abbr;
      option.textContent = name;
      select.appendChild(option);
    });
  }
  populateStateSelect(stateSelect1);
  populateStateSelect(stateSelect2);

  // ---- Shared county topology + county reference data (lazy-loaded once) ----
  let countyDataPromise = null;
  function loadCountyData() {
    if (countyDataPromise) return countyDataPromise;
    countyDataPromise = Promise.all([
      d3.json("https://cdn.jsdelivr.net/npm/us-atlas@3/counties-10m.json"),
      d3.json("/static/coverage/data/counties.json"),
    ]).then(([us, counties]) => {
      const countiesFC = topojson.feature(us, us.objects.counties);
      const countyByFips = {};
      counties.forEach((c) => {
        countyByFips[c.fips] = c;
      });
      return { countiesFC, countyByFips, countiesList: counties };
    });
    return countyDataPromise;
  }

  function resolveCountyFromPoint(lat, lon) {
    loadCountyData().then(({ countiesFC, countyByFips }) => {
      const point = [lon, lat];
      const match = countiesFC.features.find((feature) => d3.geoContains(feature, point));
      if (!match) {
        showLocationError("Couldn't match that location to a county. Try a different search.");
        return;
      }
      const fips = String(match.id).padStart(5, "0");
      const info = countyByFips[fips];
      if (!info) {
        showLocationError("Couldn't match that location to a county. Try a different search.");
        return;
      }
      setLocation(fips, info.name, info.state);
    });
  }

  // ---- Tab 1: free-form address search ----
  let addressDebounce = null;

  function hideSuggestions(list) {
    list.classList.add("hidden");
    list.innerHTML = "";
  }

  function renderSuggestions(list, results, onSelect) {
    if (!results || !results.length) {
      hideSuggestions(list);
      return;
    }
    list.innerHTML = results
      .map((result, index) => `<li class="address-suggestion" data-index="${index}">${escapeHtml(result.display_name)}</li>`)
      .join("");
    list.classList.remove("hidden");
    list.querySelectorAll(".address-suggestion").forEach((li) => {
      li.addEventListener("click", () => {
        hideSuggestions(list);
        onSelect(results[Number(li.dataset.index)]);
      });
    });
  }

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
            renderSuggestions(addressSuggestions, results, (result) => {
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

  // ---- Tab 2: state -> county dropdown ----
  if (stateSelect1 && countySelect) {
    stateSelect1.addEventListener("change", () => {
      const abbr = stateSelect1.value;
      countySelect.innerHTML = "";
      if (!abbr) {
        const option = document.createElement("option");
        option.value = "";
        option.textContent = "Select a state first…";
        countySelect.appendChild(option);
        countySelect.disabled = true;
        return;
      }
      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = "Loading counties…";
      countySelect.appendChild(placeholder);
      countySelect.disabled = true;

      loadCountyData().then(({ countiesList }) => {
        const inState = countiesList
          .filter((c) => c.state === abbr)
          .sort((a, b) => a.name.localeCompare(b.name));
        countySelect.innerHTML = "";
        const empty = document.createElement("option");
        empty.value = "";
        empty.textContent = "Select a county…";
        countySelect.appendChild(empty);
        inState.forEach((c) => {
          const option = document.createElement("option");
          option.value = c.fips;
          option.textContent = c.name;
          countySelect.appendChild(option);
        });
        countySelect.disabled = false;
      });
    });

    countySelect.addEventListener("change", () => {
      const fips = countySelect.value;
      if (!fips) return;
      loadCountyData().then(({ countyByFips }) => {
        const info = countyByFips[fips];
        if (info) setLocation(fips, info.name, info.state);
      });
    });
  }

  // ---- Tab 3: state -> typed city, resolved via geocoding ----
  let cityDebounce = null;

  if (stateSelect2 && citySearch) {
    stateSelect2.addEventListener("change", () => {
      const abbr = stateSelect2.value;
      citySearch.disabled = !abbr;
      citySearch.value = "";
      citySearch.placeholder = abbr ? "Start typing a city…" : "Select a state, then type a city…";
      hideSuggestions(citySuggestions);
    });

    citySearch.addEventListener("input", () => {
      clearTimeout(cityDebounce);
      const query = citySearch.value.trim();
      const abbr = stateSelect2.value;
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
            renderSuggestions(citySuggestions, results, (result) => {
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
})();
