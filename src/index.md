---
title: Orange County Well Water Levels
toc: false
---
<!-- markdownlint-disable MD013 MD033 -->
# Orange County Well Water Levels

```js
import * as d3 from "npm:d3";
import {feature} from "npm:topojson-client";

const wellsRaw = FileAttachment("data/wells.json").json();
const precipRaw = FileAttachment("data/precip.json").json();
const roads = FileAttachment("data/roads.json").json();
const areawater = FileAttachment("data/areawater.json").json();
const linearwater = FileAttachment("data/linearwater.json").json();

const us = await fetch(import.meta.resolve("npm:us-atlas/counties-10m.json")).then(r => r.json());
const orangeCounty = feature(us, us.objects.counties).features.find(d => d.id === "37135");
```

```js
const M = wellsRaw.months;
const currentYear = wellsRaw.current_year;
const wells = wellsRaw.wells.filter(w => w.latest_year === currentYear);
const sw = wellsRaw.series_by_well;
const cy = wellsRaw.county_by_year;
const yrs = wellsRaw.years;
const minYear = currentYear - 10;                       // show only the last ~decade (e.g. 2016+)
const yearsShown = yrs.filter(y => y >= minYear);

// precip loader emits {error} when unavailable — degrade gracefully but keep the reason.
const precip = precipRaw && !precipRaw.error ? precipRaw : null;

const fetchedAt = new Date(wellsRaw.generated);
const fetchedStr = fetchedAt.toLocaleString("en-US",
  {weekday: "short", year: "numeric", month: "long", day: "numeric", hour: "2-digit", minute: "2-digit", timeZoneName: "short"});

const latest = (() => {
  const row = cy[String(currentYear)] || [];
  for (let i = row.length - 1; i >= 0; i--) if (row[i] != null) return {i, d: row[i]};
  return null;
})();
const mName = latest ? M[latest.i] : "";
const nAbove = wells.filter(w => (w.delta_latest || 0) > 0.5).length;

function trendSinceJan(row) {
  const vs = row.map((v, i) => v != null ? {i, v} : null).filter(Boolean);
  return vs.length < 2 ? null : Math.round((vs.at(-1).v - vs[0].v) * 100) / 100;
}
const widened = trendSinceJan(cy[String(currentYear)] || []);
const peakRank = (() => {
  if (!latest) return null;
  const prior = yrs.filter(y => y < currentYear).map(y => cy[String(y)]?.[latest.i]).filter(v => v != null);
  if (!prior.length) return null;
  return {w: prior.filter(p => latest.d > p).length, t: prior.length};
})();
```

```js
const PLACES = [
  {name: "Hillsborough", lon: -79.100, lat: 36.075},
  {name: "Chapel Hill", lon: -79.056, lat: 35.913},
  {name: "Carrboro", lon: -79.075, lat: 35.910},
];


function seriesDataold(wellId) {
  if (wellId === "all") {
    return yearsShown.flatMap(y => (cy[String(y)] || []).map((v, m) => v != null ? {y, m, v} : null).filter(Boolean));
  }
  const s = sw[wellId] || {};
  return yearsShown.flatMap(y => (s[String(y)] || []).map((v, m) => v != null ? {y, m, v} : null).filter(Boolean));
}

```

```js
const wellState = Object.assign(document.createElement("input"), {type: "hidden", value: "all"});
const selectedWellId = view(wellState);
```

