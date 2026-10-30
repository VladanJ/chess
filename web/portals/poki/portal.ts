/**
 * Poki adapter (HTML5 SDK, https://developers.poki.com/guide/sdk-html5).
 * Build with `npm run build:poki`, then zip the contents of dist-poki/ and upload it
 * to the Poki Inspector (https://inspector.poki.dev/) to test before review.
 */
import type { Portal, PortalHooks } from "../../src/portal";

interface PokiSDK {
  init(): Promise<void>;
  gameLoadingFinished(): void;
  gameplayStart(): void;
  gameplayStop(): void;
  commercialBreak(beforeAd?: () => void): Promise<void>;
  rewardedBreak(beforeAd?: () => void): Promise<boolean>;
}

declare global {
  interface Window {
    PokiSDK?: PokiSDK;
  }
}

// Stays null when the script was blocked (e.g. by an adblocker).
let sdk: PokiSDK | null = null;
let hooks: PortalHooks;

function call(fn: (s: PokiSDK) => void): void {
  if (!sdk) return;
  try {
    fn(sdk);
  } catch (e) {
    console.warn("Poki SDK call failed", e);
  }
}

/** Runs a Poki ad break, muting only if an ad actually starts; never rejects. */
async function adBreak<T>(run: (s: PokiSDK, beforeAd: () => void) => Promise<T>, fallback: T): Promise<T> {
  if (!sdk) return fallback;
  let paused = false;
  try {
    return await run(sdk, () => {
      paused = true;
      hooks.pauseAudio();
    });
  } catch {
    return fallback;
  } finally {
    if (paused) hooks.resumeAudio();
  }
}

export const portal: Portal = {
  name: "poki",
  async init(h) {
    hooks = h;
    const s = window.PokiSDK;
    if (!s) return;
    try {
      await s.init();
    } catch {
      // Poki's guidance: load the game anyway.
    }
    sdk = s;
    // The game sits inside a scrollable Poki page: keep keys and the wheel from scrolling it.
    window.addEventListener("keydown", (ev) => {
      if (["ArrowDown", "ArrowUp", " "].includes(ev.key)) ev.preventDefault();
    });
    document.getElementById("board")?.addEventListener("wheel", (ev) => ev.preventDefault(), { passive: false });
  },
  loadingDone: () => call((s) => s.gameLoadingFinished()),
  gameplayStart: () => call((s) => s.gameplayStart()),
  gameplayStop: () => call((s) => s.gameplayStop()),
  commercialBreak: () => adBreak((s, beforeAd) => s.commercialBreak(beforeAd), undefined),
  rewardedBreak: () => adBreak((s, beforeAd) => s.rewardedBreak(beforeAd), false),
  happyTime: () => {}, // Poki has no equivalent
};
