import { invoke, isTauri } from "@tauri-apps/api/core";
import { disable, enable } from "@tauri-apps/plugin-autostart";
import {
  isPermissionGranted,
  requestPermission
} from "@tauri-apps/plugin-notification";

export interface DesktopDeviceSettings {
  runInBackground: boolean;
  launchAtLogin: boolean;
  nativeNotifications: boolean;
}

export function desktopControlsAvailable(): boolean {
  return isTauri();
}

export async function syncDesktopBackgroundMode(enabled: boolean): Promise<void> {
  if (!isTauri()) return;
  await invoke("set_background_mode", { enabled });
}

export async function applyDesktopDeviceSettings(settings: DesktopDeviceSettings): Promise<void> {
  if (!isTauri()) throw new Error("desktop_controls_unavailable");
  await syncDesktopBackgroundMode(settings.runInBackground);
  if (settings.launchAtLogin) await enable();
  else await disable();
  if (settings.nativeNotifications && !await isPermissionGranted()) {
    const permission = await requestPermission();
    if (permission !== "granted") throw new Error("notification_permission_denied");
  }
}
