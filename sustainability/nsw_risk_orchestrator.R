# NSW Suburb Environmental Risk Orchestrator ------------------------------------------------------
#
# Generate 7 day Erosion & Sediment Control (ESC) plus Dust risk plans for
# New South Wales suburbs.  The workflow mirrors CTRL Environmental's R based
# operational notebook and has been rewritten here as a stand-alone script for
# the Python Algorithms repository.  The code expects an ``suburbs.csv`` file
# with a single ``suburb`` column (additional optional columns can be supplied
# for ``soil`` as well as pre-computed ``latitude``/``longitude``).
#
# Usage::
#
#   Rscript sustainability/nsw_risk_orchestrator.R --input suburbs.csv
#
# All outputs will be written to ``./risk_out`` (overridable via ``--out``).
# --------------------------------------------------------------------------------

suppressPackageStartupMessages({
  req <- c(
    "bomrang", "dplyr", "tidyr", "purrr", "readr", "stringr", "lubridate",
    "geosphere", "ggplot2", "leaflet", "htmlwidgets", "scales", "janitor",
    "glue", "slider", "tidygeocoder", "sf", "digest", "optparse"
  )

  to_install <- setdiff(req, rownames(installed.packages()))
  if (length(to_install)) {
    install.packages(to_install, repos = "https://cloud.r-project.org")
  }

  invisible(lapply(req, library, character.only = TRUE))
})

# ---------------- Argument parsing ---------------------------------------------------------------
option_list <- list(
  optparse::make_option(
    c("-i", "--input"), default = "suburbs.csv",
    help = "Input CSV containing at least a suburb column", metavar = "FILE"
  ),
  optparse::make_option(
    c("-o", "--out"), default = "risk_out",
    help = "Directory to write outputs", metavar = "DIR"
  ),
  optparse::make_option(
    c("-s", "--state"), default = "NSW",
    help = "State abbreviation for geocoding bias"
  ),
  optparse::make_option(
    c("-t", "--threshold"), type = "integer", default = 60,
    help = "Calendar threshold: export days with scores >= this value"
  ),
  optparse::make_option(
    "--default-soil", default = "LOAM",
    help = "Fallback soil type if the CSV does not include a soil column"
  )
)

opt <- optparse::parse_args(optparse::OptionParser(option_list = option_list))

in_file <- opt$input
state_abbrev <- opt$state
out_dir <- opt$out
calendar_threshold <- opt$threshold
default_soil <- opt$`default-soil`

dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)

# Soil susceptibility (affects ESC and dust dispersion) -------------------------------------------
soil_factor <- c(SAND = 1.15, LOAM = 1.0, CLAY = 0.9, SILT = 1.2, GRAVEL = 0.95)

# ---------------- Helpers -----------------------------------------------------------------------
nearest_precis_location <- function(lat, lon) {
  bomrang::towns |>
    dplyr::filter(state == state_abbrev) |>
    dplyr::mutate(
      dist_km = geosphere::distHaversine(
        cbind(lon, lat), cbind(lonwgs84, latwgs84)
      ) / 1000
    ) |>
    dplyr::arrange(dist_km) |>
    dplyr::slice(1)
}

nearest_station_daily <- function(lat, lon) {
  bomrang::stations_site_list |>
    tibble::as_tibble() |>
    janitor::clean_names() |>
    dplyr::filter(state == state_abbrev) |>
    dplyr::mutate(
      dist_km = geosphere::distHaversine(
        cbind(lon, lat), cbind(longitude, latitude)
      ) / 1000
    ) |>
    dplyr::arrange(dist_km) |>
    dplyr::slice(1)
}

parse_wind_kmh <- function(x) {
  m <- stringr::str_match(x, "(\\d{1,2})\\s*to\\s*(\\d{1,2})\\s*km/h")
  out <- suppressWarnings(rowMeans(cbind(as.numeric(m[, 2]), as.numeric(m[, 3])), na.rm = TRUE))
  out[is.na(out)] <- suppressWarnings(as.numeric(stringr::str_match(x, "(\\d{1,2})\\s*km/h")[, 2]))
  out
}

