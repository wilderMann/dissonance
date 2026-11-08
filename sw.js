// Dissonance service worker: network first (short timeout), cache as fallback -> songs opened once work offline.
const CACHE = "dissonance-v18";
const SHELL = ["./", "manifest.webmanifest", "icon.svg", "icon-192.png", "icon-512.png", "icon-maskable-512.png", "nosleep.mp4", "nosleep.webm", "chords.json"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

function timeout(ms) { return new Promise((_, rej) => setTimeout(() => rej(new Error("timeout")), ms)); }

self.addEventListener("fetch", e => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin) return;
  const cacheable = url.pathname === "/" || url.pathname === "/index.html" || url.pathname.startsWith("/api/songs") || ((url.pathname.startsWith("/api/books") || url.pathname.startsWith("/api/shared")) && !url.pathname.includes("/export"))
    || SHELL.some(p => url.pathname === "/" + p);
  if (!cacheable) return;
  const key = url.pathname === "/index.html" ? new Request("./") : req;
  e.respondWith((async () => {
    const cache = await caches.open(CACHE);
    try {
      const res = await Promise.race([fetch(req), timeout(4000)]);
      if (res.ok) cache.put(key, res.clone());
      return res;
    } catch (err) {
      const hit = await cache.match(key, { ignoreSearch: true });
      if (hit) return hit;
      if (url.pathname.startsWith("/api/")) {
        return new Response(JSON.stringify({ ok: false, error: "Offline – dieses Lied ist auf dem Gerät nicht gespeichert." }),
          { status: 503, headers: { "Content-Type": "application/json" } });
      }
      throw err;
    }
  })());
});
