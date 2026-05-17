import React, { useEffect, useState } from 'react';
import { Screen } from './types';
import SideNavBar from './layout/SideNavBar';
import TopNavBar from './layout/TopNavBar';
import Footer from './layout/Footer';
import Dashboard from './screens/Dashboard';
import Devices from './screens/Devices';
import Threats from './screens/Threats';
import Firewall from './screens/Firewall';
import Honeypots from './screens/Honeypots';
import Diagnostics from './screens/Diagnostics';
import Logs from './screens/Logs';
import Settings from './screens/Settings';

export default function App() {
  const [activeScreen, setActiveScreen] = useState<Screen>(Screen.DASHBOARD);
  const [searchFilter, setSearchFilter] = useState('');
  const [searchScreen, setSearchScreen] = useState<Screen | null>(null);

  const handleSearchNavigate = (screen: Screen, query: string) => {
    setActiveScreen(screen);
    setSearchScreen(screen);
    setSearchFilter(query);
  };

  useEffect(() => {
    if (searchScreen && activeScreen !== searchScreen) {
      setSearchScreen(null);
      setSearchFilter('');
    }
  }, [activeScreen, searchScreen]);

  const renderScreen = () => {
    const externalFilter = activeScreen === searchScreen ? searchFilter : '';
    switch (activeScreen) {
      case Screen.DASHBOARD: return <Dashboard onNavigate={setActiveScreen} />;
      case Screen.DEVICES:   return <Devices externalFilter={externalFilter} />;
      case Screen.THREATS:   return <Threats externalFilter={externalFilter} />;
      case Screen.FIREWALL:  return <Firewall />;
      case Screen.HONEYPOTS: return <Honeypots />;
      case Screen.DIAGNOSTICS: return <Diagnostics />;
      case Screen.LOGS: return <Logs />;
      case Screen.SETTINGS:  return <Settings />;
      default:               return <Dashboard />;
    }
  };

  return (
    <div className="flex h-screen w-full bg-black text-on-surface overflow-hidden font-sans">
      <SideNavBar activeScreen={activeScreen} setActiveScreen={setActiveScreen} />
      
      <div className="flex-1 flex flex-col min-w-0 relative">
        <TopNavBar onNavigateToResult={handleSearchNavigate} />
        
        <main className="flex-1 overflow-y-auto custom-scrollbar relative z-10 pb-[40px]">
          {renderScreen()}
        </main>
        
        <Footer />
      </div>
    </div>
  );
}
