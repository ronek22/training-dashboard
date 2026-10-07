<template>
  <div class="mountains-page motion-page">
    <header class="page-head motion-section">
      <div>
        <span class="page-eyebrow">Trail coverage</span>
        <h1 class="page-title">Mountains</h1>
        <p class="page-sub">Marked trails you've already walked, matched from your Strava hikes, and what's still left.</p>
      </div>
      <div class="head-actions">
        <div class="region-tabs" role="tablist" aria-label="View">
          <button type="button" role="tab" :aria-selected="view === 'coverage'" :class="{ active: view === 'coverage' }" @click="setView('coverage')">Coverage</button>
          <button type="button" role="tab" :aria-selected="view === 'routes'" :class="{ active: view === 'routes' }" @click="setView('routes')">Route ideas</button>
          <button type="button" role="tab" :aria-selected="view === 'plan'" :class="{ active: view === 'plan' }" @click="setView('plan')">Planner</button>
        </div>
        <div class="region-tabs" role="tablist" aria-label="Mountain range">
          <button v-for="r in regions" :key="r.key" type="button" role="tab" :aria-selected="r.key === regionKey"
            :class="{ active: r.key === regionKey }" @click="selectRegion(r.key)">
            <span>{{ r.name }}</span><small v-if="r.imported_at">{{ r.done_pct }}%</small>
          </button>
        </div>
        <button type="button" class="action" :disabled="busy" @click="syncHikes">
          {{ busy === 'sync' ? 'Syncing hikes…' : 'Sync hikes' }}
        </button>
      </div>
    </header>
    <p v-if="message" class="flash" :class="{ error: messageIsError }" role="status">{{ message }}</p>

    <!-- Full screen moves the layout to <body>: the page's entrance animation leaves a transform
         that would otherwise trap position: fixed inside the content column. -->
    <Teleport to="body" :disabled="!fullscreen">
    <div ref="layoutEl" class="mountains-layout" :class="{ 'is-fullscreen': fullscreen, 'side-open': fullscreen && (sidePeek || sidePinned) }">
      <section class="map-card motion-section" aria-label="Trail map">
        <div ref="mapEl" class="trail-map mtn-map" :class="{ 'is-planning': view === 'plan' }"></div>

        <div v-if="data && sections.length" class="map-toolbar">
          <template v-if="view === 'coverage'">
            <div class="seg" role="group" aria-label="Show trails">
              <button v-for="f in FILTERS" :key="f.value" type="button" :class="{ on: filter === f.value }" @click="filter = f.value">{{ f.label }}</button>
            </div>
            <button type="button" class="toggle" :class="{ on: colourRemaining }" :aria-pressed="colourRemaining" @click="colourRemaining = !colourRemaining">Colour remaining</button>
          </template>
          <button type="button" class="toggle" :class="{ on: showPlaces }" :aria-pressed="showPlaces" @click="showPlaces = !showPlaces">Summits &amp; places</button>
          <button type="button" class="toggle" :class="{ on: showLabels }" :aria-pressed="showLabels" @click="showLabels = !showLabels">Labels</button>
          <button type="button" class="toggle" :class="{ on: showTracks }" :aria-pressed="showTracks" @click="showTracks = !showTracks">My GPS tracks</button>
          <div v-if="data.mapy_api_key" class="seg" role="group" aria-label="Base map">
            <button type="button" :class="{ on: base === 'relief' }" @click="base = 'relief'">Relief</button>
            <button type="button" :class="{ on: base === 'mapy' }" @click="base = 'mapy'">Mapy.com</button>
          </div>
          <button type="button" class="toggle fullscreen-toggle" :aria-pressed="fullscreen" :title="fullscreen ? 'Exit full screen (Esc)' : 'Full screen map'" @click="toggleFullscreen">
            <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path :d="fullscreen ? 'M6 2v4H2M10 2v4h4M6 14v-4H2M10 14v-4h4' : 'M2 6V2h4M14 6V2h-4M2 10v4h4M14 10v4h-4'" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>
            {{ fullscreen ? 'Exit full screen' : 'Full screen' }}
          </button>
        </div>

        <div v-if="data && sections.length && view !== 'coverage'" class="map-legend" :class="{ 'above-profile': panelRoute && routeProfile.length > 1 && !profileCollapsed, 'above-panel': panelRoute && (routeProfile.length < 2 || profileCollapsed) }" aria-hidden="true">
          <span><svg width="30" height="10"><line x1="3" y1="5" x2="27" y2="5" :stroke="legend.casing" stroke-width="10" stroke-linecap="round"/><line x1="3" y1="5" x2="27" y2="5" :stroke="ROUTE_COLOURS[theme].new" stroke-width="6" stroke-linecap="round"/></svg>New trail on the route</span>
          <span><svg width="30" height="10"><line x1="3" y1="5" x2="27" y2="5" :stroke="legend.casing" stroke-width="8" stroke-linecap="round"/><line x1="3" y1="5" x2="27" y2="5" :stroke="ROUTE_COLOURS[theme].known" stroke-width="4" stroke-linecap="round"/></svg>Already walked</span>
          <span v-if="view === 'plan'"><svg width="30" height="10"><line x1="3" y1="5" x2="27" y2="5" :stroke="ROUTE_COLOURS[theme].off" stroke-width="3.5" stroke-dasharray="5 5" stroke-linecap="round"/></svg>Off marked trails</span>
          <span><i class="route-pin legend-pin">S</i>Start <i class="route-pin legend-pin is-end">F</i>Finish</span>
        </div>
        <div v-else-if="data && sections.length" class="map-legend" aria-hidden="true">
          <span><svg width="30" height="10"><line x1="3" y1="5" x2="27" y2="5" :stroke="legend.casing" stroke-width="9" stroke-linecap="round"/><line x1="3" y1="5" x2="27" y2="5" :stroke="legend.done" stroke-width="5" stroke-linecap="round"/></svg>Done</span>
          <span><svg width="30" height="14"><line x1="3" y1="7" x2="27" y2="7" :stroke="legend.casing" stroke-width="12" stroke-linecap="round"/><line x1="3" y1="5" x2="27" y2="5" :stroke="legend.done" stroke-width="4"/><line x1="3" y1="9" x2="27" y2="9" :stroke="legend.shared" stroke-width="4"/></svg>Done, shared trail</span>
          <span><svg width="30" height="10"><line x1="3" y1="5" x2="27" y2="5" :stroke="legend.done" stroke-width="3.5" stroke-dasharray="8 6"/></svg>Partly</span>
          <span><svg width="30" height="10"><line x1="3" y1="5" x2="27" y2="5" :stroke="legend.remaining" stroke-width="2.5" stroke-dasharray="3 6" stroke-linecap="round"/></svg>Still to do</span>
          <span v-if="showPlaces && places.length"><i class="legend-icon" v-html="placeIcon('peak', true)"></i>Reached <i class="legend-icon" v-html="placeIcon('peak', false)"></i>Not yet</span>
          <span v-if="showTracks"><svg width="30" height="10"><line x1="3" y1="5" x2="27" y2="5" :stroke="legend.track" stroke-width="2"/></svg>Your tracks</span>
        </div>

        <div v-if="panelRoute" class="route-profile" :class="{ 'no-chart': routeProfile.length < 2 || profileCollapsed }" aria-label="Selected route">
          <div class="route-profile-head">
            <strong>{{ panelRoute.title }}</strong>
            <span v-if="profileHover">km {{ profileHover.km.toFixed(1) }} · {{ Math.round(profileHover.alt) }} m</span>
            <span v-else>{{ formatKm(panelRoute.distance_m) }} km<template v-if="panelRoute.ascent_m != null"> · ↑ {{ panelRoute.ascent_m }} m · ↓ {{ panelRoute.descent_m }} m</template><template v-if="routeStats"> · highest {{ Math.round(routeStats.highest.alt) }} m</template></span>
            <button v-if="routeProfile.length > 1" type="button" class="gpx-button" :aria-expanded="!profileCollapsed" :title="profileCollapsed ? 'Show the elevation profile' : 'Hide the elevation profile to see more map'" @click="profileCollapsed = !profileCollapsed">{{ profileCollapsed ? 'Show profile' : 'Hide profile' }}</button>
            <button v-if="view === 'routes'" type="button" class="gpx-button" title="Open this route in the planner to change it" @click="editInPlanner(selectedRoute)">Edit in planner</button>
            <button type="button" class="gpx-button" title="Download as GPX for Mapy.com, OsmAnd, Garmin Connect or Strava" @click="downloadGpx">
              <svg width="13" height="13" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2v8m0 0 3.5-3.5M8 10 4.5 6.5M3 13h10" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>GPX
            </button>
          </div>
          <ElevationProfile v-if="routeProfile.length > 1 && !profileCollapsed" v-model:hover="profileHover" :profile="routeProfile" :marks="routeMarks" :height="128" label="Elevation profile of the route" />
        </div>

        <div v-if="loading" class="map-state">Loading trails…</div>
        <div v-else-if="loadError" class="map-state" role="alert">{{ loadError }}</div>
        <div v-else-if="data && !sections.length" class="map-state">
          <div class="state-box">
            <strong>{{ data.region.name }} trails aren't loaded yet</strong>
            <p>Marked trails come from OpenStreetMap. Loading takes under a minute.</p>
            <button type="button" class="action" :disabled="busy" @click="importTrails">{{ busy === 'import' ? 'Loading trails…' : 'Load trails' }}</button>
          </div>
        </div>
      </section>

      <button v-if="fullscreen && data && sections.length" type="button" class="side-handle" :class="{ pinned: sidePinned }"
        :aria-expanded="sidePeek || sidePinned" :title="sidePinned ? 'Unpin the panel' : 'Hover to show the panel, click to keep it open'"
        @mouseenter="peekSide(true)" @mouseleave="peekSide(false)" @click="sidePinned = !sidePinned">
        <svg width="12" height="12" viewBox="0 0 16 16" aria-hidden="true"><path :d="sidePeek || sidePinned ? 'M6 3l5 5-5 5' : 'M10 3L5 8l5 5'" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
        <span>{{ SIDE_LABELS[view] }}</span>
      </button>
      <aside v-if="data && sections.length && view === 'routes'" class="side routes-side" @mouseenter="peekSide(true)" @mouseleave="peekSide(false)">
        <section class="card routes-controls">
          <div class="park-chips" role="group" aria-label="Park">
            <button v-for="p in data.parks" :key="p.key" type="button" :class="{ on: routePark === p.key }" :title="p.name" @click="selectPark(p.key)">
              {{ p.label || p.key }} <small v-if="p.country">{{ p.country }}</small>
            </button>
          </div>
          <div class="length-tabs" role="group" aria-label="Length">
            <button v-for="l in LENGTHS" :key="l.value" type="button" :class="{ on: routeLength === l.value }" @click="routeLength = l.value">
              <span>{{ l.label }}</span><small>{{ l.hint }}</small>
            </button>
          </div>
          <label v-if="hasAround" class="around-switch">
            <input v-model="includeAround" type="checkbox">
            <span>Count trails around the park as new<small>Routes start from bus stops and car parks either way.</small></span>
          </label>
        </section>

        <p v-if="routesLoading" class="fine routes-state">Planning routes…</p>
        <p v-else-if="routesError" class="fine routes-state" role="alert">{{ routesError }}</p>
        <p v-else-if="!routeList.length" class="fine routes-state">No route ideas here: nothing missing fits in {{ LENGTHS.find((l) => l.value === routeLength).hint }} from a bus stop or car park. Try a longer day.</p>
        <button v-for="r in routeList" :key="r.key" type="button" class="card route-card" :class="{ on: selectedRouteKey === r.key }" @click="selectRoute(r)">
          <span class="route-title">{{ r.title }}</span>
          <span class="route-sub">{{ r.mode === 'loop' ? 'Loop' : 'One way' }} · start {{ r.start.kind === 'bus' ? 'bus stop' : 'car park' }} {{ r.start.name }}<template v-if="r.mode !== 'loop'">, finish at bus stop {{ r.end.name }}</template></span>
          <span class="route-stats">
            <span><b>{{ formatKm(r.distance_m) }}</b> km</span>
            <span v-if="r.ascent_m != null">↑ <b>{{ r.ascent_m }}</b> m</span>
            <span>~<b>{{ formatHours(r.hours) }}</b></span>
          </span>
          <span class="route-new"><b>+{{ formatKm(r.new_m) }} km</b> new trail · {{ newShare(r) }}% of the route</span>
          <span v-if="routeHighlights(r).length" class="route-places">
            <span v-for="p in routeHighlights(r)" :key="p.name" :class="{ reached: p.reached }"><i v-html="placeIcon(p.kind, p.reached)"></i>{{ displayName(p.name) }}<small v-if="p.ele"> {{ p.ele }}</small></span>
          </span>
        </button>
        <p v-if="routeList.length" class="fine source">Times use 4 km/h, 300 m/h up and 500 m/h down, without breaks. Heights from OpenTopoData (EU-DEM 25 m){{ routesHaveHeights ? '' : ' are not loaded yet, so times ignore climbing' }}.</p>
      </aside>

      <aside v-else-if="data && sections.length && view === 'plan'" class="side planner-side" @mouseenter="peekSide(true)" @mouseleave="peekSide(false)">
        <section class="card planner-card">
          <div class="card-title"><span>Plan a route</span><small v-if="planLoading">Updating…</small></div>
          <p v-if="!planPoints.length" class="fine planner-hint">Click the map where you want to start, then add points along the way. The route follows marked trails; a point clicked away from them is joined with a dashed line.</p>
          <template v-else>
            <div class="planner-stats">
              <div><span>Distance</span><strong>{{ plan ? formatKm(plan.distance_m) : '–' }}<small> km</small></strong></div>
              <div><span>Time</span><strong>{{ plan && planPoints.length > 1 ? `~${formatHours(plan.hours)}` : '–' }}</strong></div>
              <div><span>Ascent</span><strong>{{ plan?.ascent_m ?? '–' }}<small> m</small></strong></div>
              <div><span>Descent</span><strong>{{ plan?.descent_m ?? '–' }}<small> m</small></strong></div>
              <div><span>Highest</span><strong>{{ plan?.max_ele ?? '–' }}<small> m</small></strong></div>
              <div><span>New trail</span><strong class="is-new">{{ plan ? formatKm(plan.new_m) : '–' }}<small> km</small></strong></div>
            </div>
            <p v-if="plan?.off_trail_m" class="fine planner-warn">{{ formatKm(plan.off_trail_m) }} km off marked trails (dashed), timed as flat walking.</p>
            <p v-if="planError" class="fine planner-warn" role="alert">{{ planError }}</p>
            <div class="planner-actions">
              <button type="button" :disabled="!planHistory.length" title="Undo (Ctrl/Cmd+Z)" @click="undoPlan">Undo</button>
              <button type="button" :disabled="planPoints.length < 2 || planIsLoop" @click="closeLoop">Back to start</button>
              <button type="button" :disabled="planPoints.length < 2" @click="reversePlan">Reverse</button>
              <button type="button" class="danger" @click="clearPlan">Clear</button>
            </div>
            <div v-if="planPoints.length > 1 && !routeForm" class="planner-save">
              <template v-if="editingRoute">
                <p class="fine planner-editing">
                  Saved as <b>{{ editingRoute.name }}</b><template v-if="editingRoute.collection"> in {{ editingRoute.collection }}</template>
                  <em v-if="planDirty">&nbsp;· unsaved changes</em>
                </p>
                <button type="button" class="primary" :disabled="!planDirty || savingRoute" @click="saveChanges">{{ savingRoute ? 'Saving…' : 'Save changes' }}</button>
                <button type="button" :disabled="savingRoute" @click="openSaveForm">Save as new</button>
              </template>
              <button v-else type="button" class="primary" @click="openSaveForm">Save route</button>
            </div>
            <SavedRouteForm v-if="routeForm?.mode === 'new'" :initial-name="routeForm.name" :initial-collection="routeForm.collection"
              :collections="savedCollections" submit-label="Save route" :busy="savingRoute" @submit="saveNewRoute" @cancel="routeForm = null" />
            <p v-if="savedError" class="fine planner-warn" role="alert">{{ savedError }}</p>
          </template>
        </section>
        <section v-if="planPoints.length" class="card planner-points">
          <div class="card-title"><span>Points</span><small>{{ planPoints.length }}</small></div>
          <p class="fine planner-hint">Drag a point on the map to move it, right-click it to remove it, click the line to add one in between, or click the start to finish there.</p>
          <ol>
            <li v-for="(w, i) in planWaypoints" :key="i">
              <i class="route-pin" :class="{ 'is-end': i === planWaypoints.length - 1 && i > 0, 'is-off': !w.on_trail }">{{ pointBadge(i) }}</i>
              <span class="planner-point-name">{{ pointName(w, i) }}</span>
              <button type="button" :aria-label="`Remove point ${i + 1}`" @click="removePoint(i)">×</button>
            </li>
          </ol>
        </section>
        <section class="card saved-routes">
          <div class="card-title"><span>Saved routes</span><small>{{ savedRoutes.length || '' }}</small></div>
          <p v-if="savedLoading && !savedRoutes.length" class="fine">Loading…</p>
          <p v-else-if="!savedRoutes.length" class="fine planner-hint">Routes you save land here, grouped into collections like "Summer 2026" or "With kids", ready to open, change or export again.</p>
          <div v-for="group in savedGroups" :key="group.collection" class="saved-group">
            <h4>{{ group.label }} <small>{{ group.routes.length }}</small></h4>
            <ul>
              <li v-for="r in group.routes" :key="r.id" :class="{ on: editingRoute?.id === r.id }">
                <template v-if="routeForm?.mode === 'edit' && routeForm.id === r.id">
                  <SavedRouteForm :initial-name="r.name" :initial-collection="r.collection" :collections="savedCollections"
                    submit-label="Save" :busy="savingRoute" @submit="renameRoute(r, $event)" @cancel="routeForm = null" />
                </template>
                <template v-else>
                  <button type="button" class="saved-open" :title="`Open ${r.name} in the planner`" @click="openSavedRoute(r)">
                    <span class="saved-name">{{ r.name }}</span>
                    <span class="saved-meta">
                      {{ formatKm(r.distance_m) }} km · ~{{ formatHours(r.hours) }}<template v-if="r.ascent_m != null"> · ↑ {{ r.ascent_m }} m</template>
                      <b v-if="r.new_m">&nbsp;· +{{ formatKm(r.new_m) }} km new</b><i v-else-if="r.new_m === 0">&nbsp;· all walked</i>
                    </span>
                  </button>
                  <div class="saved-tools">
                    <template v-if="confirmDelete === r.id">
                      <button type="button" class="danger" :disabled="savingRoute" @click="removeSavedRoute(r)">Delete</button>
                      <button type="button" @click="confirmDelete = null">Keep</button>
                    </template>
                    <template v-else>
                      <button type="button" :aria-label="`Rename or move ${r.name}`" title="Rename or move to another collection" @click="routeForm = { mode: 'edit', id: r.id }">
                        <svg width="13" height="13" viewBox="0 0 16 16" aria-hidden="true"><path d="M3 13h2.5L13 5.5 10.5 3 3 10.5zM9.5 4l2.5 2.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>
                      </button>
                      <button type="button" :aria-label="`Delete ${r.name}`" title="Delete" @click="confirmDelete = r.id">
                        <svg width="13" height="13" viewBox="0 0 16 16" aria-hidden="true"><path d="M3 4.5h10M6.5 4.5V3h3v1.5M4.5 4.5l.7 8.5h5.6l.7-8.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
                      </button>
                    </template>
                  </div>
                </template>
              </li>
            </ul>
          </div>
        </section>
      </aside>

      <aside v-else-if="data && sections.length" class="side" @mouseenter="peekSide(true)" @mouseleave="peekSide(false)">
        <section class="card progress-card">
          <div class="park-chips" role="group" aria-label="Park">
            <button type="button" :class="{ on: park === 'all' }" @click="selectPark('all')">Whole range</button>
            <button v-for="p in data.parks" :key="p.key" type="button" :class="{ on: park === p.key }" :title="p.name" @click="selectPark(p.key)">
              {{ p.label || p.key }} <small v-if="p.country">{{ p.country }}</small>
            </button>
          </div>
          <div class="progress-main">
            <strong class="pct">{{ summary.pct }}<span>%</span></strong>
            <span class="kms"><b>{{ formatKm(summary.doneM) }}</b> of {{ formatKm(summary.totalM) }} km</span>
          </div>
          <div class="bar"><i :style="{ width: `${summary.pct}%` }"></i></div>
          <p class="fine">{{ summary.doneSections }} of {{ summary.sections }} trail sections done<span v-if="summary.partialSections"> · {{ summary.partialSections }} partly walked</span></p>
          <label v-if="hasAround" class="around-switch">
            <input v-model="includeAround" type="checkbox">
            <span>Include trails around the park<small>Within 8 km of the boundary, e.g. Szklarska Poręba or Zakopane. Always on the map.</small></span>
          </label>
        </section>

        <section v-if="placeKinds.length" class="card places-card">
          <h2 class="card-title">Summits &amp; places</h2>
          <div class="kind-tabs" role="tablist" aria-label="Kind of place">
            <button v-for="k in placeKinds" :key="k.kind" type="button" role="tab" :aria-selected="placeKind === k.kind" :class="{ on: placeKind === k.kind }" @click="placeKind = k.kind">
              <span>{{ k.label }}</span><small>{{ placeSummary.counts[k.kind].reached }}/{{ placeSummary.counts[k.kind].total }}</small>
            </button>
          </div>
          <p class="places-head"><b>{{ activeKindCount.reached }}</b> of {{ activeKindCount.total }} {{ activeKindNoun }} reached</p>
          <div class="bar thin"><i :style="{ width: `${activeKindCount.total ? (activeKindCount.reached / activeKindCount.total) * 100 : 0}%` }"></i></div>
          <div class="place-filters" role="group" aria-label="Show places">
            <button v-for="f in PLACE_FILTERS" :key="f.value" type="button" :class="{ on: placeShow === f.value }" @click="placeShow = f.value">{{ f.label }}</button>
          </div>
          <p v-if="!placeSummary.list.length" class="fine">{{ placeShow === 'todo' ? `Every ${activeKindNoun.replace(/e?s$/, '')} here is reached.` : `No ${activeKindNoun} reached yet.` }}</p>
          <div v-else class="list places">
            <button v-for="p in placeSummary.list" :key="p.id" type="button" :class="{ on: activePlace === p.id, reached: isReached(p) }" @click="focusPlace(p)">
              <i class="place-icon" v-html="placeIcon(p.kind, isReached(p))"></i>
              <span class="grow">{{ p.name }}</span>
              <span v-if="p.ele" class="num ele">{{ p.ele }} m</span>
              <span class="num when">{{ isReached(p) ? p.first_visited_on.slice(0, 4) : '—' }}</span>
            </button>
          </div>
        </section>

        <section class="card">
          <h2 class="card-title">By trail colour</h2>
          <div v-for="row in summary.byColour" :key="row.colour" class="colour-row">
            <div class="row-line">
              <span class="colour-name"><i :style="{ background: colourOf(row.colour) }"></i>{{ COLOUR_LABELS[row.colour] }}</span>
              <span class="num">{{ formatKm(row.doneM) }} / {{ formatKm(row.totalM) }} km · <b>{{ row.pct }}%</b></span>
            </div>
            <div class="bar thin"><i :style="{ width: `${row.pct}%`, background: colourOf(row.colour) }"></i></div>
          </div>
        </section>

        <section v-if="summary.byYear.length" class="card">
          <h2 class="card-title">New trail by year</h2>
          <div class="years">
            <div v-for="row in summary.byYear" :key="row.year" class="year" :title="`${formatKm(row.metres)} km of new trail`">
              <span class="year-km num">{{ formatKm(row.metres) }}</span>
              <i :style="{ height: `${Math.max(6, (row.metres / maxYear) * 64)}px` }"></i>
              <span class="year-label">{{ row.year.slice(2) === row.year ? row.year : `’${row.year.slice(2)}` }}</span>
            </div>
          </div>
        </section>

        <section v-if="summary.longestTodo.length" class="card">
          <h2 class="card-title">Longest sections still to do</h2>
          <div class="list">
            <button v-for="s in summary.longestTodo" :key="s.id" type="button" @click="focusSection(s)">
              <span class="dots"><i v-for="c in s.colours" :key="c" :style="{ background: colourOf(c) }"></i></span>
              <span class="grow">{{ sectionTitle(s) }}</span>
              <span class="num">{{ formatKm(s.length_m) }} km</span>
            </button>
          </div>
        </section>

        <section class="card">
          <h2 class="card-title">Hikes <small>{{ tracks.length }}</small></h2>
          <p v-if="!tracks.length" class="fine">No hikes here yet. Use <b>Sync hikes</b> to pull your mountain activities from Strava.</p>
          <div v-else class="list hikes">
            <button v-for="t in tracks" :key="t.id" type="button" :class="{ on: activeTrack === t.id }" @click="focusTrack(t)">
              <span class="date num">{{ shortDate(t.date) }}</span>
              <span class="grow">{{ t.name || 'Hike' }}</span>
              <span v-if="newKmByTrack[t.id]" class="new num" title="Trail walked for the first time">+{{ formatKm(newKmByTrack[t.id]) }} km</span>
            </button>
          </div>
        </section>

        <p class="fine source">
          Trails © OpenStreetMap contributors<span v-if="data.imported_at"> · loaded {{ shortDate(data.imported_at.slice(0, 10)) }}</span> ·
          <button type="button" class="link" :disabled="busy" @click="importTrails">{{ busy === 'import' ? 'reloading…' : 'reload' }}</button>
        </p>
      </aside>
    </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import '../trails/map.css'
