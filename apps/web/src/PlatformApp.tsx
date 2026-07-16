import type { CorvusApi } from "./api";
import { App } from "./App";
import { AuthProvider, LocalAuthProvider } from "./auth/AuthProvider";
import { createAuthApi, type PlatformApi } from "./auth/authApi";
import { isLoopbackRuntimeHost } from "./runtime/localRuntime";
import { LocalSyncProvider, SyncProvider } from "./sync/SyncProvider";

const browserHostedApi = createAuthApi();

interface PlatformAppProps {
  hostedApi?: PlatformApi;
  locationHostname?: string;
  loopbackApi?: CorvusApi;
  preferenceStorage?: Storage;
}

export function PlatformApp({
  hostedApi = browserHostedApi,
  locationHostname,
  loopbackApi,
  preferenceStorage
}: PlatformAppProps) {
  const hostname = locationHostname ?? window.location.hostname;
  if (isLoopbackRuntimeHost(hostname)) {
    return (
      <LocalAuthProvider>
        <LocalSyncProvider>
          <App
            api={loopbackApi}
            locationHostname={hostname}
            preferenceStorage={preferenceStorage}
          />
        </LocalSyncProvider>
      </LocalAuthProvider>
    );
  }
  return (
    <AuthProvider api={hostedApi}>
      <SyncProvider api={hostedApi}>
        <App
          api={loopbackApi}
          locationHostname={hostname}
          preferenceStorage={preferenceStorage}
        />
      </SyncProvider>
    </AuthProvider>
  );
}
