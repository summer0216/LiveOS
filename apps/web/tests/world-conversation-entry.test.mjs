import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
import { runInNewContext } from 'node:vm';
import ts from 'typescript';
import * as placeContext from '../features/first-reality-runtime/placeContext.ts';
import * as scale from '../lib/geographicScaleContract.ts';
import * as presentationContract from '../lib/runtimePresentationContract.ts';
import * as worldConsequence from '../lib/worldConsequence.ts';
import * as surfacePolicy from '../features/unified-surface/presentationPolicy.ts';

const require = createRequire(import.meta.url);
const tick = () => new Promise((resolve) => setImmediate(resolve));

// Exercise the production hook/component with controlled hooks and transport;
// timers, SSE completion and rerenders are explicit so no browser is required.
function hooks() {
  const slots = [];
  let cursor = 0;
  const effects = [];
  return {
    begin() { cursor = 0; },
    flush() { effects.splice(0).forEach((effect) => effect()); },
    useState(initial) {
      const slot = cursor++;
      if (!(slot in slots)) slots[slot] = typeof initial === 'function' ? initial() : initial;
      return [slots[slot], (value) => {
        slots[slot] = typeof value === 'function' ? value(slots[slot]) : value;
      }];
    },
    useRef(initial) {
      const slot = cursor++;
      if (!(slot in slots)) slots[slot] = { current: initial };
      return slots[slot];
    },
    useMemo(fn) { return fn(); },
    useCallback(fn) { return fn; },
    useEffect(fn, deps) {
      const slot = cursor++;
      const old = slots[slot];
      if (!old || deps.some((value, i) => !Object.is(value, old.deps[i]))) {
        const next = { deps, cleanup: null };
        slots[slot] = next;
        effects.push(() => { old?.cleanup?.(); next.cleanup = fn(); });
      }
    },
  };
}

function load(relativePath, dependencies, globals = {}) {
  const source = readFileSync(new URL(relativePath, import.meta.url), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX,
    target: ts.ScriptTarget.ES2022, esModuleInterop: true,
  } }).outputText;
  const loaded = { exports: {} };
  runInNewContext(compiled, {
    module: loaded, exports: loaded.exports,
    require: (name) => name === '@/lib/runtimePresentationContract' ? presentationContract : name === './presentationPolicy' ? surfacePolicy : name in dependencies ? dependencies[name] : require(name),
    console, ...globals,
    AbortController,
  });
  return loaded.exports.default ?? loaded.exports;
}

function elements(tree, type) {
  if (!tree || typeof tree !== 'object') return [];
  if (Array.isArray(tree)) return tree.flatMap((child) => elements(child, type));
  return [
    ...(tree.type === type ? [tree] : []),
    ...elements(tree.props?.children, type),
  ];
}