import { reliefLayers } from '../trails/baseMap.js'
import { useApi } from '../stores/api'
import { MountainLabels } from '../trails/labelLayer.js'
import { displayName } from '../trails/labels.mjs'
import { LENGTHS, formatHours, gpxFileName, newShare, routeGpx, routeHighlights, routeSegments } from '../trails/routes.mjs'
import { placesOnProfile, profileFromTrack, profileStats } from '../trails/hike.mjs'
import ElevationProfile from '../components/trails/ElevationProfile.vue'
import { groupSavedRoutes, isLoop, legAt, planGpx, planTitle, samePoints } from '../trails/planner.mjs'
import SavedRouteForm from '../components/trails/SavedRouteForm.vue'
import { resolveTheme } from '../utils/theme'
import {
  COLOUR_LABELS, PLACE_KINDS, boundsOf, formatKm, inPark, isReached, offsetPoints, orientCoords, placeIconSvg, placeInPark,
  sectionLayers, sectionTitle,
  summarize, summarizePlaces, trailColour, visibleSection,
} from '../trails/coverage.mjs'

const FILTERS = [{ value: 'all', label: 'All' }, { value: 'done', label: 'Done' }, { value: 'todo', label: 'To do' }]
const PLACE_FILTERS = [{ value: 'all', label: 'All' }, { value: 'reached', label: 'Reached' }, { value: 'todo', label: 'Not yet' }]
// Below this zoom only summits are drawn, so the range overview stays readable.
const PLACE_DETAIL_ZOOM = 12.5
const TRACK_COLOUR = { dark: '#b79cff', light: '#7c3aed' }