```js
const selectedWell = selectedWellId === "all" ? null : wells.find(w => w.id == selectedWellId);
const wellId = selectedWellId;

function seriesData(wellId) {
  if (wellId === "all") {
    return yearsShown.flatMap(y => (cy[String(y)] || []).map((v, m) => v != null ? {y, m, v} : null).filter(Boolean));
  }
  const s = sw[wellId] || {};
  return yearsShown.flatMap(y => (s[String(y)] || []).map((v, m) => v != null ? {y, m, v} : null).filter(Boolean));
}

function latestValue(wellId) {
  if (wellId === "all") return latest;
  const w = wells.find(w => w.id == wellId);
  if (!w || w.delta_latest == null || w.latest_month_idx == null) return null;
  return {i: w.latest_month_idx, d: w.delta_latest};
}

const mapDomain = {...orangeCounty};

// anchor dependencies so this block re-runs when they change
wells; selectedWell; mapDomain; areawater; linearwater; roads; PLACES; orangeCounty;

function mapChart(width) {
  const mapped = wells.filter(w => w.lat != null && w.lon != null);
  const selected = selectedWell;
  const plot = Plot.plot({
    width, height: 520,
    projection: {type: "mercator", domain: mapDomain},
    marks: [
      Plot.geo(orangeCounty, {fill: "#c8dac6", stroke: "none"}),
      Plot.geo(areawater, {fill: "#ffffff", stroke: "#ffffff", strokeWidth: 0.5}),
      Plot.geo(linearwater, {stroke: "#ffffff", strokeWidth: 0.5}),
      Plot.geo(roads, {
        stroke: "#a0a0a0",
        strokeWidth: d => d.properties.name?.startsWith("I-") ? 1.8 : d.properties.name?.startsWith("US") ? 1.4 : 0.9,
        strokeOpacity: d => d.properties.name?.startsWith("I-") ? 0.65 : d.properties.name?.startsWith("US") ? 0.65 : 0.45
      }),
      Plot.dot(PLACES, {x: "lon", y: "lat", r: 2.5, fill: "var(--theme-foreground-muted)"}),
      Plot.text(PLACES.filter(p => p.name !== "Carrboro"), {x: "lon", y: "lat", text: "name", fontSize: 11, fontWeight: 600, fill: "var(--theme-foreground-muted)", dy: -9}),
      Plot.text(PLACES.filter(p => p.name === "Carrboro"), {x: "lon", y: "lat", text: "name", fontSize: 11, fontWeight: 600, fill: "var(--theme-foreground-muted)", dy: 14}),
      Plot.dot(mapped, {
        x: "lon", y: "lat", r: 5,
        fill: "#3b82c4", fillOpacity: selected ? 0.2 : 0.7,
        stroke: "none", style: "cursor: pointer;",
      }),
      Plot.dot(mapped, Plot.pointer({
        x: "lon", y: "lat", r: 8, fill: "#3b82c4", stroke: "white", strokeWidth: 2
      })),
      Plot.text(mapped, Plot.pointer({
        x: "lon", y: "lat", text: "name", fontSize: 13, fontWeight: 700, fill: "#3b82c4", dy: -12, lineAnchor: "bottom"
      })),
      ...(selected ? [
        Plot.dot([selected], {x: "lon", y: "lat", r: 8, fill: "#3b82c4", stroke: "white", strokeWidth: 2}),
        Plot.text([selected], {x: "lon", y: "lat", text: "name", fontSize: 13, fontWeight: 700, fill: "#3b82c4", dy: -12, lineAnchor: "bottom"}),
      ] : [])
    ]
  });
  let hovered = null;
  plot.addEventListener("input", () => {
    const val = plot.value;
    hovered = val ? (Array.isArray(val) ? val[0] : val) : null;
  });
  plot.addEventListener("click", () => {
    if (hovered && hovered.id != null) {
      wellState.value = String(hovered.id);
      wellState.dispatchEvent(new Event("input", {bubbles: true}));
    }
  });
  const container = document.createElement("div");
  container.style.position = "relative";
  container.append(plot);
  if (selected) {
    const btn = document.createElement("button");
    btn.textContent = "Select all";
    btn.style.cssText = "position:absolute;bottom:8px;right:8px;z-index:10;padding:4px 12px;background:#3b82c4;color:white;border:none;border-radius:4px;cursor:pointer;font-size:12px;line-height:1.4;";
    btn.addEventListener("click", (e) => { e.stopPropagation(); wellState.value = "all"; wellState.dispatchEvent(new Event("input", {bubbles: true})); });
    container.append(btn);
  }
  return container;
}
```

```js
function verbiage(wellId) {
  if (wellId === "all") {
    return {title: "All wells", desc: `All ${wells.length} active wells in the Orange County network, in service since 2016.`};
  }
  const w = wells.find(x => String(x.id) === wellId);
  if (!w) return {title: "", desc: ""};
  const label = w.depth_class === "shallow"
    ? "Shallow well (regolith) — responds within days to rainfall"
    : "Deep well (fractured bedrock) — multi-month to multi-year aquifer trends";
  const lv = latestValue(wellId);
  if (!lv) return {title: w.name, desc: `${label}. No current-year reading.`};
  const mn = M[lv.i];
  const p = (sw[wellId] || {})[String(currentYear - 1)];
  let trend = "no prior-year comparison";
  if (p && lv.i < p.length && p[lv.i] != null) {
    const diff = lv.d - p[lv.i];
    trend = diff > 0 ? `worse than last ${mn} by ${diff.toFixed(1)} ft` : `better than last ${mn} by ${Math.abs(diff).toFixed(1)} ft`;
  }
  return {title: w.name, desc: `${label}. This ${mn}'s deficit of ${lv.d.toFixed(1)} ft is ${trend}.`};
}