for (const outcome of ['ready', 'grounding-timeout', 'map-timeout', 'world-timeout']) {
test(`First Reality ${outcome}: direct reveal or bounded retry without SSE completion`, async () => {
  const react = hooks();
  const frames = [];
  const timers = new Map();
  const cameraCalls = [];
  const home = {
    id: 'home', conversation_id: 'fresh', title: '当前住所',
    provenance: 'USER_PROVIDED', geographic_status: 'GROUNDED',
    geographic_precision: 'PLACE', lng: 104, lat: 31,
  };
  let properties = [];
  let request;
  let complete;
  const Runtime = load('../features/first-reality-runtime/index.ts', {
    react, './placeContext': placeContext,
    '@/lib/createClientId': { createClientId: () => 'fresh' },
    '@/lib/geographicScaleContract': scale,
    '@/lib/decisionGeographyState': {
      isGroundedDecisionGeography: () => false, isCurrentExpressionReferent: () => false,
      decisionGeographyFingerprint: () => null, shouldApplyObservedDecisionGeography: () => false,
    },
    '@/services/chat': {
      getConversationHistory: async () => ({ messages: [] }),
      streamMessage: (options) => {
        request = options;
        return new Promise((resolve, reject) => {
          complete = resolve;
          options.signal.addEventListener('abort', () => reject(new Error('aborted')), { once: true });
        });
      },
    },
    '@/services/profile': { getLivingProfile: async () => null },
    '@/services/property': {
      getProperties: async () => properties,
      establishPlaceContext: async () => {},
    },
    '@/services/decisionGeography': { getDecisionGeography: async () => null },
    '@/services/possibleLife': { getPossibleLives: async () => [] },
  }, {
    navigator: {},
    window: {
      history: { replaceState() {} },
      setTimeout(fn, delay) { timers.set(delay, fn); return delay; },
      clearTimeout(id) { timers.delete(id); },
      requestAnimationFrame(fn) { frames.push(fn); return frames.length; },
      cancelAnimationFrame() {},
    },
    console: { ...console, info() {}, error() {} },
  });
  const presentationAnchor = { current: null };
  const render = () => { react.begin(); const result = Runtime({ initialConversationId: '', placeAnchorRef: presentationAnchor }); react.flush(); return result; };
  let runtime = render();
  assert.equal(runtime.placeAnchorRef, presentationAnchor);
  const mountedAnchor = { presentation: 'replacement UI anchor' };
  presentationAnchor.current = mountedAnchor;
  runtime.onCameraReady((...args) => cameraCalls.push(args));
  const pending = runtime.submit('我住在当前住所');
  runtime = render();
  assert.equal(runtime.phase, 'forming');
  assert.equal(frames.length, 0, 'no admitted Reality means no reveal');
  if (outcome === 'grounding-timeout') {
    timers.get(90_000)();
    await pending;
    runtime = render();
    assert.equal(runtime.firstOpenStage, 'entry');
    assert.equal(runtime.isSubmittingExpression, false);
    assert.equal(runtime.authoritativeReality, null);
    assert.equal(cameraCalls.length, 0);
    return;
  }
  properties = [home];
  request.onWorldStateReady('current-turn');
  await tick();
  runtime = render();
  assert.equal(runtime.phase, 'grounding');
  assert.equal(frames.length, 0, 'Grounding alone cannot reveal an unready map');
  if (outcome === 'map-timeout') {
    timers.get(90_000)();
    await pending;
    runtime = render();
    assert.equal(runtime.firstOpenStage, 'entry');
    assert.equal(runtime.isSubmittingExpression, false);
    assert.equal(runtime.authoritativeReality.identity, home.title, 'timeout preserves admitted Reality');
    assert.equal(cameraCalls.length, 0);
    request.onWorldStateReady('stale-turn');
    complete();
    await tick();
    assert.equal(render().firstOpenStage, 'entry', 'late SSE cannot reveal the expired turn');
    return;
  }
  runtime.onGroundReadyChange(true);
  render();
  assert.equal(frames.length, 1, 'map readiness directly schedules the reveal');
  frames.shift()();
  runtime = render();
  assert.equal(runtime.firstOpenStage, 'world');
  assert.equal(timers.has(90_000), false, 'reveal ends the readiness deadline while SSE continues');
  assert.equal(cameraCalls.length, 1);
  assert.equal(cameraCalls[0][3], mountedAnchor, 'Runtime frames the presentation-owned mounted anchor');
  assert.equal(JSON.stringify(cameraCalls[0][0]), JSON.stringify(runtime.authoritativeReality.center));
  if (outcome === 'world-timeout') {
    runtime.onWorldSettled();
    runtime = render();
    assert.equal(runtime.isSubmittingExpression, false, 'formed World releases the first request before SSE');
    const previousRequest = request;
    const previousSignal = request.signal;
    const nextPending = runtime.submit('附近吃饭方便吗？');
    runtime = render();
    assert.equal(previousSignal.aborted, true, 'a newer Expression cancels the older stream');
    const currentMessages = JSON.stringify(runtime.messages);
    previousRequest.onChunk('stale reply');
    assert.equal(JSON.stringify(render().messages), currentMessages, 'cancelled SSE cannot append to the current Conversation');
    assert.equal(runtime.isSubmittingExpression, true);
    timers.get(90_000)();
    await Promise.all([pending, nextPending]);
    runtime = render();
    assert.equal(runtime.phase, 'formed');
    assert.equal(runtime.authoritativeReality.identity, home.title);
    assert.equal(runtime.isSubmittingExpression, false, 'World request timeout restores the entry');
    return;
  }
  complete();
  await pending;
});
}