// A polyline drawn a fixed number of pixels beside its path, re-offset at every zoom,
// so the colours of a shared trail run side by side.
const OffsetPolyline = L.Polyline.extend({
  _projectLatlngs(latlngs, result, projectedBounds) {
    L.Polyline.prototype._projectLatlngs.call(this, latlngs, result, projectedBounds)
    if (this.options.offset && latlngs[0] instanceof L.LatLng) {
      result[result.length - 1] = offsetPoints(result[result.length - 1], this.options.offset).map((p) => L.point(p.x, p.y))
    }
  },
})

const api = useApi()
const route = useRoute()
const router = useRouter()

const regions = ref([])
const data = ref(null)
const loading = ref(true)
const loadError = ref('')
const busy = ref('')
const message = ref('')
const messageIsError = ref(false)
const theme = ref(resolveTheme())

const filter = ref('all')
const park = ref('all')
const colourRemaining = ref(false)
const showTracks = ref(false)
const base = ref('relief')
const activeTrack = ref(null)
const showPlaces = ref(true)
const showLabels = ref(true)
const AROUND_KEY = 'mountains.includeAround'
const includeAround = ref((() => { try { return localStorage.getItem(AROUND_KEY) === '1' } catch { return false } })())
watch(includeAround, (value) => { try { localStorage.setItem(AROUND_KEY, value ? '1' : '0') } catch { /* storage unavailable */ } })
const placeKind = ref('peak')
const placeShow = ref('all')
const activePlace = ref(null)

const regionKey = computed(() => route.params.region || 'tatras')
const VIEWS = ['coverage', 'routes', 'plan']
const view = computed(() => (VIEWS.includes(route.query.view) ? route.query.view : 'coverage'))
const ROUTE_COLOURS = { dark: { new: '#4ade80', known: '#e6ebf2', off: '#f59e0b' }, light: { new: '#16a34a', known: '#334155', off: '#d97706' } }
const ROUTE_LENGTH_KEY = 'mountains.routeLength'
const routeLength = ref((() => { try { return localStorage.getItem(ROUTE_LENGTH_KEY) || 'day' } catch { return 'day' } })())
watch(routeLength, (value) => { try { localStorage.setItem(ROUTE_LENGTH_KEY, value) } catch { /* storage unavailable */ } })
const routeList = ref([])
const routesLoading = ref(false)
const routesError = ref('')
const routesHaveHeights = ref(true)
const selectedRouteKey = ref(null)
const sections = computed(() => data.value?.sections || [])
const sectionsById = computed(() => Object.fromEntries(sections.value.map((s) => [s.id, s])))
// Route ideas are per park; "Whole range" falls back to the first park (TPN, KPN).
const routePark = computed(() => (park.value !== 'all' ? park.value : data.value?.parks?.[0]?.key))
const selectedRoute = computed(() => routeList.value.find((r) => r.key === selectedRouteKey.value) || null)
// ---------- planner state ----------
const planPoints = ref([])        // [[lat, lon]] as clicked (the backend snaps them to trails)
const planHistory = ref([])       // earlier versions of planPoints, for undo
const plan = ref(null)
const planLoading = ref(false)
const planError = ref('')
const planIsLoop = computed(() => isLoop(planPoints.value))
// Snapped waypoints once the backend has answered for the current points, else the raw clicks.
const planWaypoints = computed(() => (plan.value && plan.value.waypoints.length === planPoints.value.length
  ? plan.value.waypoints
  : planPoints.value.map(([lat, lon]) => ({ lat, lon, on_trail: true, name: null }))))

// ---------- saved routes ----------
const savedRoutes = ref([])
const savedCollections = ref([])
const savedLoading = ref(false)
const savedError = ref('')
const savingRoute = ref(false)
const editingRoute = ref(null)   // the saved route open in the planner, if any
const routeForm = ref(null)      // { mode: 'new', name, collection } or { mode: 'edit', id }
const confirmDelete = ref(null)
const savedGroups = computed(() => groupSavedRoutes(savedRoutes.value))
const planDirty = computed(() => Boolean(editingRoute.value) && !samePoints(planPoints.value, editingRoute.value.points))

// The route under the profile panel: the selected idea, or the planned route.
const panelRoute = computed(() => {
  if (view.value === 'routes') return selectedRoute.value
  // While a change is being planned the previous answer stays up, so nothing flickers.
  if (view.value === 'plan' && plan.value && planPoints.value.length > 1 && plan.value.waypoints.length > 1) {
    return { ...plan.value, title: editingRoute.value?.name || planTitle(plan.value) }
  }
  return null
})
const profileHover = ref(null)
const PROFILE_KEY = 'mountains.profileCollapsed'
const profileCollapsed = ref((() => { try { return localStorage.getItem(PROFILE_KEY) === '1' } catch { return false } })())
watch(profileCollapsed, (value) => { try { localStorage.setItem(PROFILE_KEY, value ? '1' : '0') } catch { /* storage unavailable */ } })
const routeProfile = computed(() => (panelRoute.value?.track ? profileFromTrack(panelRoute.value.track) : []))
const routeStats = computed(() => profileStats(routeProfile.value))
// Summits, passes and huts on the profile; ones not reached yet stand out.
const routeMarks = computed(() => placesOnProfile(routeProfile.value, (panelRoute.value?.places || []).filter((p) => p.kind !== 'cave' && p.lat != null), 120)
  .map((p) => ({ name: displayName(p.name), km: p.km, alt: p.alt, highlight: !p.reached, labelled: p.kind !== 'hut' })))
