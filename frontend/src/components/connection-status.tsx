type ConnectionStatusProps = {
  state: "checking" | "connected" | "error";
};

const labels: Record<ConnectionStatusProps["state"], string> = {
  checking: "CONNECTING",
  connected: "CONNECTED",
  error: "CONNECTION LOST",
};

export function ConnectionStatus({ state }: ConnectionStatusProps) {
  return (
    <span className="status-badge" data-state={state} role="status">
      {labels[state]}
    </span>
  );
}