test('one Expression Entry moves into World and accepts second and third expressions', async () => {
  const react = hooks();
  const timers = new Map();
  const submitted = [];
  let complete;
  const Experience = load('../features/first-open/index.tsx', {
    react,
    './FirstOpen.module.css': { __esModule: true, default: new Proxy({}, { get: (_, key) => key }) },
  }, { window: {
    setTimeout: (fn, delay) => { timers.set(delay, fn); return delay; },
    clearTimeout: (id) => timers.delete(id),
  } });
  let props = {
    stage: 'world', worldFormed: false, isSubmittingExpression: false,
    submittedExpression: '我住在当前住所', groundedIdentity: '当前住所',
    placeAnchorRef: { current: null }, map: 'same map', worldProjection: 'same anchor',
    onGroundingSettled() {},
    onWorldSettled() { props.worldFormed = true; },
    onSubmit(expression) {
      submitted.push(expression);
      return new Promise((resolve) => { complete = resolve; });
    },
  };
  const render = () => { react.begin(); const tree = Experience(props); react.flush(); return tree; };
  let tree = render();
  assert.equal(elements(tree, 'textarea').length, 1);
  assert.equal(elements(tree, 'textarea')[0].props.readOnly, false);
  assert.equal(tree.props['data-world-entry'], true, 'entry is already at the bottom during reveal');
  assert.equal(elements(tree, 'textarea')[0].props.value, '');
  elements(tree, 'textarea')[0].props.onChange({ target: { value: '后续表达草稿' } });
  tree = render();
  timers.get(3200)();
  tree = render();
  assert.equal(elements(tree, 'textarea')[0].props.value, '后续表达草稿', 'World formation does not erase newly typed content');
  elements(tree, 'textarea')[0].props.onChange({ target: { value: '' } });
  tree = render();
  assert.equal(tree.props['data-world-entry'], true);
  assert.equal(tree.props['data-frame'], 'world');
  for (const expression of ['附近吃饭方便吗？', '交通呢？']) {
    elements(tree, 'textarea')[0].props.onFocus();
    tree = render();
    assert.equal(tree.props['data-entry-frame'], 'focus');
    elements(tree, 'textarea')[0].props.onChange({ target: { value: expression } });
    tree = render();
    assert.equal(tree.props['data-entry-frame'], 'typing');
    const button = elements(tree, 'button')[0];
    assert.equal(button.props.disabled, false);
    assert.equal(button.props['aria-label'], '提交表达');
    button.props.onClick();
    // Repeated Enter in the same turn must not duplicate submission.
    elements(tree, 'textarea')[0].props.onKeyDown({ key: 'Enter', preventDefault() {} });
    props.isSubmittingExpression = true;
    tree = render();
    assert.equal(tree.props['data-frame'], 'world');
    assert.equal(tree.props['data-entry-frame'], 'transmitting');
    assert.equal(elements(tree, 'textarea')[0].props.readOnly, false, 'World can accept typing while the current turn finishes');
    assert.equal(elements(tree, 'textarea')[0].props.value, '', 'submission clears immediately');
    assert.equal(elements(tree, 'button')[0].props.disabled, true);
    complete();
    await tick();
    props.isSubmittingExpression = false;
    tree = render();
    assert.equal(elements(tree, 'textarea').length, 1);
    assert.equal(elements(tree, 'textarea')[0].props.value, '');
    assert.equal(tree.props['data-entry-frame'], 'ready');
    assert.equal(elements(tree, 'textarea')[0].props.readOnly, false);
  }
  assert.deepEqual(submitted, ['附近吃饭方便吗？', '交通呢？']);
  assert.equal(timers.has(3200), false, 'formed World does not replay reveal');
});

