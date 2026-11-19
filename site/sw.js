"use strict";
// Offline cache for the step-by-step guide. site/build.py fills in the cache name (a hash over
// every precached file) and the precache list, so each content change installs a fresh cache.

const CACHE = "{{CACHE_NAME}}";
const PRECACHE = {{PRECACHE}};
const SCOPE = new URL(self.registration.scope).pathname;
const PAGE = "build-steps.html";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll(PRECACHE.map((path) => new Request(path, { cache: "reload" }))))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((key) => key.startsWith("guide-") && key !== CACHE).map((key) => caches.delete(key))),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin || !url.pathname.startsWith(SCOPE)) return;
  const path = url.pathname.slice(SCOPE.length);
  if (!PRECACHE.includes(path)) return;
  if (path === PAGE) {
    // The page: network first so a new deploy shows at once; the cached copy when offline.
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE).then((cache) => cache.put(path, copy));
          }
          return response;
        })
        .catch(() => caches.open(CACHE).then((cache) => cache.match(path))),
    );
    return;
  }
  event.respondWith(
    caches.open(CACHE).then((cache) => cache.match(path).then((hit) => hit || fetch(request))),
  );
});
