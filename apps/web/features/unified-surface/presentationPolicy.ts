import type { ConversationMessage, GroundedRealityPresentation, WorldPresentationReadiness } from '@/lib/runtimePresentationContract';
import type { WorldConsequenceFocus } from '@/lib/worldConsequence';

export interface SurfacePresentationFacts extends WorldPresentationReadiness {
  messages: readonly ConversationMessage[];
  isResponding: boolean;
  isRestoringConversation: boolean;
  isSubmittingExpression: boolean;
  groundedReality: GroundedRealityPresentation | null;
  consequenceFocus: WorldConsequenceFocus | null;
}

/** Derive presentation only; Runtime remains the owner of facts and reveal progress. */
export function deriveSurfacePresentation(facts: SurfacePresentationFacts) {
  const started = facts.messages.length > 0 || facts.isRestoringConversation;
  const worldEligible = facts.groundedReality !== null;
  const worldVisible = worldEligible && facts.geographicGroundReady && facts.cameraReady && facts.revealStarted;
  const anchorMounted = worldEligible && facts.requiresCameraAnchor;
  const revealInProgress = facts.requiresCameraAnchor && !facts.revealComplete;
  const focus = facts.consequenceFocus;
  const hasExplicitRealityFocus = Boolean(focus?.focusPropertyId || focus?.focusSubject || focus?.focusPossibleLife);
  return {
    started,
    worldEligible,
    worldVisible,
    anchorMounted,
    anchorVisible: worldVisible,
    reportRevealCompletion: worldVisible && !facts.revealComplete,
    entryDisabled: facts.isResponding || facts.isRestoringConversation || facts.isSubmittingExpression || revealInProgress,
    // This is presentation emphasis from an explicit consequence, not inferred user Attention.
    visualEmphasis: worldVisible && hasExplicitRealityFocus ? 'world' : 'conversation',
  };
}