const tracks = computed(() => data.value?.tracks || [])
const places = computed(() => data.value?.pois || [])
const placeSummary = computed(() => summarizePlaces(places.value, { park: park.value, kind: placeKind.value, show: placeShow.value, includeAround: includeAround.value }))
const placeKinds = computed(() => PLACE_KINDS.filter((k) => placeSummary.value.counts[k.kind].total))
const activeKindCount = computed(() => placeSummary.value.counts[placeKind.value] || { total: 0, reached: 0 })
const activeKindNoun = computed(() => {
  const nouns = PLACE_KINDS.find((k) => k.kind === placeKind.value).noun
  return activeKindCount.value.total === 1 ? nouns[0] : nouns[1]
})
const placeIcon = (kind, reached) => placeIconSvg(kind, reached, theme.value)
const hasAround = computed(() => sections.value.some((s) => s.around))
const summary = computed(() => summarize(sections.value, { park: park.value, includeAround: includeAround.value }))
const maxYear = computed(() => Math.max(1, ...summary.value.byYear.map((r) => r.metres)))
const colourOf = (colour) => trailColour(colour, theme.value)
const legend = computed(() => ({
  done: colourOf('red'),
  shared: colourOf('blue'),
  casing: theme.value === 'dark' ? '#0b0d11' : '#ffffff',
  remaining: theme.value === 'dark' ? 'rgba(214,222,236,.62)' : 'rgba(40,52,74,.58)',
  track: TRACK_COLOUR[theme.value],
}))
const trackById = computed(() => Object.fromEntries(tracks.value.map((t) => [t.id, t])))
// Trail walked for the first time on each hike: done sections where the hike is the earliest walker.
const newKmByTrack = computed(() => {
  const totals = {}
  for (const s of sections.value) {
    if (s.around && !includeAround.value) continue
    if (s.status === 'done' && s.walked_by.length) totals[s.walked_by[0]] = (totals[s.walked_by[0]] || 0) + s.length_m
  }
  return totals
})

const shortDate = (value) => value
  ? new Date(`${value}T12:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
  : ''
const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))

// ---------- data ----------
async function loadRegions() {
  try { regions.value = (await api.getTrailRegions()).data.regions } catch { /* tabs fall back to the current region */ }
}

async function loadRegion() {
  loading.value = true
  loadError.value = ''
  activeTrack.value = null
  activePlace.value = null
  try {
    data.value = (await api.getTrailRegion(regionKey.value)).data
    park.value = savedPark(regionKey.value, data.value.parks)
    if (!summarizePlaces(data.value.pois || []).counts[placeKind.value]?.total) placeKind.value = 'peak'
  } catch {
    data.value = null
    loadError.value = 'Trails could not be loaded. Check that the backend is running and try again.'
  } finally {
    loading.value = false
  }
  await nextTick()
  renderMap(true)
  if (view.value === 'plan') loadSavedRoutes()
}

function flash(text, isError = false) {
  message.value = text
  messageIsError.value = isError
  clearTimeout(flash.timer)
  flash.timer = setTimeout(() => { message.value = '' }, 8000)
}

const errorText = (error, fallback) => error?.response?.data?.detail || fallback

async function syncHikes() {
  busy.value = 'sync'
  try {
    const result = (await api.syncTrailHikes()).data
    const added = result.added === 1 ? '1 new mountain activity' : `${result.added} new mountain activities`
    const parts = [result.added ? `Added ${added}.` : 'No new mountain activities on Strava.']
    if (result.history_added) parts.push(`${result.history_added} older ${result.history_added === 1 ? 'hike is' : 'hikes and walks are'} now in Activities.`)
    if (result.pending || result.history_pending) parts.push(`${(result.pending || 0) + (result.history_pending || 0)} more after Strava's rate limit resets — sync again in 15 minutes.`)
    flash(parts.join(' '))
    await Promise.all([loadRegions(), loadRegion()])
  } catch (error) {
    flash(errorText(error, 'Strava sync failed. Try again in a moment.'), true)
  } finally {
    busy.value = ''
  }
}

async function importTrails() {
  busy.value = 'import'
  try {
    const result = (await api.importTrailRegion(regionKey.value)).data
    flash(`Loaded ${result.sections} trail sections (${result.km} km) from OpenStreetMap.`)
    await Promise.all([loadRegions(), loadRegion()])
  } catch (error) {
    flash(errorText(error, 'Could not reach OpenStreetMap. Try again in a minute.'), true)
  } finally {
    busy.value = ''
  }
}

function selectRegion(key) {
  if (key !== regionKey.value) router.push(`/mountains/${key}`)
}

// Remember the chosen park per range, e.g. TPN for the Tatras.
const parkStorageKey = (region) => `mountains.park.${region}`
function savedPark(region, parks) {
  try {
    const saved = localStorage.getItem(parkStorageKey(region))
    return parks.some((p) => p.key === saved) ? saved : 'all'
  } catch { return 'all' }
}

function selectPark(key) {
  park.value = key
  try { localStorage.setItem(parkStorageKey(regionKey.value), key) } catch { /* storage unavailable */ }
  const visible = sections.value.filter((s) => inPark(s, key))
  const bounds = boundsOf(visible)
  if (map && bounds) map.fitBounds(bounds, { padding: [30, 30] })
}

// ---------- full screen ----------
// The map and its side panel go full screen together, so the planner keeps its stats and points.
// Uses the browser's Fullscreen API where it can, otherwise fills the window.
const layoutEl = ref(null)
const fullscreen = ref(false)
// In full screen the side panel slides away; hovering the edge tab (or the panel) brings it back,
// clicking the tab pins it.
const SIDE_LABELS = { coverage: 'Trails', routes: 'Routes', plan: 'Plan' }
const sidePeek = ref(false)
const sidePinned = ref(false)
let sideTimer = null
function peekSide(on) {
  clearTimeout(sideTimer)
  if (on) sidePeek.value = true
  else sideTimer = setTimeout(() => { sidePeek.value = false }, 350)  // time to move from the tab onto the panel
}
let nativeFullscreen = false

function toggleFullscreen() {
  if (fullscreen.value) {
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {})
    setFullscreen(false)
    return
  }
  // Fill the window straight away; real full screen (hiding the browser) follows if allowed.
  setFullscreen(true)
  if (document.fullscreenEnabled && layoutEl.value?.requestFullscreen) {
    layoutEl.value.requestFullscreen().then(() => { nativeFullscreen = true }).catch(() => {})
  }
}

function setFullscreen(on) {
  fullscreen.value = on
  sidePeek.value = false
  sidePinned.value = false
  if (!on) nativeFullscreen = false
}

const onFullscreenChange = () => { if (!document.fullscreenElement && nativeFullscreen) setFullscreen(false) }
function onFullscreenKey(e) {
  if (e.key === 'Escape' && fullscreen.value && !nativeFullscreen) setFullscreen(false)
}

// ---------- map ----------
const mapEl = ref(null)
let map = null
let baseLayers = []
let sectionLayer = null
let trackLayer = null
let placeLayer = null
let labelLayer = null
let routeLayer = null
let planLayer = null
let resizeObserver = null
let hoverMarker = null
let placeDetail = null
const placeMarkers = new Map()
let renderer = null
const trackLines = new Map()
const sectionHits = new Map()

function baseTiles() {
  const dark = theme.value === 'dark'
  if (base.value === 'mapy' && data.value?.mapy_api_key) {
    return [L.tileLayer(`https://api.mapy.com/v1/maptiles/outdoor/256/{z}/{x}/{y}?apikey=${encodeURIComponent(data.value.mapy_api_key)}`, {
      maxZoom: 18, className: dark ? 'tiles-mapy-dark' : 'tiles-mapy-light',
      attribution: '<a href="https://api.mapy.com/copyright" target="_blank" rel="noopener">© Seznam.cz a.s. a další</a>',
    })]
  }
  return reliefLayers(theme.value)
}

function drawBase() {
  baseLayers.forEach((layer) => layer.remove())
  baseLayers = baseTiles()
  baseLayers.forEach((layer) => layer.addTo(map))
}

function popupHtml(s) {
  const pct = Math.round(s.coverage * 100)
  const state = s.status === 'done' ? 'Done' : s.status === 'partial' ? `Partly walked · ${pct}%` : pct ? `Still to do · ${pct}% walked` : 'Still to do'
  const colours = s.colours.map((c) => `<i style="background:${colourOf(c)}"></i>${COLOUR_LABELS[c]}`).join(' ')
  const parkName = (s.parks || [s.park]).join(' / ')
  const walks = s.walked_by.map((id) => trackById.value[id]).filter(Boolean)
  const walkList = walks.slice(0, 5).map((t) => `<li>${escapeHtml(shortDate(t.date))} · ${escapeHtml(t.name || 'Hike')}</li>`).join('')
  return `<div class="trail-pop">
    <strong>${escapeHtml(sectionTitle(s))}</strong>
    <div class="trail-pop-meta"><span class="trail-pop-colours">${colours}</span> · ${formatKm(s.length_m)} km · ${escapeHtml(parkName)}</div>
    ${s.names.length > 1 ? `<div class="trail-pop-names">${s.names.slice(1).map(escapeHtml).join('<br>')}</div>` : ''}
    <div class="trail-pop-state is-${s.status}">${state}</div>
    ${walks.length ? `<ul>${walkList}${walks.length > 5 ? `<li>+${walks.length - 5} more</li>` : ''}</ul>` : ''}
  </div>`
}

function drawSections() {
  sectionLayer.clearLayers()
  sectionHits.clear()
  const order = { todo: 0, partial: 1, done: 2 }
  // In route ideas every trail is a faint backdrop for the route; the planner shows them all in
  // full (you plan on them) but without popups, so a click adds a point.
  const planning = view.value === 'plan'
  const outside = (s) => view.value === 'routes' || (!planning && !inPark(s, park.value))
  // Other parks first and faint, so the selected park reads on top.
  const visible = sections.value
    .filter((s) => visibleSection(s, filter.value))
    .sort((a, b) => outside(b) - outside(a) || order[a.status] - order[b.status])
  for (const s of visible) {
    const options = { theme: theme.value, colourRemaining: colourRemaining.value, outsidePark: outside(s), backdrop: planning }
    const styles = sectionLayers(s, options)
    const coords = orientCoords(s.coords)
    const lines = styles.map((style) => (style.offset ? new OffsetPolyline(coords, { renderer, interactive: false, ...style }) : L.polyline(coords, { renderer, interactive: false, ...style })).addTo(sectionLayer))
    // Hover widens the casing (side-by-side stripes keep their width) or, without one, the line itself.
    const hoverWeight = (style) => style.weight + (style.casing ? 4 : styles.some((x) => x.casing) ? 0 : 2)
    if (options.outsidePark || planning) continue
    const hit = L.polyline(s.coords, { renderer, weight: 16, opacity: 0, color: '#000' })
      .bindPopup(() => popupHtml(s), { className: 'trail-popup', maxWidth: 300 })
      .on('mouseover', () => lines.forEach((line, i) => line.setStyle({ weight: hoverWeight(styles[i]) })))
      .on('mouseout', () => lines.forEach((line, i) => line.setStyle({ weight: styles[i].weight })))
      .addTo(sectionLayer)
    sectionHits.set(s.id, hit)
  }
}

const PLACE_LABELS = { peak: 'Summit', pass: 'Pass', cave: 'Cave', hut: 'Mountain hut' }