score_ESC <- function(rain_mm, wind_kmh, tmax_c, soil = "LOAM") {
  sf <- soil_factor[[toupper(soil)]]
  if (is.null(sf)) sf <- 1.0
  rain_component <- pmin(100, (pmax(rain_mm, 0)^0.9) * 6.5)
  wind_component <- pmin(100, (pmax(wind_kmh - 15, 0) * 2.3))
  heat_component <- ifelse(tmax_c >= 32, (tmax_c - 31) * 5, 0)
  pmin(100, round(sf * (0.58 * rain_component + 0.28 * wind_component + 0.14 * heat_component)))
}

score_DUST <- function(wind_kmh, tmax_c, rain_7d, rain_3d) {
  dry_bonus <- dplyr::case_when(
    rain_7d <= 2 ~ 25,
    rain_7d <= 5 ~ 15,
    rain_7d <= 10 ~ 8,
    TRUE ~ 0
  )
  last3_dry <- ifelse(rain_3d < 1, 10, 0)
  wind_core <- pmin(100, pmax(wind_kmh - 20, 0) * 3.2)
  heat_lift <- ifelse(tmax_c >= 30, (tmax_c - 29) * 2.5, 0)
  base <- 0.55 * wind_core + 0.25 * heat_lift + 0.20 * (dry_bonus + last3_dry)
  pmin(100, round(base))
}

actions_from <- function(esc, dust, rain_mm, wind_kmh) {
  a <- c()
  if (esc >= 80) {
    a <- c(
      a,
      "Suspend bulk earthworks; inspect/empty basins pre-/post-event",
      "Double inlet protection; deploy extra street sweep"
    )
  } else if (esc >= 60) {
    a <- c(a, "Pre-stage sandbags; stabilise haul roads; confirm basin freeboard")
  } else if (esc >= 40) {
    a <- c(a, "Top up geofabric/silt socks; maintain entries; cover bins")
  } else {
    a <- c(a, "Routine controls; spot-check edges & drains")
  }

  if (dust >= 70) a <- c(a, "Increase dust suppression frequency; halt grinding if plumes visible")
  if (dust >= 85) a <- c(a, "Reschedule saw-cutting/hydro-excav unless fully contained")
  if (rain_mm >= 20) a <- c(a, "Install extra inlet protection; inspect after first flush")
  if (wind_kmh >= 35) a <- c(a, "Wind watch: monitor downwind complaints; add water cart loop")
  unique(a)
}

ics_event <- function(uid, title, date_str, description = "", tz = "Australia/Sydney") {
  glue::glue(
    "BEGIN:VEVENT\n",
    "UID:{uid}\n",
    "DTSTAMP:{format(Sys.time(), '%Y%m%dT%H%M%SZ')}\n",
    "DTSTART;VALUE=DATE:{date_str}\n",
    "SUMMARY:{title}\n",
    "DESCRIPTION:{gsub('\n','\\\n',description)}\n",
    "END:VEVENT"
  )
}

# ---------------- Load suburbs & geocode (OSM / Nominatim) --------------------------------------
subs <- readr::read_csv(in_file, show_col_types = FALSE) |>
  janitor::clean_names() |>
  dplyr::filter(!is.na(suburb), nzchar(suburb))

if (nrow(subs) == 0) {
  stop("No suburb rows found in suburbs.csv")
}

if (!"soil" %in% names(subs)) {
  subs$soil <- default_soil
}

if (!"latitude" %in% names(subs)) {
  subs$latitude <- NA_real_
}

if (!"longitude" %in% names(subs)) {
  subs$longitude <- NA_real_
}

subs <- subs |>
  dplyr::mutate(row_id = dplyr::row_number())

message("Geocoding suburbs…")

needs_geocode <- subs |>
  dplyr::filter(is.na(latitude) | is.na(longitude)) |>
  dplyr::mutate(query = paste(suburb, state_abbrev, "Australia"))

