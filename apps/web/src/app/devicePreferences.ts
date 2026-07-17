const DEVICE_PREFERENCES_KEY_PREFIX = "corvus.device-preferences.v1";
const DEVICE_PREFERENCES_VERSION = 1;

export type ThemePreference = "system" | "light" | "dark";
export type ResponseTone = "concise" | "balanced" | "detailed";
export type SendKeyMode = "adaptive" | "enter" | "ctrl-enter";
export type SafetyGuidance = "standard" | "detailed";

export interface DevicePreferences {
  version: typeof DEVICE_PREFERENCES_VERSION;
  theme: ThemePreference;
  responseTone: ResponseTone;
  customRules: string;
  mcpNotes: string;
  sendKeyMode: SendKeyMode;
  safetyGuidance: SafetyGuidance;
}

export const DEFAULT_DEVICE_PREFERENCES: DevicePreferences = Object.freeze({
  version: DEVICE_PREFERENCES_VERSION,
  theme: "system",
  responseTone: "balanced",
  customRules: "",
  mcpNotes: "",
  sendKeyMode: "adaptive",
  safetyGuidance: "standard"
});

function storageKey(workspaceId: string): string {
  return `${DEVICE_PREFERENCES_KEY_PREFIX}.${workspaceId}`;
}

function isDevicePreferences(value: unknown): value is DevicePreferences {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    candidate.version === DEVICE_PREFERENCES_VERSION &&
    (candidate.theme === "system" || candidate.theme === "light" || candidate.theme === "dark") &&
    (candidate.responseTone === "concise" ||
      candidate.responseTone === "balanced" ||
      candidate.responseTone === "detailed") &&
    typeof candidate.customRules === "string" &&
    typeof candidate.mcpNotes === "string" &&
    (candidate.sendKeyMode === "adaptive" ||
      candidate.sendKeyMode === "enter" ||
      candidate.sendKeyMode === "ctrl-enter") &&
    (candidate.safetyGuidance === "standard" || candidate.safetyGuidance === "detailed")
  );
}

export function loadDevicePreferences(storage: Storage, workspaceId: string): DevicePreferences {
  const key = storageKey(workspaceId);
  const serialized = storage.getItem(key);
  if (serialized === null) return { ...DEFAULT_DEVICE_PREFERENCES };
  try {
    const parsed = JSON.parse(serialized) as unknown;
    if (isDevicePreferences(parsed)) return parsed;
  } catch {
    // Invalid device-only data is removed below and never becomes runtime authority.
  }
  storage.removeItem(key);
  return { ...DEFAULT_DEVICE_PREFERENCES };
}

export function saveDevicePreferences(
  storage: Storage,
  workspaceId: string,
  preferences: DevicePreferences
): void {
  storage.setItem(storageKey(workspaceId), JSON.stringify(preferences));
}