function placePopupHtml(p) {
  const visits = p.visited_by.map((id) => trackById.value[id]).filter(Boolean)
  const visitList = visits.slice(0, 5).map((t) => `<li>${escapeHtml(shortDate(t.date))} · ${escapeHtml(t.name || 'Hike')}</li>`).join('')
  const meta = [PLACE_LABELS[p.kind], p.ele ? `${p.ele} m` : null, (p.parks || [p.park]).join(' / ')].filter(Boolean).join(' · ')
  return `<div class="trail-pop">
    <strong>${escapeHtml(p.name)}</strong>
    <div class="trail-pop-meta">${escapeHtml(meta)}</div>
    <div class="trail-pop-state ${isReached(p) ? 'is-done' : 'is-todo'}">${isReached(p) ? `Reached · first on ${escapeHtml(shortDate(p.first_visited_on))}` : 'Not reached yet'}</div>
    ${visits.length ? `<ul>${visitList}${visits.length > 5 ? `<li>+${visits.length - 5} more</li>` : ''}</ul>` : ''}
  </div>`
}

function drawPlaces() {
  placeLayer.clearLayers()
  placeMarkers.clear()
  placeDetail = map.getZoom() >= PLACE_DETAIL_ZOOM
  if (!showPlaces.value) return
  for (const p of places.value) {
    if (!placeDetail && p.kind !== 'peak' && p.id !== activePlace.value) continue
    const planning = view.value === 'plan'
    const outside = !planning && !placeInPark(p, park.value)
    const reached = isReached(p)
    const marker = L.marker([p.lat, p.lon], {
      icon: L.divIcon({ className: 'place-marker', html: placeIcon(p.kind, reached), iconSize: [16, 16], iconAnchor: [8, 9] }),
      opacity: outside ? 0.3 : 1,
      interactive: !outside,
      keyboard: !outside,
      zIndexOffset: (outside ? 0 : 500) + (p.kind === 'peak' ? 200 : 0) + (reached ? 100 : 0),
    })
    if (planning) {
      marker
        .bindTooltip(`${escapeHtml(p.name)}${p.ele ? ` · ${p.ele} m` : ''} · click to add`, { direction: 'top', offset: [0, -8], className: 'place-tip' })
        .on('click', () => addPoint(L.latLng(p.lat, p.lon)))
    } else if (!outside) {
      marker
        .bindTooltip(`${escapeHtml(p.name)}${p.ele ? ` · ${p.ele} m` : ''}`, { direction: 'top', offset: [0, -8], className: 'place-tip' })
        .bindPopup(() => placePopupHtml(p), { className: 'trail-popup', maxWidth: 280 })
        .on('popupopen', () => { activePlace.value = p.id })
        .on('popupclose', () => { if (activePlace.value === p.id) activePlace.value = null })
    }
    marker.addTo(placeLayer)
    placeMarkers.set(p.id, marker)
  }
  labelLayer?.redraw()
}

function labelState() {
  return {
    places: places.value,
    labels: data.value?.labels || [],
    sections: sections.value,
    theme: theme.value,
    park: park.value,
    showPlaces: showPlaces.value,
    markers: [...placeMarkers.values()].map((marker) => {
      const { lat, lng } = marker.getLatLng()
      return { lat, lon: lng }
    }),
  }
}

function syncLabels() {
  if (!map) return
  if (showLabels.value && !labelLayer) labelLayer = new MountainLabels(labelState).addTo(map)
  else if (!showLabels.value && labelLayer) { labelLayer.remove(); labelLayer = null }
  else labelLayer?.redraw()
}

function onZoomEnd() {
  if (placeDetail !== map.getZoom() >= PLACE_DETAIL_ZOOM) drawPlaces()
}

function focusPlace(p) {
  if (!map) return
  showPlaces.value = true
  activePlace.value = p.id
  // Zooming redraws the markers, so open the popup only once the map has settled.
  map.once('moveend', () => {
    drawPlaces()
    placeMarkers.get(p.id)?.openPopup()
  })
  map.setView([p.lat, p.lon], Math.max(map.getZoom(), 14.5))
}

function setView(next) {
  if (next === view.value) return
  router.replace({ query: { ...route.query, view: next === 'coverage' ? undefined : next } })
}

let routesRequest = 0
async function loadRoutes() {
  if (view.value !== 'routes' || !data.value || !routePark.value) return
  const request = ++routesRequest
  routesLoading.value = true
  routesError.value = ''
  try {
    const result = (await api.getTrailRoutes(regionKey.value, { park: routePark.value, length: routeLength.value, around: includeAround.value })).data
    if (request !== routesRequest) return
    routeList.value = result.routes
    routesHaveHeights.value = result.has_heights
    if (!routeList.value.some((r) => r.key === selectedRouteKey.value)) selectedRouteKey.value = routeList.value[0]?.key || null
  } catch (error) {
    if (request !== routesRequest) return
    routeList.value = []
    routesError.value = errorText(error, 'Route ideas could not be planned. Try again in a moment.')
  } finally {
    if (request === routesRequest) routesLoading.value = false
  }
  drawRoute(true)
}

watch([selectedRouteKey, view], () => { profileHover.value = null })
watch(profileHover, (point) => {
  if (!map || !hoverMarker) return
  if (!point) { hoverMarker.remove(); return }
  hoverMarker.setLatLng([point.lat, point.lon])
  if (!map.hasLayer(hoverMarker)) hoverMarker.addTo(map)
})

