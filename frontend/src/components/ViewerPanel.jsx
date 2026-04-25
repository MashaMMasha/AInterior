import React, { useRef, useEffect, useState, useMemo } from 'react';
import { useApp } from '../context/AppContext';
import { api } from '../services/api';
import './ViewerPanel.css';

const DEFAULT_RENDER_EMBED_URL = '/render/viewer-embed.html';
const CONVERSATION_STORAGE_KEY = (projectId) => `ainterior_conversation_${projectId}`;
const SCENE_SNAPSHOT_TYPE = 'scene_plan_snapshot_v1';

const ViewerPanel = ({ modelToLoad, onModelLoaded }) => {
  const iframeRef = useRef(null);
  const obllomovPollRef = useRef(null);
  const lastSnapshotKeyRef = useRef('');
  const latestSceneRef = useRef(null);
  const lastPersistedSnapshotKeyRef = useRef('');
  const prevVisibilityRef = useRef(new Map());
  const prevPositionRef = useRef(new Map());
  const selectedIdRef = useRef(null);
  const [viewMode, setViewMode] = useState('obllomov');
  const {
    sceneObjects,
    selectedObject,
    replaceSceneObjects,
    currentProject,
  } = useApp();

  // В Docker/nginx embed только из /render/; VITE_ с __obllomov_render__ тянет HTML с :8088 без наших путей к utils
  const obllomovSrc = useMemo(() => {
    const raw = (import.meta.env.VITE_OBLOLOMV_RENDER_URL || '').trim();
    if (raw.includes('__obllomov_render__')) {
      return DEFAULT_RENDER_EMBED_URL;
    }
    return raw || DEFAULT_RENDER_EMBED_URL;
  }, []);

  const getConversationIdForProject = (project) => {
    if (!project) return null;
    if (project.conversation_id) return project.conversation_id;
    return localStorage.getItem(CONVERSATION_STORAGE_KEY(project.id));
  };

  const getLatestRenderableStage = (messages) => {
    if (!Array.isArray(messages) || messages.length === 0) return null;
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      const stages = messages[i]?.stages || [];
      for (let j = stages.length - 1; j >= 0; j -= 1) {
        if (stages[j]?.scene_plan) {
          return {
            interactionId: messages[i].interaction_id,
            stage: stages[j],
          };
        }
      }
    }
    return null;
  };

  const getSceneSnapshotFromProject = (project) => {
    if (!project || !Array.isArray(project.objects)) return null;
    const snapshot = project.objects.find((obj) => obj?._system_type === SCENE_SNAPSHOT_TYPE);
    return snapshot?.scene_plan || null;
  };

  const saveSceneSnapshotToProject = async (project, scenePlan, snapshotKey) => {
    if (!project || project.id === 'default' || !scenePlan || !snapshotKey) return;
    if (lastPersistedSnapshotKeyRef.current === snapshotKey) return;

    const existingObjects = Array.isArray(project.objects) ? project.objects : [];
    const userObjects = existingObjects.filter((obj) => obj?._system_type !== SCENE_SNAPSHOT_TYPE);
    const snapshotObject = {
      _system_type: SCENE_SNAPSHOT_TYPE,
      snapshot_key: snapshotKey,
      scene_plan: scenePlan,
      saved_at: new Date().toISOString(),
    };

    try {
      await api.updateProject(project.id, {
        objects: [...userObjects, snapshotObject],
      });
      lastPersistedSnapshotKeyRef.current = snapshotKey;
    } catch (error) {
      console.error('Failed to persist scene snapshot to project:', error);
    }
  };

  const postSceneToIframe = (scenePlan) => {
    if (!scenePlan || !iframeRef.current?.contentWindow) return false;
    iframeRef.current.contentWindow.postMessage({ type: 'LOAD_SCENE', scene: scenePlan }, '*');
    return true;
  };

  const clearIframeScene = () => {
    if (!iframeRef.current?.contentWindow) return;
    iframeRef.current.contentWindow.postMessage({ type: 'CLEAR_SCENE' }, '*');
  };

  const postViewerCommand = (type, payload) => {
    if (!iframeRef.current?.contentWindow) return;
    iframeRef.current.contentWindow.postMessage({ type, ...payload }, '*');
  };

  useEffect(() => {
    const onMessage = (event) => {
      const { data } = event;
      if (!data || typeof data !== 'object') return;
      if (data.type === 'SCENE_ENTITIES' && Array.isArray(data.entities)) {
        const prevMap = new Map(sceneObjects.map((obj) => [obj.id, obj]));
        const merged = data.entities.map((entity) => {
          const prev = prevMap.get(entity.id);
          return {
            ...entity,
            visible: typeof prev?.visible === 'boolean' ? prev.visible : entity.visible !== false,
            _ephemeral: entity._source !== 'uploaded',
          };
        });
        replaceSceneObjects(merged);
      }
      if (data.type === 'ENTITY_MOVED' && data.entityId && data.position) {
        replaceSceneObjects(
          sceneObjects.map((obj) =>
            obj.id === data.entityId ? { ...obj, position: data.position } : obj
          )
        );
      }
    };

    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [sceneObjects, replaceSceneObjects]);

  useEffect(() => {
    if (viewMode !== 'obllomov') return;
    let cancelled = false;

    const projectSnapshot = getSceneSnapshotFromProject(currentProject);
    if (projectSnapshot) {
      latestSceneRef.current = projectSnapshot;
      postSceneToIframe(projectSnapshot);
    } else {
      clearIframeScene();
    }

    const tick = async () => {
      const convId = getConversationIdForProject(currentProject);
      if (!convId) return;

      try {
        const msgs = await api.getConversationMessages(convId);
        if (cancelled || !Array.isArray(msgs) || msgs.length === 0) return;

        const renderable = getLatestRenderableStage(msgs);
        if (!renderable) return;

        const snapshotKey = [
          renderable.interactionId || 'na',
          renderable.stage.stage_name || 'na',
          renderable.stage.created_at || 'na',
        ].join(':');

        if (snapshotKey === lastSnapshotKeyRef.current) return;
        lastSnapshotKeyRef.current = snapshotKey;
        latestSceneRef.current = renderable.stage.scene_plan;
        postSceneToIframe(renderable.stage.scene_plan);
        saveSceneSnapshotToProject(currentProject, renderable.stage.scene_plan, snapshotKey);
      } catch (error) {
        console.error('Failed to sync viewer scene snapshot:', error);
      }
    };

    tick();
    obllomovPollRef.current = setInterval(tick, 2000);

    return () => {
      cancelled = true;
      if (obllomovPollRef.current) {
        clearInterval(obllomovPollRef.current);
        obllomovPollRef.current = null;
      }
    };
  }, [viewMode, currentProject?.id, currentProject?.conversation_id]);

  useEffect(() => {
    lastSnapshotKeyRef.current = '';
    latestSceneRef.current = null;
    lastPersistedSnapshotKeyRef.current = '';
    clearIframeScene();
  }, [currentProject?.id]);

  useEffect(() => {
    if (!modelToLoad) return;

    // Сцена в режиме obllomov синхронизируется отдельным polling.
    if (modelToLoad.type === 'scene_plan') {
      if (viewMode !== 'obllomov') setViewMode('obllomov');
      return;
    }

    if (!modelToLoad.url || !modelToLoad.filename) return;
    if (viewMode !== 'obllomov') setViewMode('obllomov');

    const uploadedModelId = `uploaded-${Date.now()}`;
    const postUploaded = () => {
      if (!iframeRef.current?.contentWindow) return;
      postViewerCommand('LOAD_UPLOADED_MODEL', {
        model: {
          id: uploadedModelId,
          url: modelToLoad.url,
          filename: modelToLoad.filename,
        },
      });
      if (onModelLoaded) onModelLoaded();
    };

    setTimeout(postUploaded, 300);
  }, [modelToLoad, viewMode]);

  useEffect(() => {
    const newVisibility = new Map();
    const newPosition = new Map();
    sceneObjects.forEach((obj) => {
      newVisibility.set(obj.id, obj.visible !== false);
      newPosition.set(obj.id, obj.position || null);
      const prevVisible = prevVisibilityRef.current.get(obj.id);
      if (typeof prevVisible === 'boolean' && prevVisible !== (obj.visible !== false)) {
        postViewerCommand('SET_ENTITY_VISIBILITY', {
          entityId: obj.id,
          visible: obj.visible !== false,
        });
      }
      const prevPos = prevPositionRef.current.get(obj.id);
      if (obj.position && JSON.stringify(prevPos) !== JSON.stringify(obj.position)) {
        postViewerCommand('MOVE_ENTITY', { entityId: obj.id, position: obj.position });
      }
    });
    prevVisibilityRef.current = newVisibility;
    prevPositionRef.current = newPosition;
  }, [sceneObjects]);

  useEffect(() => {
    const selectedId = selectedObject?.id || null;
    if (selectedIdRef.current === selectedId) return;
    selectedIdRef.current = selectedId;
    postViewerCommand('SELECT_ENTITY', { entityId: selectedId });
  }, [selectedObject?.id]);

  return (
    <div className="viewer-panel">
      <iframe
        ref={iframeRef}
        className="viewer-iframe"
        title="AInterior render scene"
        src={obllomovSrc}
        onLoad={() => {
          if (latestSceneRef.current) {
            postSceneToIframe(latestSceneRef.current);
          }
        }}
      />
    </div>
  );
};

export default ViewerPanel;
