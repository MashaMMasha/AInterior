import React, { createContext, useContext, useState, useEffect } from 'react';
import { authFetch } from '../services/api';

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
  const [chatMessages, setChatMessages] = useState([
    {
      type: 'assistant',
      text: 'Привет! Я помогу вам создать интерьер мечты. Опишите какую мебель или элементы вы хотите добавить в вашу сцену.'
    }
  ]);

  useEffect(() => {
    loadProjects();
  }, []);

  const loadProjects = async () => {
    try {
      const response = await authFetch('/projects');
      const data = await response.json();
      
      if (data.status === 'success' && data.projects.length > 0) {
        setProjects(data.projects);
        setCurrentProject(data.projects[0]);
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
      const response = await authFetch(`/projects?name=${encodeURIComponent(name)}`, {
        method: 'POST'
      });
      const data = await response.json();
      
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
      const response = await authFetch(`/projects/${projectId}`, {
        method: 'DELETE'
      });
      
      const data = await response.json();
      
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

    const updatedProject = {
      ...currentProject,
      objects: sceneObjects.map(obj => ({
        id: obj.id,
        name: obj.name,
        visible: obj.visible,
        position: obj.position,
        rotation: obj.rotation,
        scale: obj.scale
      }))
    };

    try {
      const response = await authFetch(`/projects/${currentProject.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(updatedProject)
      });
      
      const data = await response.json();
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
    setChatMessages([
      {
        type: 'assistant',
        text: 'Привет! Я помогу вам создать интерьер мечты. Опишите какую мебель или элементы вы хотите добавить в вашу сцену.'
      }
    ]);
  };

  const addChatMessage = (type, text) => {
    setChatMessages(prev => [...prev, { type, text }]);
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