test('World readiness releases the initial Entry lock before SSE; late completion cannot unlock a newer submit', async () => {
  const react = hooks();
  const requests = [];
  const completions = [];
  const Experience = load('../features/first-open/index.tsx', {
    react,
    './FirstOpen.module.css': { __esModule: true, default: new Proxy({}, { get: (_, key) => key }) },
  }, { window: { setTimeout: () => 1, clearTimeout() {} } });
  const props = {
    stage: 'entry', worldFormed: false, isSubmittingExpression: false,
    submittedExpression: null, groundedIdentity: null, placeAnchorRef: { current: null },
    onWorldSettled() {},
    onSubmit(expression) {
      requests.push(expression);
      return new Promise((resolve) => completions.push(resolve));
    },
  };
  const render = () => { react.begin(); const tree = Experience(props); react.flush(); return tree; };
  let tree = render();
  elements(tree, 'textarea')[0].props.onChange({ target: { value: '我住在当前住所' } });
  tree = render();
  elements(tree, 'button')[0].props.onClick();
  props.stage = 'world';
  props.worldFormed = true;
  tree = render(); // first SSE is still pending, but World is ready.
  elements(tree, 'textarea')[0].props.onChange({ target: { value: '附近吃饭方便吗？' } });
  tree = render();
  elements(tree, 'button')[0].props.onClick();
  assert.deepEqual(requests, ['我住在当前住所', '附近吃饭方便吗？']);
  props.isSubmittingExpression = true;
  tree = render();
  completions[0]();
  await tick();
  elements(tree, 'textarea')[0].props.onChange({ target: { value: '交通呢？' } });
  tree = render();
  elements(tree, 'textarea')[0].props.onKeyDown({ key: 'Enter', preventDefault() {} });
  assert.equal(requests.length, 2, 'old SSE completion does not release a newer pending turn');
  props.isSubmittingExpression = false;
  tree = render(); // current turn semantic reconciliation completes, SSE still pending.
  elements(tree, 'textarea')[0].props.onKeyDown({ key: 'Enter', preventDefault() {} });
  assert.equal(requests.length, 3, 'next Expression does not wait for reply SSE completion');
  completions[1]();
  completions[2]();
  await tick();
});

test('First Open click and Enter share submission and block a duplicate in-flight turn', async () => {
  const react = hooks();
  const submitted = [];
  let complete;
  const Experience = load('../features/first-open/index.tsx', {
    react,
    './FirstOpen.module.css': { __esModule: true, default: new Proxy({}, { get: (_, key) => key }) },
  }, { window: { setTimeout: () => 1, clearTimeout() {} } });
  const props = {
    stage: 'entry', submittedExpression: null, groundedIdentity: null,
    placeAnchorRef: { current: null }, onGroundingSettled() {}, onWorldSettled() {},
    onSubmit(expression) {
      submitted.push(expression);
      return new Promise((resolve) => { complete = resolve; });
    },
  };
  const render = () => { react.begin(); const tree = Experience(props); react.flush(); return tree; };
  let tree = render();
  assert.equal(elements(tree, 'textarea')[0].props.readOnly, false);
  assert.equal(elements(tree, 'button')[0].props.disabled, true);
  elements(tree, 'textarea')[0].props.onChange({ target: { value: '我住在当前住所' } });
  tree = render();
  assert.equal(elements(tree, 'button')[0].props.disabled, false);
  elements(tree, 'button')[0].props.onClick();
  tree = render();
  assert.equal(elements(tree, 'textarea')[0].props.value, '');
  const entry = elements(tree, 'div').find((element) => element.props.className === 'expressionEntry');
  assert.equal(entry.props['data-entry-hidden'], true, 'initial submission hides the central entry immediately');
  elements(tree, 'textarea')[0].props.onKeyDown({ key: 'Enter', preventDefault() {} });
  assert.deepEqual(submitted, ['我住在当前住所']);
  complete();
  await tick();
});