function downloadGpx() {
  const r = panelRoute.value
  if (!r) return
  const gpx = view.value === 'plan' ? planGpx(r, r.title) : routeGpx(r, sectionsById.value)
  const url = URL.createObjectURL(new Blob([gpx], { type: 'application/gpx+xml' }))
  const link = Object.assign(document.createElement('a'), { href: url, download: gpxFileName(r) })
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function selectRoute(r) {
  selectedRouteKey.value = r.key
  drawRoute(true)
}

const routePin = (text, isEnd) => L.divIcon({ className: 'route-pin-shell', html: `<i class="route-pin${isEnd ? ' is-end' : ''}">${text}</i>`, iconSize: [22, 22], iconAnchor: [11, 11] })

function drawRoute(fit = false) {
  if (!routeLayer) return
  routeLayer.clearLayers()
  const r = selectedRoute.value
  if (view.value !== 'routes' || !r) return
  const colours = ROUTE_COLOURS[theme.value]
  const segments = routeSegments(r, sectionsById.value)
  for (const segment of segments) {
    L.polyline(segment.latlngs, { renderer, interactive: false, color: legend.value.casing, weight: segment.new ? 11 : 8, opacity: 0.9, lineCap: 'round', lineJoin: 'round' }).addTo(routeLayer)
  }
  for (const segment of segments) {
    L.polyline(segment.latlngs, { renderer, interactive: false, color: segment.new ? colours.new : colours.known, weight: segment.new ? 6 : 4, lineCap: 'round', lineJoin: 'round' }).addTo(routeLayer)
  }
  const same = r.mode === 'loop' || (r.start.lat === r.end.lat && r.start.lon === r.end.lon)
  L.marker([r.start.lat, r.start.lon], { icon: routePin(same ? 'S·F' : 'S'), zIndexOffset: 2000, title: `Start: ${r.start.name}` }).addTo(routeLayer)
  if (!same) L.marker([r.end.lat, r.end.lon], { icon: routePin('F', true), zIndexOffset: 2000, title: `Finish: ${r.end.name}` }).addTo(routeLayer)
  if (fit && map) {
    const points = segments.flatMap((segment) => segment.latlngs)
    // Leave room for the profile panel along the bottom of the map.
    if (points.length) map.fitBounds(L.latLngBounds(points), { paddingTopLeft: [50, 60], paddingBottomRight: [50, routeProfile.value.length > 1 && !profileCollapsed.value ? 250 : 110], maxZoom: 14 })
  }
}

// ---------- planner ----------
const planStorageKey = (region) => `mountains.plan.${region}`
function loadPlanDraft() {
  try {
    const saved = JSON.parse(localStorage.getItem(planStorageKey(regionKey.value)) || '[]')
    planPoints.value = Array.isArray(saved) ? saved.filter((p) => Array.isArray(p) && (p.length === 2 || p.length === 3)) : []
  } catch { planPoints.value = [] }
  planHistory.value = []
  plan.value = null
  editingRoute.value = null
  try { pendingEditingId = Number(localStorage.getItem(editingStorageKey(regionKey.value))) || null } catch { pendingEditingId = null }
}

// Which saved route the draft came from survives a reload too.
const editingStorageKey = (region) => `mountains.planRoute.${region}`
let pendingEditingId = null
watch(editingRoute, (r) => {
  if (!r && pendingEditingId) return  // not looked up yet (the saved list loads with the planner)
  try {
    if (r) localStorage.setItem(editingStorageKey(regionKey.value), String(r.id))
    else localStorage.removeItem(editingStorageKey(regionKey.value))
  } catch { /* storage unavailable */ }
})

function setPlanPoints(next) {
  planHistory.value = [...planHistory.value.slice(-49), planPoints.value]
  planPoints.value = next
}

const roundPoint = ([lat, lon, snap]) => [Math.round(lat * 1e6) / 1e6, Math.round(lon * 1e6) / 1e6, ...(snap ? [snap] : [])]
// A click snaps to a trail within ~30 px on screen (at least 200 m), kept with the point.
const SNAP_PX = 30
function clickPoint(latlng) {
  const metresPerPixel = map ? (40075016.686 * Math.cos((latlng.lat * Math.PI) / 180)) / 2 ** (map.getZoom() + 8) : 0
  return roundPoint([latlng.lat, latlng.lng, Math.round(Math.max(200, SNAP_PX * metresPerPixel))])
}
const addPoint = (latlng) => setPlanPoints([...planPoints.value, clickPoint(latlng)])
const movePoint = (i, latlng) => setPlanPoints(planPoints.value.map((p, k) => (k === i ? clickPoint(latlng) : p)))
const removePoint = (i) => setPlanPoints(planPoints.value.filter((_, k) => k !== i))
const insertPoint = (after, latlng) => setPlanPoints([...planPoints.value.slice(0, after + 1), clickPoint(latlng), ...planPoints.value.slice(after + 1)])
const reversePlan = () => setPlanPoints([...planPoints.value].reverse())
const closeLoop = () => setPlanPoints([...planPoints.value, planPoints.value[0]])
function clearPlan() {
  if (planPoints.value.length) setPlanPoints([])
  editingRoute.value = null
  routeForm.value = null
}
function undoPlan() {
  if (!planHistory.value.length) return
  planPoints.value = planHistory.value[planHistory.value.length - 1]
  planHistory.value = planHistory.value.slice(0, -1)
}
function pointName(w, i) {
  if (w.name) return displayName(w.name)
  const last = planWaypoints.value.length - 1
  const what = i === 0 ? 'Start' : i === last ? 'Finish' : `Point ${i}`
  return w.on_trail ? what : `${what} (off trail)`
}
const pointBadge = (i) => (i === 0 ? (planIsLoop.value ? 'S·F' : 'S') : i === planPoints.value.length - 1 ? 'F' : i)

// A route idea as planner points: its start, the middle of every section it walks, its finish.
// Shortest paths between neighbouring midpoints run through the shared junction, so the planner
// redraws the same route and any point can then be dragged.
function editInPlanner(r) {
  if (!r) return
  const middles = r.steps.map((step) => sectionsById.value[step.section]).filter(Boolean).map((s) => roundPoint(s.coords[Math.floor(s.coords.length / 2)]))
  const start = roundPoint([r.start.lat, r.start.lon])
  const end = r.mode === 'loop' ? start : roundPoint([r.end.lat, r.end.lon])
  planHistory.value = [...planHistory.value, planPoints.value]
  simplifyNext = true
  planPoints.value = [start, ...middles, end]
  fitPlanNext = true
  setView('plan')
}

async function loadSavedRoutes() {
  if (!data.value) return
  savedLoading.value = true
  try {
    const result = (await api.getSavedRoutes(regionKey.value)).data
    savedRoutes.value = result.routes
    savedCollections.value = result.collections
    const wanted = editingRoute.value?.id ?? pendingEditingId
    pendingEditingId = null
    if (wanted) editingRoute.value = result.routes.find((r) => r.id === wanted) || null
  } catch (error) {
    savedError.value = errorText(error, 'Saved routes could not be loaded.')
  } finally {
    savedLoading.value = false
  }
}

function openSaveForm() {
  savedError.value = ''
  routeForm.value = { mode: 'new', name: panelRoute.value?.title || planTitle(plan.value), collection: editingRoute.value?.collection || '' }
}

async function withSaving(action, failure) {
  savingRoute.value = true
  savedError.value = ''
  try {
    await action()
    routeForm.value = null
    await loadSavedRoutes()
  } catch (error) {
    savedError.value = errorText(error, failure)
  } finally {
    savingRoute.value = false
  }
}

const saveNewRoute = ({ name, collection }) => withSaving(async () => {
  const saved = (await api.createSavedRoute(regionKey.value, { name, collection, points: planPoints.value })).data
  editingRoute.value = saved
  flash(`Saved "${saved.name}"${saved.collection ? ` in ${saved.collection}` : ''}.`)
}, 'The route could not be saved.')

const saveChanges = () => withSaving(async () => {
  editingRoute.value = (await api.updateSavedRoute(editingRoute.value.id, { points: planPoints.value })).data
  flash(`Saved changes to "${editingRoute.value.name}".`)
}, 'The changes could not be saved.')

const renameRoute = (r, { name, collection }) => withSaving(async () => {
  const saved = (await api.updateSavedRoute(r.id, { name, collection })).data
  if (editingRoute.value?.id === r.id) editingRoute.value = saved
}, 'The route could not be renamed.')

const removeSavedRoute = (r) => withSaving(async () => {
  await api.deleteSavedRoute(r.id)
  confirmDelete.value = null
  if (editingRoute.value?.id === r.id) editingRoute.value = null
  flash(`Deleted "${r.name}".`)
}, 'The route could not be deleted.')

function openSavedRoute(r) {
  routeForm.value = null
  confirmDelete.value = null
  editingRoute.value = r
  setPlanPoints(r.points.map(roundPoint))  // undo goes back to the previous plan
  fitPlanNext = true
}

let planRequest = 0
let planTimer = null
let fitPlanNext = false
let simplifyNext = false   // the next answer may drop points the route goes through anyway
function requestPlan() {
  clearTimeout(planTimer)
  planTimer = setTimeout(async () => {
    const points = planPoints.value
    const request = ++planRequest
    if (!points.length) { plan.value = null; planLoading.value = false; drawPlan(); return }
    planLoading.value = true
    try {
      const simplify = simplifyNext
      simplifyNext = false
      const result = (await api.planTrailRoute(regionKey.value, points, simplify)).data
      if (request !== planRequest) return
      plan.value = result
      if (simplify && result.points.length < points.length) {
        planPoints.value = result.points.map(roundPoint)  // same route, fewer points (watch replans: cheap)
      }
      planError.value = ''
    } catch (error) {
      if (request !== planRequest) return
      planError.value = errorText(error, 'The route could not be planned. Try again in a moment.')
    } finally {
      if (request === planRequest) planLoading.value = false
    }
    drawPlan()
    if (fitPlanNext && view.value === 'plan') fitPlan()
  }, 120)
}

function fitPlan() {
  if (!map || !(plan.value?.track.length > 1)) return
  fitPlanNext = false
  map.fitBounds(L.latLngBounds(plan.value.track.map(([lat, lon]) => [lat, lon])), { paddingTopLeft: [50, 60], paddingBottomRight: [50, profileCollapsed.value ? 110 : 250], maxZoom: 15 })
}

// Double-click would add two points, so it only zooms outside the planner.
function syncPlanMode() {
  if (!map) return
  if (view.value === 'plan') map.doubleClickZoom.disable()
  else map.doubleClickZoom.enable()
}
watch(view, (next, previous) => {
  syncPlanMode()
  if (next === 'plan') loadSavedRoutes()
  if (next === 'plan' && previous && planPoints.value.length > 1) { fitPlanNext = true; fitPlan() }
})

watch(planPoints, (points) => {
  try { localStorage.setItem(planStorageKey(regionKey.value), JSON.stringify(points)) } catch { /* storage unavailable */ }
  drawPlan()
  requestPlan()
}, { deep: false })

function drawPlan() {
  if (!planLayer) return
  planLayer.clearLayers()
  if (view.value !== 'plan') return
  const colours = ROUTE_COLOURS[theme.value]
  // The previous answer stays drawn until the new one arrives; only an up-to-date one takes clicks.
  const current = planPoints.value.length > 1 ? plan.value : null
  const upToDate = current && current.waypoints.length === planPoints.value.length
  if (current) {
    for (const segment of current.segments) {
      L.polyline(segment.coords, { renderer, interactive: false, color: legend.value.casing, weight: segment.new ? 11 : 8, opacity: segment.on_trail ? 0.9 : 0.6, lineCap: 'round', lineJoin: 'round' }).addTo(planLayer)
    }
    for (const segment of current.segments) {
      const colour = !segment.on_trail ? colours.off : segment.new ? colours.new : colours.known
      L.polyline(segment.coords, { renderer, interactive: false, color: colour, weight: segment.new ? 6 : 4, dashArray: segment.on_trail ? null : '8 8', lineCap: 'round', lineJoin: 'round' }).addTo(planLayer)
    }
    // A wide invisible line: clicking it adds a point between the two around it.
    if (upToDate && current.track.length > 1) {
      L.polyline(current.track.map(([lat, lon]) => [lat, lon]), { renderer, weight: 18, opacity: 0, color: '#000', bubblingMouseEvents: false })
        .bindTooltip('Click to add a point here', { sticky: true, className: 'place-tip', direction: 'top', offset: [0, -10] })
        .on('click', (e) => insertPoint(legAt(current.track, current.waypoints, e.latlng.lat, e.latlng.lng), e.latlng))
        .addTo(planLayer)
    }
  }
  const last = planWaypoints.value.length - 1
  planWaypoints.value.forEach((w, i) => {
    if (planIsLoop.value && i === last) return  // the finish sits on the start pin
    const end = i === last && i > 0
    const via = i > 0 && !end
    const icon = L.divIcon({
      className: 'route-pin-shell',
      html: `<i class="route-pin${end ? ' is-end' : ''}${via ? ' is-via' : ''}${w.on_trail ? '' : ' is-off'}">${via ? '' : pointBadge(i)}</i>`,
      iconSize: via ? [14, 14] : [22, 22], iconAnchor: via ? [7, 7] : [11, 11],
    })
    const name = pointName(w, i)
    L.marker([w.lat, w.lon], { icon, draggable: true, zIndexOffset: 2500, autoPan: true, title: `${name} — drag to move, right-click to remove` })
      .on('dragend', (e) => movePoint(i, e.target.getLatLng()))
      .on('contextmenu', (e) => { L.DomEvent.preventDefault(e.originalEvent); removePoint(i) })
      .on('click', () => { if (i === 0 && planPoints.value.length > 1 && !planIsLoop.value) closeLoop() })
      .addTo(planLayer)
  })
}

function onMapClick(e) {
  if (view.value === 'plan') addPoint(e.latlng)
}

function onPlanKey(e) {
  if (view.value !== 'plan' || !(e.metaKey || e.ctrlKey) || e.key.toLowerCase() !== 'z' || e.shiftKey) return
  if (/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName)) return
  e.preventDefault()
  undoPlan()
}

function drawTracks() {
  trackLayer.clearLayers()
  trackLines.clear()
  if (!showTracks.value) return
  for (const t of tracks.value) {
    const active = activeTrack.value === t.id
    const line = L.polyline(t.latlng, {
      renderer, interactive: false, color: TRACK_COLOUR[theme.value],
      weight: active ? 4 : 2, opacity: activeTrack.value && !active ? 0.25 : active ? 1 : 0.6,
    }).addTo(trackLayer)
    trackLines.set(t.id, line)
  }
  if (activeTrack.value) trackLines.get(activeTrack.value)?.bringToFront()
}

function renderMap(fit = false) {
  if (!mapEl.value || !data.value || !sections.value.length) {
    destroyMap()
    return
  }
  if (!map) {
    map = L.map(mapEl.value, { zoomControl: true, scrollWheelZoom: true, minZoom: 9, zoomSnap: 0.25, zoomDelta: 0.5, wheelPxPerZoomLevel: 90 })
    map.createPane('labels')
    map.getPane('labels').style.zIndex = 380
    map.getPane('labels').style.pointerEvents = 'none'
    renderer = L.canvas({ tolerance: 4, padding: 0.3 })
    trackLayer = L.layerGroup().addTo(map)
    sectionLayer = L.layerGroup().addTo(map)
    routeLayer = L.layerGroup().addTo(map)
    planLayer = L.layerGroup().addTo(map)
    hoverMarker = L.circleMarker([0, 0], { renderer, radius: 7, weight: 3, color: '#0b0d11', fillColor: '#f5f7fb', fillOpacity: 1, interactive: false })
    placeLayer = L.layerGroup().addTo(map)
    map.on('zoomend', onZoomEnd)
    map.on('click', onMapClick)
    // Re-measure whenever the map box changes size (full screen, window resize).
    resizeObserver = new ResizeObserver(() => map?.invalidateSize())
    resizeObserver.observe(mapEl.value)
    syncPlanMode()
    drawBase()
    fit = true
  }
  syncLabels()
  map.invalidateSize()
  drawTracks()
  drawSections()
  drawRoute()
  drawPlan()
  if (fit) {
    const bounds = boundsOf(sections.value.filter((s) => inPark(s, park.value)))
    if (bounds) map.fitBounds(bounds, { padding: [24, 24] })
    // In the planner, open on the draft route (now, or once it has been planned).
    if (view.value === 'plan' && planPoints.value.length > 1) { fitPlanNext = true; fitPlan() }
  }
  drawPlaces()
}

function destroyMap() {
  resizeObserver?.disconnect()
  resizeObserver = null
  map?.remove()
  map = sectionLayer = trackLayer = placeLayer = labelLayer = routeLayer = planLayer = hoverMarker = renderer = null
  placeMarkers.clear()
  baseLayers = []
}