const info = verbiage(wellId);
```

```js
const precipSummary = precip ? (() => {
  const cyData = precip.precip_by_year[String(currentYear)] || [];
  const monthsWithData = cyData.map((v, m) => v != null ? m : null).filter(d => d != null);
  if (monthsWithData.length === 0) return null;
  const now = new Date();
  const monthFraction = now.getDate() / new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
  const lastM = monthsWithData[monthsWithData.length - 1];
  const isPartial = lastM === now.getMonth();
  const completeMonths = isPartial ? monthsWithData.slice(0, -1) : monthsWithData;
  const cyTotal = completeMonths.reduce((s, m) => s + cyData[m], 0) + (isPartial ? cyData[lastM] : 0);
  const histTotal = completeMonths.reduce((s, m) => s + (precip.precip_hist_avg[m] || 0), 0) + (isPartial ? (precip.precip_hist_avg[lastM] || 0) * monthFraction : 0);
  const diff = cyTotal - histTotal;
  return {total: cyTotal.toFixed(1), hist: histTotal.toFixed(1), diff: Math.abs(diff).toFixed(1), dir: diff > 0 ? "above" : "below", through: M[lastM]};
})() : null;
```

<div class="grid grid-cols-2">
  <div class="card">
    <h3>Summary of ${selectedWell ? `${selectedWell.name} (${selectedWell.depth ?? "?"} ft · since ${selectedWell.record_start ?? "?"})` : "entire county"}</h3>
    <p>As of ${mName} ${currentYear}, well depths in the county are ${Math.abs(latest.d).toFixed(1)} ft <strong>${latest.d > 0 ? "above" : "below"}</strong> the long-term monthly average <strong>${latest.d > 0 ? "drier" : "wetter"}</strong> than normal (higher is drier, lower is wetter).</p>
    <p>${nAbove} of ${wells.length} wells are above their average depth.</p>
    ${html`<p>The total precipitation is ${precipSummary.total}″ for ${currentYear} thus far. This is ${precipSummary.diff}″ <strong>${precipSummary.dir}</strong> the ${precipSummary.hist}″ average for this point in the year.</p>`}
    <p>${info.desc}</p>
    ${selectedWell ? "" : html`<p style="color:var(--theme-foreground-muted);font-style:italic;">Click a well on the map to see individual statistics.</p>`}
  </div>
  <div class="card">
    ${resize((width) => mapChart(width))}
  </div>
</div>

### Well Depths

In the graph below we can see how the depth of water measured in wells vary from the average (above average is high is dry).


<div class="grid grid-cols-1">
  <div class="card">
    ${resize((width) => wellDeficitChart(width, wellId, countyStddev))}
  </div>
</div>

```js
// anchor dependencies so this block re-runs when they change
seriesData; currentYear; M; minYear; wellId; wellsRaw;

const countyStddev = wellsRaw.county_stddev;

const _yearColorScale = d3.scaleLinear()
  .domain([minYear, currentYear - 1])
  .range(["#eaeaea", "#777777"]);

const yearColor = (y) => y === currentYear ? "currentColor" : _yearColorScale(y);

const STDDEV_FILL = "#777777";
const STDDEV_OPACITY = 0.10;

const plotLayout = (width) => ({
  width, height: 340, marginLeft: 48,
  x: {domain: d3.range(12), tickFormat: i => M[i], label: null, grid: false},
});

function timeSeriesMarks(data, formatVal, interactiveOptions) {
  const years = [...new Set(data.map(d => d.y))].sort((a, b) => a - b);
  const marks = [
    Plot.ruleY([0], {stroke: "var(--theme-foreground-faint)"}),
    ...years.flatMap(y => {
      const yd = data.filter(d => d.y === y);
      return [
        Plot.line(yd, {x: "m", y: "v", stroke: () => yearColor(y), strokeWidth: () => y === currentYear ? 2.5 : 1, curve: "catmull-rom"}),
        Plot.dot(yd, {x: "m", y: "v", r: 1, fill: () => yearColor(y)}),
      ];
    }),
  ];
  const explicitStats = typeof interactiveOptions === "object" && interactiveOptions.avg ? interactiveOptions : null;
  const stats = explicitStats || (() => {
    const byMonth = {};
    for (const d of data) {
      if (d.y === currentYear) continue;
      if (!byMonth[d.m]) byMonth[d.m] = [];
      byMonth[d.m].push(d.v);
    }
    const s = {};
    for (const [m, vals] of Object.entries(byMonth)) {
      if (vals.length >= 2) {
        const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
        const sqDiff = vals.reduce((sum, v) => sum + (v - mean) ** 2, 0);
        s[m] = {mean, stdv: Math.sqrt(sqDiff / (vals.length - 1))};
      }
    }
    return s;
  })();
  const unit = explicitStats ? "″" : "ft";
  marks.push(
    Plot.dot(data, Plot.pointerX({x: "m", y: "v", r: 7, fill: "currentColor", stroke: "white"})),
    Plot.tip(data, Plot.pointerX({
      x: "m",
      y: "v",
      channels: {
        year: {value: (d) => `${d.y}`, label: "Year"},
        value: {value: (d) => formatVal(d), label: explicitStats ? "Precipitation" : "Level"},
        normal_range: {value: (d) => {
          if (explicitStats) {
            const avg = explicitStats.avg[d.m];
            const stdv = explicitStats.stdv[d.m];
            if (avg == null || stdv == null) return null;
            return `${(avg - stdv).toFixed(2)}${unit} – ${(avg + stdv).toFixed(2)}${unit}`;
          }
          const s = stats[d.m];
          if (!s) return null;
          return `${(s.mean - s.stdv).toFixed(2)}${unit} – ${(s.mean + s.stdv).toFixed(2)}${unit}`;
        }, label: "±1 std"}
      },
      format: {x: false, y: false}
    }))
  );
  return marks;
}

