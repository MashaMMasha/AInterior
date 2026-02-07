import React, { useState } from 'react';
import { AppProvider } from './context/AppContext';
import Header from './components/Header';
import ChatPanel from './components/ChatPanel';
import ViewerPanel from './components/ViewerPanel';
import ScenePanel from './components/ScenePanel';
import ResizablePanel from './components/ResizablePanel';
import './styles/global.css';
import './App.css';

function App() {
  const [modelToLoad, setModelToLoad] = useState(null);
  const [isLeftCollapsed, setIsLeftCollapsed] = useState(false);
  const [isRightCollapsed, setIsRightCollapsed] = useState(false);

  const handleModelLoad = (url, filename) => {
    setModelToLoad({ url, filename, timestamp: Date.now() });
  };

  const handleToggleLeftPanel = () => {
    setIsLeftCollapsed(prev => !prev);
  };

  const handleToggleRightPanel = () => {
    setIsRightCollapsed(prev => !prev);
  };

  return (
    <AppProvider>
      <div className="app">
        <Header 
          onToggleLeftPanel={handleToggleLeftPanel}
          onToggleRightPanel={handleToggleRightPanel}
          isLeftCollapsed={isLeftCollapsed}
          isRightCollapsed={isRightCollapsed}
        />
        <div className="main-container">
          <ResizablePanel 
            side="left" 
            minWidth={280} 
            maxWidth={600} 
            defaultWidth={350}
            collapsed={isLeftCollapsed}
            onToggle={handleToggleLeftPanel}
          >
            <ChatPanel onModelLoad={handleModelLoad} />
          </ResizablePanel>
          <ViewerPanel modelToLoad={modelToLoad} onModelLoaded={() => setModelToLoad(null)} />
          <ResizablePanel 
            side="right" 
            minWidth={250} 
            maxWidth={500} 
            defaultWidth={300}
            collapsed={isRightCollapsed}
            onToggle={handleToggleRightPanel}
          >
            <ScenePanel onModelLoad={handleModelLoad} />
          </ResizablePanel>
        </div>
      </div>
    </AppProvider>
  );
}

export default App;
