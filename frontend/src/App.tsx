import { useState } from 'react';
import { Header } from '@/components/layout/Header';
import { Sidebar } from '@/components/layout/Sidebar';
import { AnalysisPage } from '@/pages/AnalysisPage';
import { CasesReportsPage } from '@/pages/CasesReportsPage';
import { ClustersPage } from '@/pages/ClustersPage';
import { DatasetPage } from '@/pages/DatasetPage';
import { EntityInvestigationPage } from '@/pages/EntityInvestigationPage';
import { GraphInvestigationPage } from '@/pages/GraphInvestigationPage';
import { InvestigativeLeadsPage } from '@/pages/InvestigativeLeadsPage';
import { OverviewPage } from '@/pages/OverviewPage';
import { SettingsPage } from '@/pages/SettingsPage';
import { TransactionFlowPage } from '@/pages/TransactionFlowPage';
import type { PageId } from '@/types';

const availablePages: PageId[] = ['overview', 'dataset', 'analysis', 'leads', 'entity', 'graph', 'transaction-flow', 'clusters', 'cases', 'settings'];

function App() {
  const [activePage, setActivePage] = useState<PageId>('overview');
  // No default entity: the backend has no `Wallet-A7F2` record, so seeding
  // that mock ID here caused `GET /entities/wallet/Wallet-A7F2` → 404 on
  // first visit to Entity Investigation. The ID is only set from real
  // backend IDs (Investigative Leads Review, Overview leads, Search).
  const [selectedEntityId, setSelectedEntityId] = useState<string | undefined>(undefined);

  function handleNavigate(page: PageId) {
    if (availablePages.includes(page)) setActivePage(page);
  }

  function renderPage() {
    switch (activePage) {
      case 'dataset':
        return <DatasetPage />;
      case 'analysis':
        return <AnalysisPage onNavigate={handleNavigate} />;
      case 'leads':
        return <InvestigativeLeadsPage onNavigate={handleNavigate} onOpenEntity={setSelectedEntityId} />;
      case 'entity':
        return <EntityInvestigationPage entityId={selectedEntityId} onNavigate={handleNavigate} />;
      case 'graph':
        return <GraphInvestigationPage />;
      case 'transaction-flow':
        return <TransactionFlowPage />;
      case 'clusters':
        return <ClustersPage />;
      case 'cases':
        return <CasesReportsPage />;
      case 'settings':
        return <SettingsPage />;
      case 'overview':
      default:
        return <OverviewPage onNavigate={handleNavigate} onOpenEntity={(id) => { setSelectedEntityId(id); handleNavigate('entity'); }} />;
    }
  }

  return (
    <div className="min-h-screen bg-ink-950 text-ink-100 flex">
      <Sidebar active={activePage} onNavigate={handleNavigate} />
      <div className="min-w-0 flex-1">
        <Header
          onNavigate={handleNavigate}
          onSearchResult={(result) => {
            const [page, id] = result.route.split(':');
            if (page === 'entity' && id) {
              setSelectedEntityId(id);
              handleNavigate('entity');
            } else if (page === 'transaction-flow' || page === 'clusters') {
              handleNavigate(page);
            } else {
              handleNavigate('overview');
            }
          }}
        />
        <main className="p-5">{renderPage()}</main>
      </div>
    </div>
  );
}

export default App;