test('continuing SSE turns preserve the formed subject, Conversation and camera gate', async () => {
  const react = hooks();
  const home = {
    id: 'home', conversation_id: 'current-conversation', title: '当前住所',
    provenance: 'USER_PROVIDED', geographic_status: 'GROUNDED',
    geographic_identity: '当前住所', geographic_precision: 'PLACE', lng: 104, lat: 31,
  };
  const requests = [];
  let release;
  let fail;
  let failedReread = false;
  let currentProperties = [home];
  let rereads = 0;
  const Runtime = load('../features/first-reality-runtime/index.ts', {
    react, './placeContext': placeContext,
    '@/lib/createClientId': { createClientId() { throw new Error('must keep existing Conversation'); } },
    '@/lib/geographicScaleContract': scale,
    '@/lib/decisionGeographyState': {
      isGroundedDecisionGeography: () => false, isCurrentExpressionReferent: () => false,
      decisionGeographyFingerprint: () => null, shouldApplyObservedDecisionGeography: () => false,
    },
    '@/services/chat': {
      getConversationHistory: async () => ({ messages: [{ role: 'user', content: '我住在当前住所' }] }),
      streamMessage: (options) => {
        requests.push(options);
        return new Promise((resolve, reject) => { release = resolve; fail = reject; });
      },
    },
    '@/services/profile': { getLivingProfile: async () => null },
    '@/services/property': {
      getProperties: async () => {
        rereads++;
        if (failedReread) throw new Error('reread unavailable');
        return currentProperties;
      },
      establishPlaceContext: async () => {},
    },
    '@/services/decisionGeography': { getDecisionGeography: async () => null },
    '@/services/possibleLife': { getPossibleLives: async () => [] },
  }, {
    navigator: {},
    window: {
      history: { replaceState() {} },
      setTimeout() { return 1; },
      requestAnimationFrame() { throw new Error('continuation must not reorient camera'); },
      clearTimeout() {},
    },
    console: { ...console, info() {}, error() {} },
  });
  const presentationAnchor = { current: null };
  const render = () => { react.begin(); return Runtime({ initialConversationId: home.conversation_id, placeAnchorRef: presentationAnchor }); };
  render(); react.flush(); await tick();
  let runtime = render();
  assert.equal(runtime.phase, 'formed');
  const identity = runtime.authoritativeReality.identity;
  const center = JSON.stringify(runtime.authoritativeReality.center);
  for (const expression of ['附近吃饭方便吗？', '交通呢？']) {
    const pending = runtime.submit(expression);
    runtime = render(); react.flush();
    assert.equal(runtime.phase, 'formed');
    assert.equal(runtime.firstOpenStage, 'world');
    assert.equal(runtime.isSubmittingExpression, true);
    assert.equal(runtime.authoritativeReality.identity, identity);
    assert.equal(JSON.stringify(runtime.authoritativeReality.center), center);
    const request = requests.at(-1);
    assert.equal(request.conversationId, home.conversation_id);
    assert.equal(request.message, expression);
    request.onWorldStateReady('current-turn');
    request.onWorldConsequenceReady();
    await tick();
    runtime = render(); react.flush();
    assert.equal(runtime.isSubmittingExpression, false, 'authoritative turn reread releases entry before SSE completion');
    // A transient empty reread must not erase the already-admitted World subject.
    currentProperties = [];
    release(); await pending;
    runtime = render(); react.flush();
    assert.equal(runtime.phase, 'formed');
    assert.equal(runtime.isSubmittingExpression, false);
    assert.equal(runtime.authoritativeReality.identity, identity);
    assert.equal(JSON.stringify(runtime.authoritativeReality.center), center);
    assert.equal(runtime.submittedExpression, '我住在当前住所');
    currentProperties = [home];
  }
  assert.equal(requests.length, 2);
  assert.ok(rereads >= 5);
  const failedTurn = runtime.submit('再问一句');
  failedReread = true;
  fail(new Error('transport unavailable'));
  await failedTurn;
  runtime = render();
  assert.equal(runtime.phase, 'formed');
  assert.equal(runtime.isSubmittingExpression, false);
  assert.equal(runtime.authoritativeReality.identity, identity);
});

