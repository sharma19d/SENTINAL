import React, { useState } from 'react';
import { Screen } from './types';
import SideNavBar from './layout/SideNavBar';
import TopNavBar from './layout/TopNavBar';
import Footer from './layout/Footer';
import Dashboard from './screens/Dashboard';
import Devices from './screens/Devices';
import Threats from './screens/Threats';
import Firewall from './screens/Firewall';
import Honeypots from './screens/Honeypots';
import Settings from './screens/Settings';

export default function App() {
  const [activeScreen, setActiveScreen] = useState<Screen>(Screen.DASHBOARD);

  const renderScreen = () => {
    switch (activeScreen) {
      case Screen.DASHBOARD: return <Dashboard />;
      case Screen.DEVICES:   return <Devices />;
      case Screen.THREATS:   return <Threats />;
      case Screen.FIREWALL:  return <Firewall />;
      case Screen.HONEYPOTS: return <Honeypots />;
      case Screen.SETTINGS:  return <Settings />;
      default:               return <Dashboard />;
    }
  };

  return (
    <div className="flex h-screen w-full bg-black text-on-surface overflow-hidden font-sans">
      <SideNavBar activeScreen={activeScreen} setActiveScreen={setActiveScreen} />
      
      <div className="flex-1 flex flex-col min-w-0 relative">
        <TopNavBar />
        
        <main className="flex-1 overflow-y-auto custom-scrollbar relative z-10 pb-[40px]">
          {renderScreen()}
        </main>
        
        <Footer />
      </div>
    </div>
  );
}
