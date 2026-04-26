// useWorkspaceContextSync — reflects useWorkspace() into AppContext (US1).
//
// Mounted once at the shell level so the Sidebar nav badge and the
// ContextBar LensSelector see the live workspace state regardless of
// whether the Connections page is currently rendered. The hook owns
// the polling; this bridge just dispatches a normalized list back
// into the AppContext reducer.

import { useEffect, useMemo } from "react";
import {
  useAppState,
  type WorkspaceConnectionRef,
} from "../context/AppContext";
import { useWorkspace, type Connection } from "./useWorkspace";

function toRef(c: Connection): WorkspaceConnectionRef {
  return {
    connection_id: c.connection_id,
    driver_type: c.driver_type,
    display_name: c.display_name,
    scope: c.scope,
    status: c.status,
  };
}

/** Subscribe to /workspace/* and mirror the result into AppContext. */
export function useWorkspaceContextSync(): void {
  const { connections } = useWorkspace();
  const { dispatch } = useAppState();

  // Memoize the projection so identical fetches don't re-render dependents.
  const refs = useMemo(() => connections.map(toRef), [connections]);
  const fingerprint = useMemo(
    () =>
      refs
        .map((r) => `${r.connection_id}:${r.status}`)
        .sort()
        .join("|"),
    [refs]
  );

  useEffect(() => {
    dispatch({ type: "WORKSPACE_CONNECTIONS_SET", connections: refs });
    // We use the fingerprint (not refs identity) so the dispatch only fires
    // when the relevant fields actually change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fingerprint]);
}
