const STORAGE_VERSION = 1;
const STORAGE_PREFIX = "corvus.local-conversations.v1";

export interface DeviceMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
}

export interface DeviceThread {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messages: DeviceMessage[];
  workingDirectory?: string;
  repositoryId?: string;
  repositoryName?: string;
}

interface DeviceConversationState { version: typeof STORAGE_VERSION; threads: DeviceThread[]; }

function key(scope: string): string { return `${STORAGE_PREFIX}.${scope}`; }

function validMessage(value: unknown): value is DeviceMessage {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return typeof candidate.id === "string" &&
    (candidate.role === "user" || candidate.role === "assistant") &&
    typeof candidate.content === "string" && typeof candidate.createdAt === "string";
}

function validThread(value: unknown): value is DeviceThread {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return typeof candidate.id === "string" && typeof candidate.title === "string" &&
    typeof candidate.createdAt === "string" && typeof candidate.updatedAt === "string" &&
    Array.isArray(candidate.messages) && candidate.messages.every(validMessage) &&
    (candidate.workingDirectory === undefined || typeof candidate.workingDirectory === "string") &&
    (candidate.repositoryId === undefined || typeof candidate.repositoryId === "string") &&
    (candidate.repositoryName === undefined || typeof candidate.repositoryName === "string");
}

export function loadDeviceThreads(storage: Storage, scope: string): DeviceThread[] {
  const storageKey = key(scope);
  const value = storage.getItem(storageKey);
  if (value === null) return [];
  try {
    const parsed = JSON.parse(value) as { version?: unknown; threads?: unknown };
    if (parsed.version === STORAGE_VERSION && Array.isArray(parsed.threads) && parsed.threads.every(validThread)) return parsed.threads;
  } catch { /* Invalid device-only data is removed below. */ }
  storage.removeItem(storageKey);
  return [];
}

export function saveDeviceThreads(storage: Storage, scope: string, threads: readonly DeviceThread[]): void {
  const state: DeviceConversationState = { version: STORAGE_VERSION, threads: [...threads] };
  storage.setItem(key(scope), JSON.stringify(state));
}