function focusSection(s) {
  if (!map) return
  if (!visibleSection(s, filter.value)) filter.value = 'all'
  nextTick(() => {
    const bounds = L.latLngBounds(s.coords)
    map.fitBounds(bounds, { padding: [90, 90], maxZoom: 15 })
    sectionHits.get(s.id)?.openPopup(bounds.getCenter())
  })
}

function focusTrack(t) {
  activeTrack.value = activeTrack.value === t.id ? null : t.id
  if (activeTrack.value) {
    showTracks.value = true
    if (map) map.fitBounds(L.latLngBounds(t.latlng), { padding: [50, 50] })
  }
}

const onThemeChange = () => {
  theme.value = resolveTheme()
  if (map) { drawBase(); renderMap() }
}

watch([filter, colourRemaining, park], () => map && drawSections())
watch([showPlaces, park], () => map && drawPlaces())
watch(showLabels, syncLabels)
watch([showTracks, activeTrack], () => map && drawTracks())
watch(base, () => map && drawBase())
watch(regionKey, () => {
  filter.value = 'all'
  routeList.value = []
  savedRoutes.value = []
  editingRoute.value = null
  routeForm.value = null
  destroyMap()
  loadPlanDraft()
  loadRegion()
})
watch([view, routePark, routeLength, includeAround, () => data.value?.imported_at], () => {
  if (map) { drawSections(); drawRoute(); drawPlan(); drawPlaces() }
  loadRoutes()
})

onMounted(() => {
  window.addEventListener('themechange', onThemeChange)
  window.addEventListener('keydown', onPlanKey)
  window.addEventListener('keydown', onFullscreenKey)
  document.addEventListener('fullscreenchange', onFullscreenChange)
  loadPlanDraft()
  loadRegions()
  loadRegion()
})
onBeforeUnmount(() => {
  window.removeEventListener('themechange', onThemeChange)
  window.removeEventListener('keydown', onPlanKey)
  window.removeEventListener('keydown', onFullscreenKey)
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  if (document.fullscreenElement === layoutEl.value) document.exitFullscreen().catch(() => {})
  clearTimeout(flash.timer)
  clearTimeout(planTimer)
  clearTimeout(sideTimer)
  destroyMap()
})
</script>

<style scoped>
.mountains-page { display: grid; gap: 0; }
.page-head { align-items: flex-end; margin-bottom: 18px; }
.head-actions { display: flex; align-items: center; gap: 10px; }
.region-tabs { display: flex; gap: 3px; padding: 3px; border: 1px solid var(--border); border-radius: 12px; background: rgb(var(--panel-rgb) / .7); }
.region-tabs button { white-space: nowrap; display: inline-flex; align-items: baseline; gap: 7px; padding: 8px 14px; border: 0; border-radius: 9px; background: transparent; color: var(--muted-soft); font: 600 13px var(--font-display); cursor: pointer; }
.region-tabs button small { font-size: 11px; color: var(--muted); font-variant-numeric: tabular-nums; }
.region-tabs button.active { background: rgb(var(--ov-rgb) / .08); color: var(--text); box-shadow: inset 0 0 0 1px var(--border); }
.region-tabs button.active small { color: var(--success-text); }
.action { padding: 10px 14px; border: 1px solid rgba(95,140,255,.38); border-radius: 11px; background: rgba(95,140,255,.14); color: var(--text); font-size: 12px; font-weight: 700; cursor: pointer; white-space: nowrap; }
.action:hover:not(:disabled) { background: rgba(95,140,255,.22); border-color: rgba(123,163,255,.55); }
.action:disabled { opacity: .6; cursor: progress; }
.flash { margin: -6px 0 14px; padding: 9px 12px; border: 1px solid rgba(67,209,124,.3); border-radius: 10px; background: rgba(67,209,124,.08); color: var(--text); font-size: 13px; }
.flash.error { border-color: rgba(255,92,111,.35); background: rgba(255,92,111,.08); }

.mountains-layout { display: grid; grid-template-columns: minmax(0, 1fr) 330px; gap: 16px; align-items: start; }
.map-card { position: relative; height: max(560px, calc(100vh - 190px)); border: 1px solid var(--border); border-radius: var(--radius-card); overflow: hidden; background: var(--deep); box-shadow: var(--shadow-card); }
.trail-map { position: absolute; inset: 0; }
.map-state { position: absolute; inset: 0; display: grid; place-items: center; color: var(--muted); font-size: 14px; z-index: 500; }
.state-box { max-width: 360px; padding: 22px; border: 1px solid var(--border); border-radius: 14px; background: rgb(var(--panel-rgb) / .96); text-align: center; display: grid; gap: 10px; justify-items: center; }
.state-box strong { color: var(--text); font: 600 16px var(--font-display); }
.state-box p { margin: 0; font-size: 13px; }