function conversationRuntime(history = [], { failWorldRead = false, failHistory = false } = {}) {
  const react = hooks();
  const requests = [];
  const chat = load('../services/chat.ts', {
    './api': {
      apiFetch: async () => {
        if (failHistory) throw new Error('history unavailable');
        return { conversation_id: 'existing', messages: history };
      },
      apiRequest: async (_path, options) => {
        let output;
        const body = new ReadableStream({ start(controller) { output = controller; } });
        requests.push({
          body: JSON.parse(options.body),
          emit(text) { output.enqueue(new TextEncoder().encode(text)); },
          finish() { output.close(); },
          fail() { output.error(new Error('stream unavailable')); },
        });
        options.signal.addEventListener('abort', () => output.error(new Error('aborted')), { once: true });
        return new Response(body);
      },
    },
    '@/lib/worldConsequence': worldConsequence,
  }, { setTimeout, clearTimeout, TextDecoder });
  const Runtime = load('../features/first-reality-runtime/index.ts', {
    react, './placeContext': placeContext,
    '@/lib/createClientId': { createClientId: () => 'fresh' },
    '@/lib/geographicScaleContract': scale,
    '@/lib/decisionGeographyState': {
      isGroundedDecisionGeography: () => false, isCurrentExpressionReferent: () => false,
      decisionGeographyFingerprint: () => null, shouldApplyObservedDecisionGeography: () => false,
    },
    '@/services/chat': chat,
    '@/services/profile': { getLivingProfile: async () => null },
    '@/services/property': {
      getProperties: async () => { if (failWorldRead) throw new Error('world unavailable'); return []; },
      establishPlaceContext: async () => {},
    },
    '@/services/decisionGeography': { getDecisionGeography: async () => null },
    '@/services/possibleLife': { getPossibleLives: async () => [] },
  }, {
    navigator: {},
    window: {
      setTimeout() { return 1; }, clearTimeout() {}, history: { replaceState() {} },
      requestAnimationFrame() { throw new Error('ungrounded Conversation must not reveal a World'); },
    },
    console: { ...console, info() {}, error() {} },
  });
  const anchor = { current: null };
  const render = () => {
    react.begin();
    const runtime = Runtime({ initialConversationId: history.length || failHistory ? 'existing' : '', placeAnchorRef: anchor });
    react.flush();
    return runtime;
  };
  return { render, requests };
}

test('real SSE progressively presents replies, keeps Conversation ID, and restores without duplication', async () => {
  const { render, requests } = conversationRuntime();
  let runtime = render();
  const first = runtime.submit('你是谁？');
  runtime = render();
  assert.equal(runtime.conversationId, 'fresh');
  assert.equal(runtime.messages[0].content, '你是谁？');
  assert.equal(runtime.isResponding, true);
  await tick();
  requests[0].emit('data: "我是"\n\n');
  await tick();
  assert.equal(render().messages[1].content, '我是');
  requests[0].emit('data: " LiveOS。"\n\n');
  await tick();
  assert.equal(render().messages[1].content, '我是 LiveOS。');
  requests[0].finish(); await first;
  runtime = render();
  assert.equal(runtime.isResponding, false);
  assert.equal(runtime.hasGroundedWorld, false);
  assert.equal(runtime.phase, 'empty');
  const second = runtime.submit('你能帮我做什么？');
  render(); await tick();
  assert.equal(requests[1].body.conversation_id, requests[0].body.conversation_id);
  requests[1].emit('data: "可以一起梳理你的生活选择。"\n\n');
  requests[1].finish(); await second;
  runtime = render();
  assert.equal(runtime.messages.length, 4);
  const persisted = runtime.messages.map(({ role, content }) => ({ role, content }));
  const restored = conversationRuntime(persisted);
  assert.equal(restored.render().isRestoringConversation, true);
  await tick();
  const recovered = restored.render();
  assert.equal(recovered.isRestoringConversation, false);
  assert.equal(JSON.stringify(recovered.messages.map(({ role, content }) => ({ role, content }))), JSON.stringify(persisted));
  assert.equal(new Set(recovered.messages.map((message) => message.id)).size, 4);
  restored.render(); await tick();
  assert.equal(restored.render().messages.length, 4);
});

test('Conversation history recovers independently of World reads and reports history failure', async () => {
  const history = [{ role: 'user', content: '你好' }, { role: 'assistant', content: '你好。' }];
  const restored = conversationRuntime(history, { failWorldRead: true });
  restored.render(); await tick();
  assert.equal(restored.render().messages.length, 2);
  assert.equal(restored.render().isRestoringConversation, false);
  const failed = conversationRuntime([], { failHistory: true });
  failed.render(); await tick();
  assert.equal(failed.render().isRestoringConversation, false);
  assert.ok(failed.render().conversationError);
});

