import assert from 'node:assert/strict';
import test from 'node:test';

import {
  GEOGRAPHIC_SCALE_CONTRACT,
  decisionGeographyZoom,
  geographicCameraCenterForViewport,
  geographicZoomForViewport,
  homeViewport,
  realityLevelForPrecision,
} from '../lib/geographicScaleContract.ts';

test('a grounded PLACE keeps SEE stable and gives Focus adaptive subject prominence', () => {
  const home = {
    geographic_status: 'GROUNDED', geographic_precision: 'PLACE',
    lng: 103.920730, lat: 30.753792,
  };
  const see = homeViewport(home, 'SEE');
  const focus = homeViewport(home, 'FOCUS');
  assert.deepEqual(see.center, { lng: home.lng, lat: home.lat });
  assert.equal(see.framing.level, 'PLACE');
  assert.equal(see.framing.attention, 'SEE');
  assert.deepEqual(focus.center, see.center);
  assert.equal(focus.framing.level, 'PLACE');
  const compactZoom = geographicZoomForViewport(see.framing, {
    width: 390, height: 700,
  });
  const desktopZoom = geographicZoomForViewport(see.framing, {
    width: 1440, height: 960,
  });
  assert.equal(compactZoom, 15.25);
  assert.equal(desktopZoom, 16.25);
  assert.ok(desktopZoom > compactZoom);
  const focusViewport = {
    width: 1440,
    height: 960,
    insets: { right: 360 },
  };
  const focusedZoom = geographicZoomForViewport(focus.framing, focusViewport);
  assert.equal(focusedZoom, 17.5);
  assert.ok(focusedZoom - desktopZoom >= 1);
  const narrowerReadingLayerZoom = geographicZoomForViewport(focus.framing, {
    width: 1440,
    height: 960,
    insets: { right: 240 },
  });
  assert.equal(narrowerReadingLayerZoom, 17.25);
  assert.notEqual(
    focusedZoom - desktopZoom,
    narrowerReadingLayerZoom - desktopZoom,
  );
  const focusedCenter = geographicCameraCenterForViewport(
    see.center,
    focusedZoom,
    focusViewport,
  );
  assert.ok(focusedCenter.lng > see.center.lng);
  assert.ok(Math.abs(focusedCenter.lat - see.center.lat) < 1e-9);
  const area = homeViewport({ ...home, geographic_precision: 'AREA' }, 'SEE');
  assert.equal(geographicZoomForViewport(area.framing, { width: 390, height: 700 }), 13.5);
  assert.equal(realityLevelForPrecision('COMMUNITY'), 'RESIDENCE');
  assert.equal(realityLevelForPrecision('STREET'), 'PLACE');
  assert.equal(decisionGeographyZoom({ geographic_scope: 'REGION' }), 6.5);
  assert.equal(decisionGeographyZoom({ geographic_scope: 'CITY' }), 10.5);
  assert.equal(decisionGeographyZoom({ geographic_scope: 'LOCAL' }), 13.5);
  assert.equal(GEOGRAPHIC_SCALE_CONTRACT.PLACE.FOCUS, GEOGRAPHIC_SCALE_CONTRACT.PLACE.SEE);
  assert.equal(homeViewport({ ...home, geographic_status: 'UNRESOLVED' }, 'FOCUS'), null);
  assert.equal(homeViewport({ ...home, lng: null }, 'FOCUS'), null);
});
