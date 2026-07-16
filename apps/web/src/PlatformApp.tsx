import type { CorvusApi } from "./api";
import { App } from "./App";
import { AuthProvider } from "./auth/AuthProvider";
import { createAuthApi, type PlatformApi } from "./auth/authApi";
import { SyncProvider } from "./sync/SyncProvider";

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
  return (
    <AuthProvider api={hostedApi}>
      <SyncProvider api={hostedApi}>
        <App
          api={loopbackApi}
          locationHostname={locationHostname}
          preferenceStorage={preferenceStorage}
        />
      </SyncProvider>
    </AuthProvider>
  );
}
