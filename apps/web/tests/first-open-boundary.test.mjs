import assert from 'node:assert/strict';
import test from 'node:test';
import { existsSync, readFileSync } from 'node:fs';

const page = readFileSync(new URL('../app/page.tsx', import.meta.url), 'utf8');
const firstOpen = readFileSync(
  new URL('../features/first-open/index.tsx', import.meta.url),
  'utf8',
);
const firstOpenStyles = readFileSync(
  new URL('../features/first-open/FirstOpen.module.css', import.meta.url),
  'utf8',
);
const firstRealityRuntime = readFileSync(
  new URL('../features/first-reality-runtime/index.ts', import.meta.url),
  'utf8',
);
const mapGround = readFileSync(
  new URL('../features/living-map/AMapGround.tsx', import.meta.url),
  'utf8',
);

test('First Open visual states live outside the product page boundary', () => {
  assert.match(page, /import FirstOpenExperience/);
  assert.match(page, /<FirstOpenExperience/);
  assert.doesNotMatch(page, /ConversationComposer/);
  assert.doesNotMatch(page, /transitionPrefixVisible|transitionMapVisible/);

  for (const frame of [
    'idle',
    'focus',
    'typing',
    'ready',
    'transmitting',
    'grounding',
    'world',
  ]) {
    assert.match(firstOpen + firstOpenStyles, new RegExp(frame));
  }
});

test('prototype navigation and hard-coded Reality are not shipped', () => {
  const production = page + firstOpen + firstOpenStyles + firstRealityRuntime;
  assert.doesNotMatch(production, /frame-picker|selectFrame|targetExpression/);
  assert.doesNotMatch(production, /龙湖时代天街/);
  assert.doesNotMatch(production, /103\.9201|30\.7546/);
});

