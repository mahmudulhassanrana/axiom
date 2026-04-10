import { Header } from "./header";
import { Sidebar } from "./sidebar";

type DashboardShellProps = {
  children: React.ReactNode;
  headerTitle: string;
  headerDescription?: string;
};

export function DashboardShell({ children, headerTitle, headerDescription }: DashboardShellProps) {
  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header title={headerTitle} description={headerDescription} />
        <main className="flex-1 overflow-auto px-6 py-8 lg:px-10">{children}</main>
      </div>
    </div>
  );
}
