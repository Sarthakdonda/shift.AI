// Cache only a public offline explanation. Account and project responses stay network-only.
self.addEventListener('install',event=>{event.waitUntil(caches.open('shift-public-v1').then(cache=>cache.add('/offline.html')));self.skipWaiting();});
self.addEventListener('activate',event=>{event.waitUntil(self.clients.claim());});
self.addEventListener('fetch',event=>{if(event.request.mode==='navigate')event.respondWith(fetch(event.request).catch(()=>caches.match('/offline.html')));});
