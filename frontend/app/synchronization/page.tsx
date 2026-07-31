import { AppShell } from "../../components/app-shell";
import { SynchronizationCenter } from "../../components/synchronization-center";

export default function SynchronizationPage() {
  return (
    <AppShell active="/synchronization">
      <header className="topbar">
        <div><p className="eyebrow">USTAWIENIA</p><h1>Synchronizacja</h1><p className="muted">Połączenia, harmonogramy, błędy i historia wszystkich platform.</p></div>
      </header>
      <SynchronizationCenter />
    </AppShell>
  );
}
