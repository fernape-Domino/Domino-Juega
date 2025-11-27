const CACHE_NAME = 'domino-juega-v1';
const URLS_TO_CACHE = [
  '/',
  '/players',
  '/teams',
  '/matches',
  '/matches/new'
];

// Instalar: guardar en caché algunos recursos básicos
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(URLS_TO_CACHE).catch(() => null);
    })
  );
});

// Activar: limpiar cachés viejas si cambias el nombre del CACHE_NAME
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys
          .filter(key => key !== CACHE_NAME)
          .map(key => caches.delete(key))
      );
    })
  );
});

// Fetch: servir desde caché cuando sea posible
self.addEventListener('fetch', event => {
  const request = event.request;

  // Solo manejamos peticiones GET
  if (request.method !== 'GET') {
    return;
  }

  event.respondWith(
    caches.match(request).then(response => {
      // Si está en caché, lo devolvemos
      if (response) {
        return response;
      }

      // Si no, lo pedimos a la red y opcionalmente lo guardamos
      return fetch(request).then(networkResponse => {
        // No cacheamos llamadas a API POST, etc., solo páginas estáticas/GET
        if (!networkResponse || networkResponse.status !== 200 || networkResponse.type !== 'basic') {
          return networkResponse;
        }

        const responseToCache = networkResponse.clone();
        caches.open(CACHE_NAME).then(cache => {
          cache.put(request, responseToCache);
        });

        return networkResponse;
      }).catch(() => {
        // Aquí podrías devolver una página offline personalizada si quieres
        return new Response('Sin conexión y este recurso no está en caché.', {
          status: 503,
          headers: { 'Content-Type': 'text/plain' }
        });
      });
    })
  );
});
