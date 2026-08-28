import { useEffect, useState } from 'react';
import ChatWindow from './components/ChatWindow';
import ModelPicker from './components/ModelPicker';
import Sidebar from './components/Sidebar';
import { fetchConfig, ingestDocument } from './services/api';
import type { ConfigResponse, ModelInfo } from './types';

export default function App() {
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [selectedModel, setSelectedModel] = useState('');

  useEffect(() => {
    fetchConfig()
      .then(setConfig)
      .catch(() => setConfig(null))
      .finally(() => setLoaded(true));
  }, []);

  const handleIngest = async (text: string, name: string) => {
    return ingestDocument(text, name);
  };

  return (
    <div className="app">
      <Sidebar onIngest={handleIngest} />
      <main className="main">
        <header className="topbar">
          <h1>Knowledge & Analytics Agent</h1>
          <ModelPicker
            models={(config?.available_models ?? []) as ModelInfo[]}
            selected={selectedModel}
            onSelect={setSelectedModel}
          />
        </header>
        {!loaded ? (
          <div className="loading">Loading configuration…</div>
        ) : (
          <ChatWindow modelOverride={selectedModel} />
        )}
      </main>
    </div>
  );
}
