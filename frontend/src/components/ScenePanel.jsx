import React, { useRef } from 'react';
import { useApp } from '../context/AppContext';
import { api } from '../services/api';
import './ScenePanel.css';

const ScenePanel = ({ onModelLoad }) => {
  const {
    sceneObjects,
    selectedObject,
    setSelectedObject,
    removeSceneObject,
    toggleObjectVisibility,
    addChatMessage
  } = useApp();
  
  const fileInputRef = useRef(null);

  const handleFileSelect = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    try {
      addChatMessage('assistant', 'Загружаю файл...');
      const result = await api.uploadModel(file);
      
      if (onModelLoad) {
        onModelLoad(result.download_url, result.filename);
      }
    } catch (error) {
      console.error('Upload error:', error);
      addChatMessage('assistant', `Ошибка загрузки: ${error.message}`);
    }
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.currentTarget.classList.add('dragging');
  };

  const handleDragLeave = (e) => {
    e.currentTarget.classList.remove('dragging');
  };

  const handleDrop = async (e) => {
    e.preventDefault();
    e.currentTarget.classList.remove('dragging');
    
    const file = e.dataTransfer.files[0];
    if (file) {
      try {
        addChatMessage('assistant', 'Загружаю файл...');
        const result = await api.uploadModel(file);
        
        if (onModelLoad) {
          onModelLoad(result.download_url, result.filename);
        }
      } catch (error) {
        console.error('Upload error:', error);
        addChatMessage('assistant', `Ошибка загрузки: ${error.message}`);
      }
    }
  };

  return (
    <div className="scene-panel">
      <div className="scene-objects">
        {sceneObjects.length === 0 ? (
          <div className="scene-empty">Пока нет объектов на сцене</div>
        ) : (
          sceneObjects.map((obj) => (
            <div
              key={obj.id}
              className={`scene-object ${selectedObject?.id === obj.id ? 'selected' : ''}`}
              onClick={() => setSelectedObject(obj)}
            >
              <span className="scene-object-icon">📦</span>
              <span className="scene-object-name">{obj.name}</span>
              <div className="scene-object-actions">
                <button
                  className="scene-object-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleObjectVisibility(obj.id);
                  }}
                  title="Видимость"
                >
                  {obj.visible ? '👁️' : '🚫'}
                </button>
                <button
                  className="scene-object-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    removeSceneObject(obj.id);
                  }}
                  title="Удалить"
                >
                  🗑️
                </button>
              </div>
            </div>
          ))
        )}
      </div>
      
      <div
        className="upload-area"
        onClick={handleUploadClick}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <div className="upload-icon">
          <svg width="60" height="60" viewBox="0 0 110 113" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M106 52.5659L58.3748 101.591C41.5005 113.988 20.6152 108.251 13.6083 101.591C-1.60828 87.1274 3.09787 71.339 14.9102 57.2672L65.771 7.87136C73.9458 0.0358686 91.5592 5.53774 95.8412 11.5909C100.123 17.6441 102.752 24.3259 99.3827 31.8018C96.0132 39.2777 49.1054 85.0383 48.777 84.6915C42.3921 88.5 36.9647 91.6791 29.3133 87.0099C22.9509 80.7094 24.8972 73.6896 29.3133 67.8451L51.5019 46.6893" stroke="#C8A1B1" strokeWidth="8" strokeLinecap="round"/>
          </svg>
        </div>
        <div className="upload-text">Загрузить модель</div>
        <div className="upload-hint">GLB, GLTF, OBJ</div>
      </div>
      
      <input
        ref={fileInputRef}
        type="file"
        accept=".glb,.gltf,.obj,.fbx,.stl"
        style={{ display: 'none' }}
        onChange={handleFileSelect}
      />
    </div>
  );
};

export default ScenePanel;
