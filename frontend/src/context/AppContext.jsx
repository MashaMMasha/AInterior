import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../services/api';

const AppContext = createContext();

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within AppProvider');
  }
  return context;
};

export const AppProvider = ({ children }) => {
  const [projects, setProjects] = useState([]);
  const [currentProject, setCurrentProject] = useState(null);
  const [sceneObjects, setSceneObjects] = useState([]);
  const [selectedObject, setSelectedObject] = useState(null);
  // Убираем дефолтное сообщение - чат будет загружаться через ChatPanel
  const [chatMessages, setChatMessages] = useState([]);

  useEffect(() => {
    // Всегда загружаем проекты пользователя при открытии
    loadProjects();
  }, []);

  const updateCurrentProject = (partial) => {
    setCurrentProject((p) => {
      if (!p) return p;
      const next = { ...p, ...partial };
      setProjects((list) => list.map((proj) => (proj.id === p.id ? next : proj)));
      return next;
    });
  };

  const loadProjects = async () => {
    try {
      const data = await api.getProjects();
      
      if (data.status === 'success' && data.projects.length > 0) {
        let projs = data.projects;
        // Один существующий чат без привязки: привязываем к единственному проекту
        if (projs.length === 1 && projs[0].id !== 'default' && !projs[0].conversation_id) {
          try {
            const convs = await api.getConversations();
            if (convs && convs.length === 1) {
              const cid = convs[0].conversation_id;
              await api.updateProject(projs[0].id, { conversation_id: cid });
              projs = [{ ...projs[0], conversation_id: cid }];
            }
          } catch (e) {
            console.error('Chat migration (link single session) failed:', e);
          }
        }
        setProjects(projs);
        setCurrentProject(projs[0]);
      } else {
      const defaultProject = {
          id: 'default',
          name: 'Мой проект',
          objects: []
        };
        setProjects([defaultProject]);
        setCurrentProject(defaultProject);
      }
    } catch (error) {
      console.error('Error loading projects:', error);
      const defaultProject = {
        id: 'default',
        name: 'Мой проект',
        objects: []
      };
      setProjects([defaultProject]);
      setCurrentProject(defaultProject);
    }
  };

  const createProject = async (name) => {
    try {
      const data = await api.createProject(name);
      
      if (data.status === 'success') {
        setProjects([...projects, data.project]);
        switchProject(data.project.id);
        return data.project;
      }
    } catch (error) {
      console.error('Error creating project:', error);
    }
  };

  const deleteProject = async (projectId) => {
    if (projects.length === 1) {
      alert('Нельзя удалить последний проект');
      return;
    }

    try {
      const data = await api.deleteProject(projectId);
      
      if (data.status === 'success') {
        const newProjects = projects.filter(p => p.id !== projectId);
        setProjects(newProjects);
        
        if (currentProject?.id === projectId) {
          switchProject(newProjects[0].id);
        }
      }
    } catch (error) {
      console.error('Error deleting project:', error);
    }
  };

  const saveCurrentProject = async () => {
    if (!currentProject) return;
    if (currentProject.id === 'default') {
      return;
    }

    const updatedProject = {
      name: currentProject.name,
      objects: sceneObjects.map((obj) => ({
        id: obj.id,
        name: obj.name,
        visible: obj.visible,
        position: obj.position,
        rotation: obj.rotation,
        scale: obj.scale
      })),
    };
    if (currentProject.conversation_id) {
      updatedProject.conversation_id = currentProject.conversation_id;
    }

    try {
      const data = await api.updateProject(currentProject.id, updatedProject);
      
      if (data.status === 'success') {
        console.log('Project saved successfully');
      }
    } catch (error) {
      console.error('Error saving project:', error);
    }
  };

  const switchProject = (projectId) => {
    const project = projects.find(p => p.id === projectId);
    if (!project) return;

    if (currentProject) {
      saveCurrentProject();
    }

    setCurrentProject(project);
    setSceneObjects([]);
    setSelectedObject(null);
    setChatMessages([]);
  };

  const addChatMessage = (type, text) => {
    setChatMessages((prev) => [...prev, { type, text }]);
  };

  const addSceneObject = (obj) => {
    setSceneObjects(prev => [...prev, obj]);
  };

  const removeSceneObject = (id) => {
    setSceneObjects(prev => prev.filter(obj => obj.id !== id));
    if (selectedObject?.id === id) {
      setSelectedObject(null);
    }
  };

  const toggleObjectVisibility = (id) => {
    setSceneObjects(prev => 
      prev.map(obj => 
        obj.id === id ? { ...obj, visible: !obj.visible } : obj
      )
    );
  };

  useEffect(() => {
    const interval = setInterval(() => {
      saveCurrentProject();
    }, 30000);

    return () => clearInterval(interval);
  }, [currentProject, sceneObjects]);

  const value = {
    projects,
    currentProject,
    sceneObjects,
    selectedObject,
    chatMessages,
    setChatMessages,
    updateCurrentProject,
    setSelectedObject,
    createProject,
    deleteProject,
    switchProject,
    addChatMessage,
    addSceneObject,
    removeSceneObject,
    toggleObjectVisibility,
    saveCurrentProject
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};