test('a failed SSE keeps partial reply and permits continued expression in the same Conversation', async () => {
  const { render, requests } = conversationRuntime();
  const pending = render().submit('你是谁？');
  render(); await tick();
  requests[0].emit('data: "我是"\n\n'); await tick();
  requests[0].fail(); await pending;
  const runtime = render();
  assert.equal(runtime.isResponding, false);
  assert.ok(runtime.conversationError);
  assert.equal(runtime.messages[1].content, '我是');
  const retry = runtime.submit('继续');
  render(); await tick();
  assert.equal(requests[1].body.conversation_id, 'fresh');
  requests[1].emit('data: "我们继续。"\n\n'); requests[1].finish(); await retry;
  assert.equal(render().conversationError, null);
});

test('Unified Surface retains reveal timing and a continuous Expression Entry', () => {
  const react = hooks();
  const timers = new Map();
  let settled = 0;
  const Surface = load('../features/unified-surface/index.tsx', {
    react, './UnifiedSurface.module.css': new Proxy({}, { get: (_, key) => key }),
    './Conversation': { __esModule: true, default: 'Conversation' }, './ExpressionEntry': { __esModule: true, default: 'ExpressionEntry' },
    '@/features/possible-life-world/RealityAnchorProjection': { __esModule: true, default: 'RealityAnchorProjection' },
  }, { window: { setTimeout(fn, ms) { timers.set(ms, fn); return ms; }, clearTimeout(id) { timers.delete(id); } } });
  const props = {
    requiresCameraAnchor: false, revealStarted: false, revealComplete: false, messages: [], isResponding: false, isSubmittingExpression: false,
    isRestoringConversation: false, conversationError: null, groundedReality: null,
    geographicGroundReady: false, cameraReady: false, consequenceFocus: null,
    mapProjection: null, mapZoom: null, placeAnchorRef: { current: null },
    onSubmit: async () => {}, onWorldSettled: () => { settled++; },
  };
  const render = () => { react.begin(); const tree = Surface(props); react.flush(); return tree; };
  assert.equal(render().props['data-started'], false);
  props.messages = [{ id: 'u', role: 'user', content: '你是谁？' }];
  assert.equal(render().props['data-started'], true);
  assert.equal(elements(render(), 'ExpressionEntry').length, 1);
  assert.equal(timers.size, 0);
  props.groundedReality = { identity: '当前住所', center: { lng: 104, lat: 31 } };
  props.requiresCameraAnchor = true; render();
  assert.equal(timers.size, 0);
  props.geographicGroundReady = true; props.cameraReady = true;
  props.revealStarted = true; render();
  assert.ok(timers.has(presentationContract.WORLD_SETTLE_MS));
  timers.get(presentationContract.WORLD_SETTLE_MS)();
  assert.equal(settled, 1);
  props.revealComplete = true; render();
  assert.equal(timers.size, 0);
});

test('Unified Expression Entry respects IME, Shift+Enter and blocks duplicate submissions', async () => {
  const react = hooks();
  let complete;
  const submissions = [];
  const Entry = load('../features/unified-surface/ExpressionEntry.tsx', {
    react, './UnifiedSurface.module.css': new Proxy({}, { get: (_, key) => key }),
  });
  const props = { disabled: false, onSubmit(value) {
    submissions.push(value);
    return new Promise((resolve) => { complete = resolve; });
  } };
  const render = () => { react.begin(); return Entry(props); };
  elements(render(), 'textarea')[0].props.onChange({ target: { value: '你是谁？' } });
  const keyboard = (overrides = {}) => ({ key: 'Enter', shiftKey: false, nativeEvent: { isComposing: false }, preventDefault() {}, ...overrides });
  elements(render(), 'textarea')[0].props.onKeyDown(keyboard({ nativeEvent: { isComposing: true } }));
  elements(render(), 'textarea')[0].props.onKeyDown(keyboard({ shiftKey: true }));
  assert.equal(submissions.length, 0);
  elements(render(), 'textarea')[0].props.onKeyDown(keyboard());
  render().props.onSubmit({ preventDefault() {} });
  assert.deepEqual(submissions, ['你是谁？']);
  assert.equal(elements(render(), 'textarea')[0].props.value, '');
  complete(); await tick();
  props.disabled = true;
  elements(render(), 'textarea')[0].props.onChange({ target: { value: '继续' } });
  render().props.onSubmit({ preventDefault() {} });
  assert.equal(submissions.length, 1);
});
