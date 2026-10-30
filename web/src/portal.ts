/**
 * Game-portal integration (ads, gameplay events). The game imports `portal` from
 * "@portal"; this file is the default for our own site and does nothing. Portal
 * builds swap in portals/<name>/portal.ts (see vite.config.ts).
 */

/** What a portal may ask the game to do. */
export interface PortalHooks {
  /** An ad started: silence the game. */
  pauseAudio(): void;
  /** The ad ended (or never showed): restore audio. */
  resumeAudio(): void;
  /** The portal itself requires the game to be muted (e.g. a site-wide mute). */
  setForcedMute(muted: boolean): void;
}

export interface Portal {
  /** "web" for our own site, otherwise the portal's name. */
  readonly name: string;
  init(hooks: PortalHooks): Promise<void>;
  loadingDone(): void;
  gameplayStart(): void;
  gameplayStop(): void;
  /** Natural break before the next match; resolves when the game may continue. */
  commercialBreak(): Promise<void>;
  /** Player-chosen ad; resolves true if the reward should be granted. */
  rewardedBreak(): Promise<boolean>;
  /** A celebration-worthy moment (e.g. beating the AI). */
  happyTime(): void;
}

export const portal: Portal = {
  name: "web",
  init: async () => {},
  loadingDone: () => {},
  gameplayStart: () => {},
  gameplayStop: () => {},
  commercialBreak: async () => {},
  rewardedBreak: async () => false,
  happyTime: () => {},
};
