// Map tile configuration for docs/js/timelineMap.js.
//
// HOW TO ADD YOUR MAPBOX API KEY
// ------------------------------
// 1. Go to https://account.mapbox.com/ and sign in (create a free account if
//    you do not have one -- the free tier covers well over 50,000 map views
//    per month).
// 2. Open https://account.mapbox.com/access-tokens/ .
// 3. Copy your "Default public token" (starts with pk.), or create a new
//    token and give it only the PUBLIC scopes: maps:read, styles:read,
//    tiles:read (NEVER paste a secret_token that starts with sk.).
// 4. Paste the token between the quotes below, save this file, refresh the
//    browser page. That is all -- no other file needs to change.
//
// While the token is empty, the map falls back to free key-less tiles
// (ESRI World Street Map), so the site keeps working without a key.
//
// NOTE: this token is visible to anyone who loads the page. Public tokens are
// designed for exactly that and can be restricted by domain/URL in the
// Mapbox dashboard (recommended: set a "URL限 restrictions" -> your GitHub
// Pages URL, e.g. https://jesnyder.github.io/).

window.MAP_CONFIG = {
  mapboxToken: "pk.eyJ1IjoiamVzc2ljYTU5MiIsImEiOiJjbXZoY2tldjcwOGN1MndxNTUydHA4cTZrIn0.BHiABV3HCG-jPp-ZuS8lfg",
};