if (nrow(needs_geocode) > 0) {
  geo_attempt <- tryCatch(
    tidygeocoder::geocode(
      needs_geocode,
      address = query,
      lat = latitude,
      long = longitude,
      method = "osm",
      limit = 1
    ),
    error = function(e) {
      warning("Geocoding failed: ", conditionMessage(e))
      needs_geocode
    }
  )

  subs <- subs |>
    dplyr::left_join(
      geo_attempt |>
        dplyr::select(row_id, latitude_geo = latitude, longitude_geo = longitude),
      by = "row_id"
    ) |>
    dplyr::mutate(
      latitude = dplyr::coalesce(latitude, latitude_geo),
      longitude = dplyr::coalesce(longitude, longitude_geo)
    ) |>
    dplyr::select(-latitude_geo, -longitude_geo)
}

missing_geo <- subs |>
  dplyr::filter(is.na(latitude) | is.na(longitude))

if (nrow(missing_geo) > 0) {
  warning("Unable to geocode some suburbs: ", paste(missing_geo$suburb, collapse = ", "))
}

geo <- subs |>
  dplyr::filter(!is.na(latitude) & !is.na(longitude)) |>
  dplyr::select(-row_id)

if (nrow(geo) == 0) {
  stop("No geocoded suburbs available.")
}

# ---------------- Find nearest forecast + nearest daily station per suburb -----------------------
nearest_tbl <- geo |>
  dplyr::mutate(row = dplyr::row_number()) |>
  dplyr::mutate(
    nearest_precis = purrr::pmap(
      list(latitude, longitude),
      ~ nearest_precis_location(..1, ..2)
    ),
    nearest_daily = purrr::pmap(
      list(latitude, longitude),
      ~ nearest_station_daily(..1, ..2)
    )
  ) |>
  tidyr::unnest_wider(nearest_precis, names_sep = "_") |>
  tidyr::unnest_wider(nearest_daily, names_sep = "_") |>
  dplyr::rename(
    wmo = nearest_precis_wmo,
    forecast_name = nearest_precis_name,
    forecast_lat = nearest_precis_latwgs84,
    forecast_lon = nearest_precis_lonwgs84,
    daily_site = nearest_daily_site,
    daily_name = nearest_daily_name,
    daily_lat = nearest_daily_latitude,
    daily_lon = nearest_daily_longitude,
    daily_dist_km = nearest_daily_dist_km
  )

# ---------------- Pull 7-day BoM precis forecasts for unique WMO codes --------------------------
loc_ids <- unique(nearest_tbl$wmo)
message("Fetching precis forecasts for ", length(loc_ids), " locations…")

fc_list <- lapply(loc_ids, function(id) {
  tryCatch({
    f <- bomrang::get_precis_forecast(id)
    f$wmo <- id
    f
  }, error = function(e) NULL)
})

fc_all <- dplyr::bind_rows(fc_list) |>
  janitor::clean_names()

fc_7 <- fc_all |>
  dplyr::mutate(date = as.Date(aussie_date)) |>
  dplyr::select(
    wmo, date, forecast = precis, min = air_temp_min_c,
    max = air_temp_max_c, rain_mm = rainfall, wind
  ) |>
  dplyr::filter(date >= Sys.Date(), date <= Sys.Date() + 6) |>
  dplyr::mutate(
    wind_kmh = parse_wind_kmh(wind),
    rain_mm = suppressWarnings(as.numeric(rain_mm)),
    tmax_c = suppressWarnings(as.numeric(max)),
    tmin_c = suppressWarnings(as.numeric(min))
  ) |>
  dplyr::select(-wind, -max, -min)

# ---------------- Pull recent daily rainfall near each suburb (dryness proxy) -------------------
start_hist <- Sys.Date() - 21
message("Fetching daily rainfall history…")

hist_list <- lapply(unique(nearest_tbl$daily_site), function(site) {
  tryCatch({
    d <- bomrang::get_historical(
      site, type = "daily", from = start_hist, to = Sys.Date()
    )
    d$site <- site
    d
  }, error = function(e) NULL)
})

