export async function loadDemoData() {
  const files = [
    { key: 'detection', path: '/demo/detection.geojson' },
    { key: 'corridor', path: '/demo/corridor.geojson' },
    { key: 'origin', path: '/demo/origin.json' },
    { key: 'suspects', path: '/demo/suspects.geojson' },
    { key: 'dossier', path: '/demo/dossier.json' },
  ];

  const results = {};

  for (const { key, path } of files) {
    const response = await fetch(path);
    if (!response.ok) {
      throw new Error(`Failed to load demo data: ${path}`);
    }
    results[key] = await response.json();
  }

  return results;
}
