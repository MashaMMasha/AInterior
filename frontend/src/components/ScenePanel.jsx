import React, { useMemo, useRef, useState, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { api } from '../services/api';
import './ScenePanel.css';

const GROUP_CONFIG = [
  { key: 'object', title: 'Объекты' },
  { key: 'uploaded', title: 'Загруженные модели' },
  { key: 'door', title: 'Двери' },
  { key: 'window', title: 'Окна' },
  { key: 'wall', title: 'Стены' },
  { key: 'floor', title: 'Пол' },
  { key: 'other', title: 'Прочее' },
];

const EyeIcon = ({ hidden = false }) => (
  <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path
      d="M2 12C4.2 8.2 7.6 6 12 6C16.4 6 19.8 8.2 22 12C19.8 15.8 16.4 18 12 18C7.6 18 4.2 15.8 2 12Z"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.8" />
    {hidden && <path d="M4 20L20 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />}
  </svg>
);

const TrashIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="M4 7H20" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    <path d="M9 7V5C9 4.4 9.4 4 10 4H14C14.6 4 15 4.4 15 5V7" stroke="currentColor" strokeWidth="1.7" />
    <path d="M7 7L8 19C8 20.1 8.9 21 10 21H14C15.1 21 16 20.1 16 19L17 7" stroke="currentColor" strokeWidth="1.7" />
    <path d="M10 11V17" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    <path d="M14 11V17" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
  </svg>
);

const ChevronIcon = ({ expanded }) => (
  <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className={expanded ? 'expanded' : ''}>
    <path d="M8 10L12 14L16 10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
  </svg>
);

const ScenePanel = ({ onModelLoad }) => {
  const {
    sceneObjects,
    selectedObject,
    setSelectedObject,
    removeSceneObject,
    toggleObjectVisibility,
    moveSceneObject,
    addChatMessage
  } = useApp();
  
  const fileInputRef = useRef(null);
  const [posDraft, setPosDraft] = useState({ x: 0, y: 0, z: 0 });
  const [expandedGroups, setExpandedGroups] = useState(() =>
    Object.fromEntries(GROUP_CONFIG.map((g) => [g.key, true]))
  );

  useEffect(() => {
    if (!selectedObject?.position) return;
    setPosDraft({
      x: Number(selectedObject.position.x ?? 0),
      y: Number(selectedObject.position.y ?? 0),
      z: Number(selectedObject.position.z ?? 0),
    });
  }, [selectedObject?.id, selectedObject?.position]);

  const groupedObjects = useMemo(() => {
    const buckets = Object.fromEntries(GROUP_CONFIG.map((g) => [g.key, []]));
    for (const obj of sceneObjects) {
      const type = obj?.type || 'other';
      const key = buckets[type] ? type : 'other';
      buckets[key].push(obj);
    }
    Object.keys(buckets).forEach((k) => {
      buckets[k].sort((a, b) => String(a.name || '').localeCompare(String(b.name || '')));
    });
    return buckets;
  }, [sceneObjects]);

  const visibleGroups = useMemo(
    () => GROUP_CONFIG.filter((group) => (groupedObjects[group.key] || []).length > 0),
    [groupedObjects]
  );

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
        {visibleGroups.length === 0 ? (
          <div className="scene-empty">Пока нет объектов на сцене</div>
        ) : (
          visibleGroups.map((group) => (
            <div key={group.key} className="scene-group">
              <button
                type="button"
                className="scene-group-header"
                onClick={() =>
                  setExpandedGroups((prev) => ({ ...prev, [group.key]: !prev[group.key] }))
                }
              >
                <span className="scene-group-title">{group.title}</span>
                <span className="scene-group-count">{groupedObjects[group.key].length}</span>
                <span className="scene-group-chevron">
                  <ChevronIcon expanded={Boolean(expandedGroups[group.key])} />
                </span>
              </button>

              {expandedGroups[group.key] && (
                <div className="scene-group-items">
                  {groupedObjects[group.key].map((obj) => (
                    <div
                      key={obj.id}
                      className={`scene-object ${selectedObject?.id === obj.id ? 'selected' : ''}`}
                      onClick={() => setSelectedObject(obj)}
                    >
                      <span className="scene-object-name">{obj.name}</span>
                      <div className="scene-object-actions">
                        <button
                          className="scene-object-btn icon-btn eye"
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleObjectVisibility(obj.id);
                          }}
                          title={obj.visible ? 'Скрыть' : 'Показать'}
                        >
                          <EyeIcon hidden={!obj.visible} />
                        </button>
                        {obj._source === 'uploaded' && (
                          <button
                            className="scene-object-btn icon-btn"
                            onClick={(e) => {
                              e.stopPropagation();
                              removeSceneObject(obj.id);
                            }}
                            title="Удалить"
                          >
                            <TrashIcon />
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {selectedObject && (
        <div className="scene-transform">
          <div className="scene-transform-title">Позиция</div>
          <div className="scene-transform-grid">
            <label>
              X
              <input
                type="number"
                step="0.1"
                disabled={selectedObject.movable === false}
                value={Number.isFinite(posDraft.x) ? posDraft.x : 0}
                onChange={(e) => setPosDraft((p) => ({ ...p, x: Number(e.target.value) }))}
              />
            </label>
            <label>
              Y
              <input
                type="number"
                step="0.1"
                disabled={selectedObject.movable === false}
                value={Number.isFinite(posDraft.y) ? posDraft.y : 0}
                onChange={(e) => setPosDraft((p) => ({ ...p, y: Number(e.target.value) }))}
              />
            </label>
            <label>
              Z
              <input
                type="number"
                step="0.1"
                disabled={selectedObject.movable === false}
                value={Number.isFinite(posDraft.z) ? posDraft.z : 0}
                onChange={(e) => setPosDraft((p) => ({ ...p, z: Number(e.target.value) }))}
              />
            </label>
          </div>
          <button
            className="scene-transform-apply"
            disabled={selectedObject.movable === false}
            onClick={() => moveSceneObject(selectedObject.id, { ...posDraft })}
          >
            Применить
          </button>
        </div>
      )}
      
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
