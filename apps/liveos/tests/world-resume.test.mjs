import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import vm from 'node:vm';
import test from 'node:test';
import { selectEnvironmentProjection } from '../features/living-world/selectEnvironmentProjection.ts';
import { selectGroundedPlace } from '../features/living-world/groundedPlace.ts';

const require = createRequire(import.meta.url);
const React = require('react');
const ts = require('typescript');
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};
const flush = () => new Promise((resolve) => setImmediate(resolve));
function load(path, dependencies) {
  const compiled = { exports: {} };
  const code = ts.transpileModule(readFileSync(new URL(path, import.meta.url), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  vm.runInNewContext(`(function(require,module,exports){${code}\n})`, {
    AbortController, console: { error() {} },
  })((name) => dependencies[name] ?? require(name), compiled, compiled.exports);
  return compiled.exports;
}
function realityHook() {
  let value = null, effect, dependencies, cleanup;
  const requests = [];
  const { useGroundedPlace: readHook } = load('../features/living-world/useGroundedPlace.ts', {
    react: {
      useState: () => [value, (next) => { value = next; }],
      useEffect(next, deps) {
        if (JSON.stringify(deps) !== JSON.stringify(dependencies)) {
          dependencies = deps;
          effect = next;
        }
      },
    },
    '../../infrastructure/groundedRealityApi': { getProperties(id, signal) {
      const request = { ...deferred(), id, signal };
      requests.push(request);
      return request.promise;
    } },
    './groundedPlace': { selectGroundedPlace },
  });
  return {
    read: (id = 'saved', refresh = 0) => readHook(id, refresh),
    commit() { if (effect) { cleanup?.(); cleanup = effect(); effect = null; } },
    requests,
  };
}
const property = {
  conversation_id: 'saved', provenance: 'USER_PROVIDED', decision_state: 'ACTIVE',
  title: '已确认地点', geographic_identity: '真实地点身份', geographic_precision: 'PLACE',
  geographic_status: 'GROUNDED', lng: 116.32, lat: 39.68,
};

test('pending reality differs from resolved absence; failure terminates restoration and exposes error', async () => {
  for (const failure of [false, true]) {
    const h = realityHook();
    assert.equal(h.read().isRestoring, true);
    h.commit();
    if (failure) h.requests[0].reject(new Error('offline'));
    else h.requests[0].resolve([]);
    await flush();
    assert.equal(h.read().isRestoring, false);
    assert.equal(h.read().place, null);
    assert.equal(Boolean(h.read().error), failure);
  }
});
test('refresh preserves current world while reading; stale requests cannot restore another conversation', async () => {
  const h = realityHook();
  assert.equal(h.read('').isRestoring, false);
  h.read(); h.commit(); h.requests[0].resolve([property]); await flush();
  assert.equal(h.read().place.identity, property.geographic_identity);
  assert.equal(h.read('saved', 1).isRestoring, false);
  h.commit();
  assert.equal(h.read('other').place, null);
  h.commit();
  h.requests[1].resolve([property]); await flush();
  assert.equal(h.read('other').isRestoring, true);
  h.requests[2].resolve([]); await flush();
  assert.equal(h.read('other').isRestoring, false);
});

test('saved surface waits for both history and reality, then renders world directly or conversation', () => {
  let session, reality;
  const Surface = load('../features/first-conversation/FirstConversationExperience.tsx', {
    react: { ...React, useState: (initial) => [initial, () => {}] },
    'next/image': { default: 'image' },
    '../../components/brand/Wordmark': { default: 'wordmark' },
    '../../../../docs/03_Design/UI_Library/ Screens/01_First_Open/assets/first-open-mountain-background.png': {},
    '../../runtime/useConversationSession': { useConversationSession: () => session },
    '../living-world/selectEnvironmentProjection': { selectEnvironmentProjection },
    '../living-world/useGroundedPlace': { useGroundedPlace: () => reality },
    '../living-world/WorldFocusSurface': { default: 'world' },
    './ConversationTranscript': { default: 'transcript' },
    './ExpressionComposer': { default: 'composer' },
    './first-conversation.module.css': { default: {} },
  }).default;
  session = { conversationId: 'saved', messages: [{ content: 'restored' }], isRestoring: false };
  reality = { place: null, isRestoring: true };
  const render = (initialConversationId = 'saved') => Surface({ initialConversationId });
  assert.equal(render().props['aria-busy'], 'true'); // History completed first.
  reality = { place: property, isRestoring: false };
  session.isRestoring = true;
  assert.equal(render().props['aria-busy'], 'true'); // Reality completed first.
  session.isRestoring = false;
  assert.equal(render().props.children.type, 'world');
  reality = { place: null, isRestoring: false };
  assert.equal(render().props.children.props.children[2].type, 'transcript');
  reality.error = '无法恢复地点，请刷新重试。';
  assert.equal(render().props.children.props.children[3].props.children[0].props.children, reality.error);
  session = { conversationId: '', messages: [], isRestoring: false };
  reality = { place: null, isRestoring: false };
  assert.equal(render('').props.children.props.children[2].type, 'section');
});
