self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("push", (event) => {
  const payload = event.data?.json?.() ?? {};
  const title = payload.title ?? "CouncilSense";
  const options = {
    body: payload.body ?? "You have a new CouncilSense update.",
    data: payload.data ?? {},
  };

  event.waitUntil(self.registration.showNotification(title, options));
});
