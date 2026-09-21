import assert from 'node:assert/strict';
import test from 'node:test';

import { focusedHomeViewport } from '../lib/focusedHomeViewport.ts';

test('one grounded focused Home reveals local geography without inventing a camera', () => {
  const home = {
    geographic_status: 'GROUNDED', lng: 103.917856, lat: 30.754633,
  };
  const viewport = focusedHomeViewport(home);
  assert.deepEqual(viewport.center, { lng: home.lng, lat: home.lat });
  assert.ok(viewport.zoom > 12.5 && viewport.zoom < 17);
  assert.equal(focusedHomeViewport({ ...home, geographic_status: 'UNRESOLVED' }), null);
  assert.equal(focusedHomeViewport({ ...home, lng: null }), null);
});