.map-toolbar { position: absolute; top: 12px; left: 56px; right: 12px; z-index: 600; display: flex; flex-wrap: wrap; gap: 8px; pointer-events: none; }
.map-toolbar > * { pointer-events: auto; }
.fullscreen-toggle { margin-left: auto; display: inline-flex; align-items: center; gap: 6px; }
.mountains-layout.is-fullscreen { position: fixed; inset: 0; z-index: 2000; padding: 12px; background: var(--bg); }
.mountains-layout.is-fullscreen .map-card { height: calc(100vh - 24px); animation: none; }  /* moving the node would replay the entrance */
.mountains-layout.is-fullscreen { grid-template-columns: minmax(0, 1fr); }
.mountains-layout.is-fullscreen .side {
  position: fixed; top: 12px; right: 12px; z-index: 2002; width: 340px; max-height: calc(100vh - 24px);
  padding: 4px; border-radius: calc(var(--radius-card) + 4px); background: rgb(var(--deep-rgb) / .72); backdrop-filter: blur(6px);
  box-shadow: 0 8px 30px rgb(var(--shadow-rgb) / .45);
  transform: translateX(calc(100% + 24px)); opacity: 0; pointer-events: none; transition: transform .22s ease, opacity .22s ease;
}
.mountains-layout.is-fullscreen.side-open .side { transform: none; opacity: 1; pointer-events: auto; }
.side-handle {
  position: fixed; right: 12px; top: 64px; z-index: 2001;  /* under the panel's top edge: opening it puts the pointer on the panel */
  display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 12px 6px; border: 1px solid var(--border); border-right: 0;
  border-radius: 10px 0 0 10px; background: rgb(var(--panel-rgb) / .94); color: var(--muted-soft); font: 600 11.5px var(--font-display); cursor: pointer;
  box-shadow: 0 2px 10px rgb(var(--shadow-rgb) / .3); transition: opacity .22s ease;
}
.side-handle span { writing-mode: vertical-rl; transform: rotate(180deg); letter-spacing: .04em; }
.side-handle:hover, .side-handle.pinned { color: var(--text); border-color: rgba(123,163,255,.55); }
.mountains-layout.side-open .side-handle.pinned { right: 364px; }  /* beside the pinned panel, to unpin it */
.seg { display: flex; gap: 2px; padding: 3px; border-radius: 10px; background: rgb(var(--panel-rgb) / .92); border: 1px solid var(--border); box-shadow: 0 2px 10px rgb(var(--shadow-rgb) / .25); }
.seg button, .toggle { border: 0; background: transparent; color: var(--muted-soft); padding: 6px 11px; border-radius: 7px; font-size: 12px; font-weight: 600; cursor: pointer; }
.seg button.on { background: rgb(var(--ov-rgb) / .1); color: var(--text); }
.toggle { background: rgb(var(--panel-rgb) / .92); border: 1px solid var(--border); border-radius: 10px; padding: 8px 12px; box-shadow: 0 2px 10px rgb(var(--shadow-rgb) / .25); }
.toggle.on { color: var(--text); border-color: rgba(123,163,255,.55); background: rgb(var(--panel-rgb) / .97); box-shadow: inset 0 0 0 1px rgba(123,163,255,.35), 0 2px 10px rgb(var(--shadow-rgb) / .25); }
.map-legend { position: absolute; left: 12px; bottom: 12px; z-index: 600; display: flex; gap: 14px; padding: 8px 12px; border-radius: 10px; background: rgb(var(--panel-rgb) / .92); border: 1px solid var(--border); color: var(--muted-soft); font-size: 11.5px; }
.map-legend span { display: inline-flex; align-items: center; gap: 6px; }
.map-legend.above-profile { bottom: 200px; }
.map-legend.above-panel { bottom: 76px; }
.route-profile { position: absolute; left: 12px; right: 12px; bottom: 26px; z-index: 600; padding: 10px 14px 4px; border-radius: 12px; background: rgb(var(--panel-rgb) / .94); border: 1px solid var(--border); box-shadow: 0 2px 14px rgb(var(--shadow-rgb) / .3); }
.route-profile-head { display: flex; justify-content: space-between; gap: 16px; font-size: 12px; color: var(--muted-soft); font-variant-numeric: tabular-nums; }
.route-profile-head strong { color: var(--text); font: 600 13px var(--font-display); min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.route-profile-head { align-items: center; }
.route-profile-head span { flex: none; margin-left: auto; }
.route-profile.no-chart { padding-bottom: 10px; }
.gpx-button { flex: none; display: inline-flex; align-items: center; gap: 5px; margin: -4px 0; padding: 4px 10px; border: 1px solid var(--border); border-radius: 8px; background: rgb(var(--ov-rgb) / .05); color: var(--text); font: inherit; font-size: 11.5px; font-weight: 600; cursor: pointer; }
.planner-hint { line-height: 1.5; }
.planner-stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px 10px; margin-bottom: 12px; }
.planner-stats span { display: block; color: var(--muted); font-size: 11px; margin-bottom: 2px; }
.planner-stats strong { font: 700 18px/1.15 var(--font-display); font-variant-numeric: tabular-nums; }
.planner-stats strong small { font-size: 11px; color: var(--muted); font-weight: 600; }
.planner-stats strong.is-new { color: var(--success-text); }
.planner-warn { margin-bottom: 10px; color: #f5b14a; }
.planner-actions { display: flex; flex-wrap: wrap; gap: 6px; }
.planner-actions button { padding: 6px 10px; border: 1px solid var(--border); border-radius: 8px; background: rgb(var(--ov-rgb) / .04); color: var(--text); font-size: 12px; font-weight: 600; cursor: pointer; }
.planner-actions button:hover:not(:disabled) { background: rgb(var(--ov-rgb) / .09); }
.planner-actions button:disabled { opacity: .45; cursor: default; }
.planner-actions button.danger { margin-left: auto; color: #ff8a98; }
.planner-points .planner-hint { margin-bottom: 8px; }
.planner-points ol { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: minmax(0, 1fr); }
.planner-points li { display: flex; align-items: center; gap: 10px; padding: 6px 0; border-top: 1px solid var(--border); font-size: 13px; }
.planner-points li:first-child { border-top: 0; }
.planner-points li .route-pin { flex: none; min-width: 26px; }
.planner-point-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.planner-points li button { flex: none; width: 22px; height: 22px; border: 0; border-radius: 6px; background: transparent; color: var(--muted); font-size: 16px; line-height: 1; cursor: pointer; }
.planner-points li button:hover { background: rgb(var(--ov-rgb) / .08); color: var(--text); }
.planner-save { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); }
.planner-save button { padding: 6px 12px; border: 1px solid var(--border); border-radius: 8px; background: rgb(var(--ov-rgb) / .04); color: var(--text); font-size: 12px; font-weight: 600; cursor: pointer; }
.planner-save button.primary { border-color: rgba(74, 222, 128, .45); background: rgba(74, 222, 128, .14); }
.planner-save button:disabled { opacity: .5; cursor: default; }
.planner-editing { flex-basis: 100%; margin-bottom: 4px; }
.planner-editing b { color: var(--text); font-weight: 600; }
.planner-editing em { font-style: normal; color: #f5b14a; }
.saved-group + .saved-group { margin-top: 12px; }
.saved-group h4 { margin: 0 0 4px; color: var(--muted-soft); font: 600 11px var(--font-display); text-transform: uppercase; letter-spacing: .05em; }
.saved-group h4 small { color: var(--muted); font-weight: 500; margin-left: 4px; }
.saved-group ul { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: minmax(0, 1fr); }
.saved-group li { display: flex; align-items: center; gap: 4px; border-top: 1px solid var(--border); }
.saved-group li:first-child { border-top: 0; }
.saved-group li:has(.saved-form) { display: block; }
.saved-group li:has(.saved-form) .saved-form { margin-top: 4px; border-top: 0; padding: 4px 0 10px; }
.saved-open { flex: 1; min-width: 0; display: grid; gap: 2px; padding: 8px 6px; margin-left: -6px; border: 0; border-radius: 8px; background: transparent; color: var(--text); text-align: left; font: inherit; cursor: pointer; }
.saved-open:hover { background: rgb(var(--ov-rgb) / .05); }
.saved-group li.on .saved-open { background: rgba(74, 222, 128, .08); }
.saved-name { font-size: 13px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.saved-meta { color: var(--muted); font-size: 11.5px; font-variant-numeric: tabular-nums; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.saved-meta b { color: var(--success-text); font-weight: 600; }
.saved-meta i { font-style: normal; }
.saved-tools { flex: none; display: flex; gap: 2px; opacity: .55; transition: opacity .15s; }
.saved-group li:hover .saved-tools, .saved-tools:focus-within { opacity: 1; }
.saved-tools button { display: inline-grid; place-items: center; min-width: 26px; height: 26px; padding: 0 6px; border: 0; border-radius: 6px; background: transparent; color: var(--muted-soft); font-size: 11.5px; font-weight: 600; cursor: pointer; }
.saved-tools button:hover { background: rgb(var(--ov-rgb) / .08); color: var(--text); }
.saved-tools button.danger { color: #ff8a98; }
.gpx-button:hover { border-color: rgba(74, 222, 128, .55); background: rgb(var(--ov-rgb) / .09); }

.side { display: grid; grid-template-columns: minmax(0, 1fr); gap: 12px; max-height: max(560px, calc(100vh - 190px)); overflow-y: auto; padding-right: 2px; }
.side .card { padding: 16px 18px; }
.side .card-title { margin-bottom: 10px; display: flex; justify-content: space-between; }
.side .card-title small { font-size: 11px; letter-spacing: 0; color: var(--muted); }
.park-chips { display: flex; gap: 5px; flex-wrap: wrap; margin-bottom: 14px; }
.park-chips button { border: 1px solid var(--border); background: transparent; color: var(--muted-soft); padding: 5px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; cursor: pointer; }
.park-chips button small { color: var(--muted); font-weight: 500; margin-left: 2px; }
.park-chips button.on { color: var(--text); border-color: rgba(123,163,255,.55); background: rgba(95,140,255,.14); }
.progress-main { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; }
.pct { font: 700 44px/1 var(--font-display); letter-spacing: -.04em; }
.pct span { font-size: 22px; color: var(--muted); margin-left: 2px; }
.kms { color: var(--muted-soft); font-size: 13px; font-variant-numeric: tabular-nums; }
.kms b { color: var(--text); }
.bar { height: 8px; border-radius: 999px; background: rgb(var(--ov-rgb) / .07); overflow: hidden; margin: 12px 0 8px; }
.bar i { display: block; height: 100%; border-radius: inherit; background: var(--success-text); }
.bar.thin { height: 5px; margin: 5px 0 10px; }
.fine { margin: 0; color: var(--muted); font-size: 12px; }
.colour-row .row-line { display: flex; justify-content: space-between; gap: 8px; font-size: 12.5px; }
.colour-name { display: inline-flex; align-items: center; gap: 7px; font-weight: 600; }
.colour-name i { width: 10px; height: 10px; border-radius: 50%; box-shadow: 0 0 0 1px rgb(var(--ov-rgb) / .2); }
.num { font-variant-numeric: tabular-nums; color: var(--muted-soft); }
.num b { color: var(--text); }
.years { display: flex; align-items: flex-end; gap: 8px; height: 100px; }
.year { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; gap: 4px; min-width: 0; }
.year i { width: 100%; max-width: 30px; border-radius: 5px 5px 2px 2px; background: var(--success-text); opacity: .85; }
.year-km { font-size: 10.5px; }
.year-label { font-size: 11px; color: var(--muted); }
.list { display: grid; gap: 1px; margin: 0 -8px; }
.list button { display: flex; align-items: center; gap: 9px; padding: 7px 8px; min-width: 0; border: 0; border-radius: 8px; background: transparent; color: var(--text); font-size: 12.5px; text-align: left; cursor: pointer; }
.list button:hover, .list button.on { background: rgb(var(--ov-rgb) / .06); }
.list button.on { box-shadow: inset 2px 0 0 #b79cff; }
.grow { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dots { display: inline-flex; gap: 2px; }
.dots i { width: 8px; height: 8px; border-radius: 50%; box-shadow: 0 0 0 1px rgb(var(--ov-rgb) / .2); }
.date { width: 82px; flex: none; font-size: 11.5px; }
.new { color: var(--success-text); font-size: 11.5px; font-weight: 600; }
.hikes { max-height: 340px; overflow-y: auto; overflow-x: hidden; }
.source { padding: 0 4px 8px; }
.link { border: 0; padding: 0; background: none; color: var(--accent-strong); font: inherit; cursor: pointer; text-decoration: underline; }

.places-card .card-title { margin-bottom: 12px; }
.kind-tabs { display: grid; grid-template-columns: repeat(auto-fit, minmax(0, 1fr)); gap: 3px; padding: 3px; border-radius: 10px; background: rgb(var(--ov-rgb) / .05); margin-bottom: 12px; }
.kind-tabs button { display: grid; gap: 1px; min-width: 0; border: 0; background: transparent; color: var(--muted-soft); padding: 5px 2px; border-radius: 7px; font-size: 12px; font-weight: 600; cursor: pointer; }
.kind-tabs button small { color: var(--muted); font-size: 11px; font-weight: 500; font-variant-numeric: tabular-nums; }
.kind-tabs button.on { background: rgb(var(--ov-rgb) / .1); color: var(--text); }
.places-head { margin: 0; font-size: 12.5px; color: var(--muted-soft); }
.places-head b { color: var(--text); font-size: 15px; }
.place-filters { display: flex; gap: 5px; margin-bottom: 8px; }
.place-filters button { border: 1px solid var(--border); background: transparent; color: var(--muted-soft); padding: 4px 10px; border-radius: 999px; font-size: 11.5px; font-weight: 600; cursor: pointer; }
.place-filters button.on { color: var(--text); border-color: rgba(123,163,255,.55); background: rgba(95,140,255,.14); }
.places { max-height: 300px; overflow-y: auto; overflow-x: hidden; }
.places .place-icon { width: 16px; height: 16px; flex: none; }
.places .place-icon :deep(svg) { display: block; }
.places button:not(.reached) .grow { color: var(--muted-soft); }
.places .ele { font-size: 11.5px; }
.places .when { width: 34px; flex: none; text-align: right; font-size: 11.5px; }
.places button.reached .when { color: var(--success-text); font-weight: 600; }
.legend-icon { display: inline-flex; width: 14px; height: 14px; }
.legend-icon :deep(svg) { width: 14px; height: 14px; }
.around-switch { display: flex; gap: 9px; align-items: flex-start; margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); font-size: 12.5px; color: var(--text); cursor: pointer; }
.around-switch input { margin-top: 2px; accent-color: var(--accent); }
.around-switch small { display: block; margin-top: 2px; color: var(--muted); font-size: 11.5px; }
.routes-controls { display: grid; gap: 12px; }
.routes-controls .park-chips { margin-bottom: 0; }
.length-tabs { display: grid; grid-template-columns: repeat(3, 1fr); gap: 3px; padding: 3px; border-radius: 10px; background: rgb(var(--ov-rgb) / .05); }
.length-tabs button { display: grid; gap: 1px; border: 0; background: transparent; color: var(--muted-soft); padding: 6px 4px; border-radius: 7px; font-size: 12px; font-weight: 600; cursor: pointer; }
.length-tabs button small { color: var(--muted); font-size: 10.5px; font-weight: 500; }
.length-tabs button.on { background: rgb(var(--ov-rgb) / .1); color: var(--text); }
.routes-controls .around-switch { margin-top: 0; }
.routes-state { padding: 4px 4px 0; }
.route-card { display: grid; gap: 6px; width: 100%; text-align: left; color: var(--text); font: inherit; cursor: pointer; padding: 14px 16px !important; }
.route-card.on { border-color: rgba(74, 222, 128, .55); box-shadow: inset 0 0 0 1px rgba(74, 222, 128, .35), var(--shadow-card); }
.route-title { font: 600 14px/1.3 var(--font-display); }
.route-sub { color: var(--muted); font-size: 11.5px; }
.route-stats { display: flex; gap: 12px; color: var(--muted-soft); font-size: 12.5px; font-variant-numeric: tabular-nums; }
.route-stats b { color: var(--text); }
.route-new { font-size: 12.5px; color: var(--muted-soft); }
.route-new b { color: var(--success-text); }
.route-places { display: flex; flex-wrap: wrap; gap: 4px 10px; font-size: 11.5px; }
.route-places > span { display: inline-flex; align-items: center; gap: 4px; color: var(--text); }
.route-places > span.reached { color: var(--muted); }
.route-places i { display: inline-flex; width: 12px; height: 12px; }
.route-places i :deep(svg) { width: 12px; height: 12px; }
.route-places small { color: var(--muted); }
.legend-pin { position: static !important; }
.map-legend .route-pin { min-width: 18px; height: 18px; font-size: 9.5px; margin-right: 2px; }

@media (max-width: 1100px) {
  .mountains-layout { grid-template-columns: 1fr; }
  .side { max-height: none; overflow: visible; }
}
@media (max-width: 760px) {
  .page-head { display: grid; align-items: start; }
  .head-actions { flex-wrap: wrap; }
  .map-card { height: 62vh; min-height: 420px; }
  .map-toolbar { left: 12px; top: 56px; }
  .map-legend { display: none; }
}
</style>