hist_all <- dplyr::bind_rows(hist_list) |>
  janitor::clean_names()

hist_tidy <- hist_all |>
  dplyr::transmute(
    site,
    date = lubridate::make_date(year, month, day),
    rainfall_mm
  ) |>
  dplyr::filter(!is.na(date))

# ---------------- Build plan per suburb ---------------------------------------------------------
plan <- nearest_tbl |>
  dplyr::select(
    suburb, latitude, longitude, soil, wmo,
    forecast_name, daily_site, daily_name
  ) |>
  dplyr::left_join(fc_7, by = "wmo") |>
  dplyr::group_by(suburb) |>
  dplyr::arrange(date, .by_group = TRUE) |>
  dplyr::left_join(hist_tidy, by = c("daily_site" = "site", "date" = "date")) |>
  dplyr::group_by(suburb) |>
  dplyr::mutate(
    rain_7d = slider::slide_dbl(
      rainfall_mm, ~ sum(pmax(.x, 0), na.rm = TRUE), .before = 6, .complete = FALSE
    ),
    rain_3d = slider::slide_dbl(
      rainfall_mm, ~ sum(pmax(.x, 0), na.rm = TRUE), .before = 2, .complete = FALSE
    ),
    days_since_rain = slider::slide_int(
      rainfall_mm,
      ~ {
        r <- rev(.x)
        k <- match(TRUE, r > 0)
        ifelse(is.na(k), length(.x), k - 1)
      },
      .before = 14, .complete = FALSE
    )
  ) |>
  dplyr::ungroup() |>
  dplyr::mutate(
    esc_score = score_ESC(
      rain_mm = dplyr::coalesce(rain_mm, 0),
      wind_kmh = dplyr::coalesce(wind_kmh, 0),
      tmax_c = dplyr::coalesce(tmax_c, 0),
      soil = soil
    ),
    dust_score = score_DUST(
      wind_kmh = dplyr::coalesce(wind_kmh, 0),
      tmax_c = dplyr::coalesce(tmax_c, 0),
      rain_7d = dplyr::coalesce(rain_7d, 0),
      rain_3d = dplyr::coalesce(rain_3d, 0)
    ),
    risk_band = dplyr::case_when(
      pmax(esc_score, dust_score) >= 80 ~ "Severe",
      pmax(esc_score, dust_score) >= 60 ~ "High",
      pmax(esc_score, dust_score) >= 40 ~ "Elevated",
      TRUE ~ "Moderate"
    ),
    actions = purrr::pmap_chr(
      list(
        esc_score, dust_score,
        dplyr::coalesce(rain_mm, 0),
        dplyr::coalesce(wind_kmh, 0)
      ),
      ~ paste(actions_from(..1, ..2, ..3, ..4), collapse = " · ")
    )
  )

# ---------------- Trend engine (per suburb) ----------------------------------------------------
trend <- plan |>
  dplyr::group_by(suburb) |>
  dplyr::arrange(date, .by_group = TRUE) |>
  dplyr::mutate(
    total_score = pmax(esc_score, dust_score),
    delta_d1 = total_score - dplyr::lag(total_score, 1),
    wk_mean = slider::slide_dbl(total_score, mean, .before = 6, .complete = FALSE),
    wk_delta = wk_mean - dplyr::lag(wk_mean, 7),
    rising_run = ifelse(is.na(delta_d1), 0L, ifelse(delta_d1 > 0, 1L, 0L)),
    rising_streak = slider::slide_int(
      rising_run,
      ~ {
        if (length(.x) == 0) {
          0L
        } else {
          r <- rle(.x)
          idx <- cumsum(r$lengths)
          ifelse(any(idx == length(.x) & r$values == 1), r$lengths[idx == length(.x)], 0L)
        }
      },
      .before = 6
    ),
    changepoint = ifelse(
      sign(delta_d1) != sign(dplyr::lag(delta_d1, 1)) &
        !is.na(delta_d1) &
        !is.na(dplyr::lag(delta_d1, 1)),
      TRUE, FALSE
    )
  ) |>
  dplyr::ungroup()

