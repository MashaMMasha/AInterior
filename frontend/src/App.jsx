import React, { useState } from 'react';
import { Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { AppProvider } from './context/AppContext';
import ProtectedRoute from './components/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import VerifyEmailPage from './pages/VerifyEmailPage';
import Header from './components/Header';
import ChatPanel from './components/ChatPanel';
import ViewerPanel from './components/ViewerPanel';
import ScenePanel from './components/ScenePanel';
import ResizablePanel from './components/ResizablePanel';
import './styles/global.css';
import './App.css';

function MainApp() {
  const [modelToLoad, setModelToLoad] = useState(null);
  const [isLeftCollapsed, setIsLeftCollapsed] = useState(false);
  const [isRightCollapsed, setIsRightCollapsed] = useState(false);

  const handleModelLoad = (payloadOrUrl, filename) => {
    if (payloadOrUrl && typeof payloadOrUrl === 'object' && payloadOrUrl.type === 'scene_plan') {
      setModelToLoad({ ...payloadOrUrl, timestamp: Date.now() });
      return;
    }

    setModelToLoad({ url: payloadOrUrl, filename, timestamp: Date.now() });
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

function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/verify-email" element={<VerifyEmailPage />} />
        <Route path="/*" element={
          <ProtectedRoute>
            <MainApp />
          </ProtectedRoute>
        } />
      </Routes>
    </AuthProvider>
  );
}

export default App;