function wellDeficitChart(width, wellId, countyStddev) {
  const pts = seriesData(wellId);
  const prev = pts.filter(d => d.y !== currentYear);

  const yExtent = d3.extent(pts, d => d.v);
  const yPad = (yExtent[1] - yExtent[0]) * 0.05 || 0.5;
  const yDomain = [yExtent[0] - yPad, yExtent[1] + yPad];

  const marks = [
    // dry/wet background regions
    Plot.areaY(d3.range(12), {x: d => d, y1: 0, y2: yDomain[1], fill: "#b8860b", fillOpacity: 0.04}),
    Plot.areaY(d3.range(12), {x: d => d, y1: yDomain[0], y2: 0, fill: "#4682b4", fillOpacity: 0.04}),
  ];

  // pooled std dev band across all past years (excludes current year)
  if (countyStddev) {
    const pastByMonth = {};
    for (const d of prev) {
      if (!pastByMonth[d.m]) pastByMonth[d.m] = [];
      pastByMonth[d.m].push(d.v);
    }
    const bandData = [];
    for (const m in pastByMonth) {
      const vals = pastByMonth[m];
      if (vals.length >= 2) {
        const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
        const sqDiff = vals.reduce((sum, v) => sum + (v - mean) ** 2, 0);
        const stdv = Math.sqrt(sqDiff / (vals.length - 1));
        bandData.push({m: +m, low: mean - stdv, high: mean + stdv});
      }
    }
    marks.push(Plot.areaY(bandData, {
      x: "m", y1: "low", y2: "high",
      fill: STDDEV_FILL, fillOpacity: STDDEV_OPACITY, curve: "catmull-rom",
    }));
  }

  marks.push(...timeSeriesMarks(pts, d => `${Math.abs(d.v).toFixed(2)} ft ${d.v > 0 ? "above" : "below"} average`));

  const plot = Plot.plot({
    ...plotLayout(width),
    y: {domain: yDomain, grid: true, label: "Deficit (ft) — higher = drier", tickFormat: d => (d > 0 ? "+" : "") + d},
    marks
  });
  return plot;
}
```

## Precipitation

```js
function precipChart(width) {
  if (!precip) {
    return html`<p style="color:var(--theme-foreground-muted);padding:1rem;">Precipitation unavailable</p>`;
  }
  const precipYrs = yearsShown.filter(y => precip.precip_by_year[String(y)]);
  const pts = precipYrs.flatMap(y =>
    (precip.precip_by_year[String(y)] || []).map((v, m) => v != null ? {y, m, v} : null).filter(Boolean)
  );

  const marks = [
    Plot.ruleY([0], {stroke: "var(--theme-foreground-faint)"}),
    // ±1 std dev band around the monthly normal
    ...(precip.precip_hist_stddev ? [Plot.areaY(
      d3.range(12).map(m => {
        const avg = precip.precip_hist_avg[m];
        const stdv = precip.precip_hist_stddev[m];
        return (avg != null && stdv != null) ? {m, low: avg - stdv, high: avg + stdv} : null;
      }).filter(Boolean),
      {x: "m", y1: "low", y2: "high", fill: STDDEV_FILL, fillOpacity: STDDEV_OPACITY, curve: "catmull-rom"}
    )] : []),
  ];

  marks.push(...timeSeriesMarks(pts, d => `${d.v.toFixed(2)}″`, {avg: precip.precip_hist_avg, stdv: precip.precip_hist_stddev}));

  const plot = Plot.plot({
    ...plotLayout(width),
    y: {grid: true, label: "Precipitation (in)"},
    marks
  });
  return plot;
}
```

<div class="grid grid-cols-1">
  <div class="card">${resize((width) => precipChart(width))}</div>
</div>

## Data Sources

* **Groundwater levels** — NC DEQ Division of Water Resources, [ncwater.org](https://www.ncwater.org) daily depth-to-water records for the ${wells.length} active Orange County monitoring wells.
* **Precipitation** — NOAA Climate Data Online (GHCND).
* **Geographic data** — US Census Bureau, TIGER/Line (Orange County, NC).