# ---------------- Exports per suburb -----------------------------------------------------------
subs_list <- unique(trend$suburb)
message("Exporting per-suburb plans & charts…")

for (s in subs_list) {
  df <- trend |>
    dplyr::filter(suburb == s)

  clean_name <- stringr::str_replace_all(s, "[^A-Za-z0-9]+", "_")

  readr::write_csv(df, file.path(out_dir, paste0("plan_", clean_name, ".csv")))

  g <- ggplot2::ggplot(df, ggplot2::aes(date, total_score)) +
    ggplot2::geom_line() +
    ggplot2::geom_point(ggplot2::aes(shape = changepoint)) +
    ggplot2::geom_hline(yintercept = c(40, 60, 80), linetype = "dashed") +
    ggplot2::labs(
      title = paste0(s, " — 7-Day Risk (ESC or Dust, whichever higher)"),
      x = NULL,
      y = "Risk score (0–100)"
    ) +
    ggplot2::theme_minimal(base_size = 11)

  ggplot2::ggsave(
    file.path(out_dir, paste0("trend_", clean_name, ".png")),
    g, width = 8.5, height = 4.8, dpi = 144
  )
}

# ---------------- High-risk calendar (ICS) -----------------------------------------------------
ics <- c("BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//CTRL//Suburb Risk//EN")

high <- trend |>
  dplyr::filter(pmax(esc_score, dust_score) >= calendar_threshold)

if (nrow(high)) {
  add <- purrr::pmap_chr(
    list(high$suburb, high$date, high$risk_band, high$actions),
    function(sb, dt, band, act) {
      uid <- paste0(digest::digest(paste(sb, dt, band)), "@ctrl")
      title <- glue::glue("{sb}: {band} risk")
      ics_event(uid, title, format(dt, "%Y%m%d"), act)
    }
  )
  ics <- c(ics, add)
}

ics <- c(ics, "END:VCALENDAR")
writeLines(ics, file.path(out_dir, "High-Risk.ics"))

# ---------------- Leaflet map (latest day view) ------------------------------------------------
latest_day <- Sys.Date()

latest_pts <- trend |>
  dplyr::filter(date == latest_day) |>
  dplyr::group_by(suburb, latitude, longitude) |>
  dplyr::summarise(
    esc = max(esc_score, na.rm = TRUE),
    dust = max(dust_score, na.rm = TRUE),
    band = dplyr::first(risk_band),
    actions = dplyr::first(actions),
    .groups = "drop"
  ) |>
  sf::st_as_sf(coords = c("longitude", "latitude"), crs = 4326)

pal <- leaflet::colorFactor(
  palette = c(
    "Moderate" = "#9ecae1",
    "Elevated" = "#fec44f",
    "High" = "#fb6a4a",
    "Severe" = "#a50f15"
  ),
  levels = c("Moderate", "Elevated", "High", "Severe")
)

leaf <- leaflet::leaflet(latest_pts) |>
  leaflet::addProviderTiles(leaflet::providers$CartoDB.Positron) |>
  leaflet::addCircleMarkers(
    radius = 7, stroke = FALSE, fillOpacity = 0.9,
    color = ~pal(band),
    label = ~paste0(suburb, " — ESC ", esc, " | Dust ", dust),
    popup = ~sprintf(
      "<b>%s</b><br/>ESC: %s | Dust: %s<br/><i>%s</i>",
      suburb, esc, dust, actions
    )
  ) |>
  leaflet::addLegend(
    "bottomright", pal = pal, values = ~band,
    title = paste0("Risk (", latest_day, ")")
  )

htmlwidgets::saveWidget(
  leaf, file.path(out_dir, "map.html"), selfcontained = TRUE
)

message("Done. Outputs in: ", normalizePath(out_dir))
