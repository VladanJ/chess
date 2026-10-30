/**
 * CrazyGames adapter (HTML5 SDK v3, https://docs.crazygames.com/sdk/intro/).
 * Build with `npm run build:crazygames`, then zip the contents of dist-crazygames/
 * and upload it at https://developer.crazygames.com/. Test locally with
 * `npm run dev:crazygames` (the SDK shows demo-ad overlays on localhost).
 */
import type { Portal, PortalHooks } from "../../src/portal";

interface CrazySettings {
  muteAudio: boolean;
}

interface CrazySDK {
  init(): Promise<void>;
  environment: "local" | "crazygames" | "disabled";
  game: {
    settings: CrazySettings;
    addSettingsChangeListener(listener: (s: CrazySettings) => void): void;
    loadingStart(): void;
    loadingStop(): void;
    gameplayStart(): void;
    gameplayStop(): void;
    happytime(): void;
  };
  ad: {
    requestAd(type: "midgame" | "rewarded", callbacks: {
      adStarted?: () => void;
      adFinished?: () => void;
      adError?: (error: unknown) => void;
    }): void;
  };
}

declare global {
  interface Window {
    CrazyGames?: { SDK: CrazySDK };
  }
}

// Stays null when the script was blocked or we're on a domain where the SDK is disabled.
let sdk: CrazySDK | null = null;
let hooks: PortalHooks;

function call(fn: (s: CrazySDK) => void): void {
  if (!sdk) return;
  try {
    fn(sdk);
  } catch (e) {
    console.warn("CrazyGames SDK call failed", e);
  }
}

/** Resolves true if the ad played to the end; never rejects. */
function requestAd(type: "midgame" | "rewarded"): Promise<boolean> {
  return new Promise((resolve) => {
    if (!sdk) {
      resolve(false);
      return;
    }
    let started = false;
    const done = (ok: boolean) => {
      if (started) hooks.resumeAudio();
      resolve(ok);
    };
    try {
      sdk.ad.requestAd(type, {
        adStarted: () => {
          started = true;
          hooks.pauseAudio();
        },
        adFinished: () => done(true),
        adError: () => done(false), // unfilled, adblock, cooldown...: just continue
      });
    } catch {
      resolve(false);
    }
  });
}

export const portal: Portal = {
  name: "crazygames",
  async init(h) {
    hooks = h;
    const s = window.CrazyGames?.SDK;
    if (!s) return;
    await s.init();
    if (s.environment === "disabled") return;
    sdk = s;
    sdk.game.loadingStart();
    h.setForcedMute(sdk.game.settings.muteAudio);
    sdk.game.addSettingsChangeListener((settings) => h.setForcedMute(settings.muteAudio));
  },
  loadingDone: () => call((s) => s.game.loadingStop()),
  gameplayStart: () => call((s) => s.game.gameplayStart()),
  gameplayStop: () => call((s) => s.game.gameplayStop()),
  commercialBreak: async () => {
    await requestAd("midgame");
  },
  rewardedBreak: () => requestAd("rewarded"),
  happyTime: () => call((s) => s.game.happytime()),
};
