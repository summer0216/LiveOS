import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { deriveSurfacePresentation } from '../features/unified-surface/presentationPolicy.ts';

const groundedReality = {
  identity: '首次住所', center: { lng: 104, lat: 31 }, focusZoom: 15,
  worldFraming: { level: 'PLACE', attention: 'SEE' },
};
const facts = (overrides = {}) => ({
  messages: [], isResponding: false, isRestoringConversation: false,
  isSubmittingExpression: false, groundedReality: null, requiresCameraAnchor: false, revealStarted: false, revealComplete: false,
  geographicGroundReady: false, cameraReady: false, consequenceFocus: null,
  ...overrides,
});

test('World requires admitted Reality, map/camera readiness and an initiated reveal', () => {
  for (const reality of [null, groundedReality]) {
    for (const revealStarted of [false, true]) {
      for (const geographicGroundReady of [false, true]) {
        for (const cameraReady of [false, true]) {
          const policy = deriveSurfacePresentation(facts({ groundedReality: reality, revealStarted, geographicGroundReady, cameraReady }));
          const visible = Boolean(reality && geographicGroundReady && cameraReady && revealStarted);
          assert.equal(policy.worldVisible, visible);
          assert.equal(policy.anchorVisible, visible);
          assert.equal(policy.reportRevealCompletion, visible);
        }
      }
    }
  }
});

test('camera-only anchor mounts before readiness; restored World waits for the live map', () => {
  const grounding = deriveSurfacePresentation(facts({ groundedReality, requiresCameraAnchor: true }));
  assert.equal(grounding.anchorMounted, true);
  assert.equal(grounding.worldVisible, false);
  const restored = deriveSurfacePresentation(facts({ groundedReality, requiresCameraAnchor: true, revealStarted: true, revealComplete: true }));
  assert.equal(restored.anchorMounted, true);
  assert.equal(restored.worldVisible, false);
  assert.equal(restored.reportRevealCompletion, false);
});

test('Conversation and input policy use data and Runtime constraints without First Open Stage', () => {
  assert.equal(deriveSurfacePresentation(facts()).started, false);
  assert.equal(deriveSurfacePresentation(facts({ messages: [{ id: 'u', role: 'user', content: '你好' }] })).started, true);
  assert.equal(deriveSurfacePresentation(facts({ isRestoringConversation: true })).started, true);
  for (const flag of ['isResponding', 'isRestoringConversation', 'isSubmittingExpression']) {
    assert.equal(deriveSurfacePresentation(facts({ [flag]: true })).entryDisabled, true);
  }
  assert.equal(deriveSurfacePresentation(facts({ requiresCameraAnchor: true })).entryDisabled, true);
  assert.equal(deriveSurfacePresentation(facts({ requiresCameraAnchor: true, revealStarted: true })).entryDisabled, true);
  assert.equal(deriveSurfacePresentation(facts({ groundedReality, requiresCameraAnchor: true, revealStarted: true, revealComplete: true })).entryDisabled, false);
});

test('explicit consequence focus changes emphasis without replacing the first Reality or revealing an ungrounded World', () => {
  const ready = facts({ groundedReality, requiresCameraAnchor: true, revealStarted: true, revealComplete: true, geographicGroundReady: true, cameraReady: true });
  assert.equal(deriveSurfacePresentation(ready).visualEmphasis, 'conversation');
  const focused = { ...ready, consequenceFocus: { focusPropertyId: 'another-property' } };
  const before = JSON.stringify(focused);
  assert.equal(deriveSurfacePresentation(focused).visualEmphasis, 'world');
  assert.equal(focused.groundedReality, groundedReality);
  assert.equal(JSON.stringify(focused), before, 'policy does not mutate Runtime facts');
  assert.equal(deriveSurfacePresentation({ ...focused, groundedReality: null }).worldVisible, false);
  assert.equal(deriveSurfacePresentation({ ...ready, consequenceFocus: {} }).visualEmphasis, 'conversation');
});

test('Conversation continues while an admitted World remains visible', () => {
  const continuing = deriveSurfacePresentation(facts({
    groundedReality, requiresCameraAnchor: true, revealStarted: true, revealComplete: true, geographicGroundReady: true, cameraReady: true,
    isResponding: true, messages: [{ id: 'u', role: 'user', content: '继续' }],
  }));
  assert.equal(continuing.started, true);
  assert.equal(continuing.worldVisible, true);
  assert.equal(continuing.anchorVisible, true);
  assert.equal(continuing.reportRevealCompletion, false);
});


test('page maps Runtime lifecycle into facts with identical World, Anchor, input and handshake behavior', () => {
  const page = readFileSync(new URL('../app/page.tsx', import.meta.url), 'utf8');
  const mapping = Object.fromEntries(['requiresCameraAnchor', 'revealStarted', 'revealComplete'].map((name) => {
    const expression = page.match(new RegExp(name + '=\\{([^}]+)\\}'))?.[1];
    assert.ok(expression, name + ' must be mapped at the page boundary');
    return [name, new Function('phase', 'return (' + expression + ')')];
  }));
  for (const phase of ['empty', 'forming', 'grounding', 'revealing', 'formed']) {
    for (const reality of [null, groundedReality]) {
      for (const geographicGroundReady of [false, true]) {
        for (const cameraReady of [false, true]) {
          const mapped = Object.fromEntries(Object.entries(mapping).map(([name, derive]) => [name, derive(phase)]));
          const input = facts({ groundedReality: reality, geographicGroundReady, cameraReady, ...mapped });
          const policy = deriveSurfacePresentation(input);
          const visible = Boolean(reality && geographicGroundReady && cameraReady && ['revealing', 'formed'].includes(phase));
          assert.equal(policy.worldVisible, visible, phase);
          assert.equal(policy.anchorVisible, visible, phase);
          assert.equal(policy.anchorMounted, Boolean(reality && ['grounding', 'revealing', 'formed'].includes(phase)), phase);
          assert.equal(policy.reportRevealCompletion, visible && phase === 'revealing', phase);
          assert.equal(policy.entryDisabled, ['grounding', 'revealing'].includes(phase), phase);
        }
      }
    }
  }
});

test('readiness contract has independent facts and no Runtime feature or phase dependency', () => {
  const source = readFileSync(new URL('../features/unified-surface/presentationPolicy.ts', import.meta.url), 'utf8');
  assert.doesNotMatch(source, /features\/first-reality-runtime|FirstRealityPhase|revealPhase|'grounding'|'revealing'|'formed'/);
  const ready = facts({ groundedReality, geographicGroundReady: true, cameraReady: true, revealStarted: true });
  assert.equal(deriveSurfacePresentation(ready).reportRevealCompletion, true);
  assert.equal(deriveSurfacePresentation({ ...ready, revealComplete: true }).reportRevealCompletion, false);
  assert.equal(deriveSurfacePresentation({ ...ready, revealComplete: true }).worldVisible, true);
  assert.equal(deriveSurfacePresentation({ ...ready, revealStarted: false, revealComplete: true }).worldVisible, false);
});