test('Grounding and World remain gated by authoritative runtime Reality', () => {
  assert.match(firstRealityRuntime, /resolveAuthoritativeGroundedReality\(/);
  assert.match(firstRealityRuntime, /property\.geographic_status === 'GROUNDED'/);
  assert.match(firstRealityRuntime, /isGroundedDecisionGeography\(decisionGeography\)/);
  assert.match(firstRealityRuntime, /profile\?\.geographic_status === 'GROUNDED'/);
  assert.match(
    firstRealityRuntime,
    /setFirstRealityTransition\(transition\);\s*setPhase\('grounding'\)/,
  );
  assert.match(
    firstRealityRuntime,
    /phase !== 'grounding'[\s\S]*!firstRealityTransition[\s\S]*!groundingSettled[\s\S]*!geographicGroundReady/,
  );
  assert.match(page, /initialMapCenter && hasGroundedWorld/);
});

test('First World reveal uses the runtime center and a real camera transition', () => {
  assert.match(page, /initialCenter=\{initialMapCenter\}/);
  assert.match(page, /firstRealityTransition\.focusZoom/);
  assert.match(firstRealityRuntime, /firstRealityTransition\.worldFraming/);
  assert.match(page, /initialFraming=\{!firstRealityTransition[\s\S]*authoritativeReality\?\.worldFraming/);
  assert.match(page, /FIRST_OPEN_WORLD_CAMERA_TRANSITION_MS/);
  assert.doesNotMatch(page, /\b(?:2800|3200)\b/);
  assert.match(firstOpen, /FIRST_OPEN_WORLD_CAMERA_TRANSITION_MS = 2800/);
  assert.match(firstOpen, /WORLD_SETTLE_MS = 3200/);
  assert.match(firstOpen, /window\.setTimeout\(onWorldSettled, WORLD_SETTLE_MS\)/);
  assert.match(
    firstRealityRuntime,
    /firstRealityTransition\.center,[\s\S]*firstRealityTransition\.worldFraming,[\s\S]*placeAnchorRef\.current/,
  );
  assert.match(
    firstRealityRuntime,
    /const FIRST_WORLD_FRAMING: GeographicCameraFraming = \{\s*level: 'PLACE',\s*attention: 'SEE'/,
  );
  assert.match(firstRealityRuntime, /worldFraming: FIRST_WORLD_FRAMING/);
  assert.match(mapGround, /geographicZoomForViewport\(initialFramingRef\.current, initialViewport\)/);
  assert.match(
    mapGround,
    /geographicCameraCenterForViewport\(\s*center,\s*zoom,\s*viewport,\s*screenAnchorPoint\(screenAnchor\)/,
  );
  assert.match(mapGround, /cameraTransitionDurationRef/);
  assert.match(mapGround, /animateEnable: cameraTransitionDurationRef\.current !== undefined/);
});

test('existing conversations restore formed World from shared authoritative Reality truth', () => {
  assert.match(
    firstRealityRuntime,
    /const restoredReality = resolveAuthoritativeGroundedReality\([\s\S]*?nextProfile,[\s\S]*?nextProperties,[\s\S]*?decisionGeography,[\s\S]*?\);/,
  );
  assert.match(
    firstRealityRuntime,
    /setPhase\(restoredReality \? 'formed' : 'empty'\);/,
  );
  assert.match(
    firstRealityRuntime,
    /skipRestoreConversationRef\.current = currentConversationId;\s*setConversationId\(currentConversationId\);/,
  );
  assert.doesNotMatch(
    firstRealityRuntime,
    /if \(nextProfile\.geographic_status === 'GROUNDED'\) \{\s*setPhase\('formed'\);/,
  );
  assert.match(firstRealityRuntime, /getConversationHistory\(conversationId\)/);
  assert.match(
    firstRealityRuntime,
    /expressionForGroundedReality\(history\.messages, restoredReality\.identity\)/,
  );
  assert.match(page, /groundedIdentity=\{authoritativeReality\?\.identity \?\? null\}/);
  assert.match(page, /initialScreenAnchorRef=\{authoritativeReality \? placeAnchorRef : undefined\}/);
  assert.match(firstRealityRuntime, /phase === 'formed' && !submittedExpression/);
  assert.match(firstRealityRuntime, /const firstOpenActive = Boolean\(submittedExpression\) \|\| !hasGroundedWorld \|\| worldVisible/);
  assert.match(firstRealityRuntime, /const firstOpenStage: FirstOpenRuntimeStage = phase === 'formed'\s*\? 'world'/);
});

test('page composes First Reality Runtime without owning its detailed implementation', () => {
  assert.match(page, /useFirstRealityRuntime\(\{/);
  assert.match(page, /<FirstOpenExperience/);
  assert.match(page, /<AMapGround/);
  assert.doesNotMatch(page, /streamMessage\(/);
  assert.doesNotMatch(page, /getLivingProfile\(/);
  assert.doesNotMatch(page, /getDecisionGeography\(/);
  assert.doesNotMatch(page, /resolveAuthoritativeGroundedReality\(/);
  assert.doesNotMatch(page, /latestSubmitIdRef/);

  assert.match(firstRealityRuntime, /const latestSubmitIdRef = useRef\(0\)/);
  assert.match(firstRealityRuntime, /const chatCompletion = streamMessage\(\{/);
  assert.match(firstRealityRuntime, /await Promise\.race\(\[/);
  assert.match(firstRealityRuntime, /getDecisionGeography\(currentConversationId\)/);
  assert.match(firstRealityRuntime, /applySceneResolution\(completedProfile, completedProperties, undefined, true\)/);
});

test('root no longer composes the retired post-07 Product Surface', () => {
  assert.doesNotMatch(page, /PossibleLifeProjection|focusedChoiceIds|singleFocusedHome/);
  assert.doesNotMatch(page, /handleExternalRent|handlePublicRentAction|handleDailyGrocery/);
  assert.doesNotMatch(page, /handlePlaceContext|handlePlaceUnderstanding|deriveBudgetMeaning/);
  assert.doesNotMatch(page, /Living World|compare-meaning|current_judgment/);
});

test('retired prototype routes and dead UI entries are deleted', () => {
  for (const relativePath of [
    '../app/living-map/scene-02/page.tsx',
    '../features/living-map/Scene02Prototype.tsx',
    '../app/living-map/transition/page.tsx',
    '../features/living-map/TransitionPrototype.tsx',
    '../features/ai-entry/components/PromptComposer/index.tsx',
    '../features/ai-entry/components/welcome/index.tsx',
    '../features/index.tsx',
    '../features/ai-entry/index.ts',
    '../app/conversation/page.tsx',
    '../app/living-map/page.tsx',
    '../app/profile/page.tsx',
    '../app/workspace/profile/page.tsx',
    '../app/workspace/property/page.tsx',
    '../app/workspace/decision/page.tsx',
    '../app/workspace/history/page.tsx',
    '../app/workspace/memory/page.tsx',
    '../features/conversation/index.tsx',
    '../features/living-map/index.tsx',
    '../features/living-map/PossibleLifeProjection.tsx',
    '../features/profile/index.tsx',
    '../features/living-profile-workspace/index.tsx',
    '../features/property-workspace/index.tsx',
    '../features/decision-workspace/index.tsx',
    '../features/history-workspace/index.tsx',
    '../features/memory-workspace/index.tsx',
    '../components/RouteLoading.tsx',
    '../features/ai-entry/components/AICore/index.tsx',
  ]) {
    assert.equal(existsSync(new URL(relativePath, import.meta.url)), false);
  }
});
