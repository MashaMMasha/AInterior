import React from 'react';
import { useApp } from '../context/AppContext';
import './Header.css';

const Header = ({ onToggleLeftPanel, onToggleRightPanel, isLeftCollapsed, isRightCollapsed }) => {
  const { projects, currentProject, createProject, deleteProject, switchProject } = useApp();

  const handleCreateProject = () => {
    const projectName = prompt('Название нового проекта:', `Проект ${projects.length + 1}`);
    if (projectName) {
      createProject(projectName);
    }
  };

  const handleCloseProject = (e, projectId) => {
    e.stopPropagation();
    deleteProject(projectId);
  };

  return (
    <div className="header">
      <div className="header-left">
        <div className="logo">AInterior</div>
        <div className="projects-tabs">
          {projects.map(project => (
            <button
              key={project.id}
              className={`project-tab ${currentProject?.id === project.id ? 'active' : ''}`}
              onClick={() => switchProject(project.id)}
            >
              <span>{project.name}</span>
              <span
                className="project-tab-close"
                onClick={(e) => handleCloseProject(e, project.id)}
              >
                ×
              </span>
            </button>
          ))}
          <button className="new-project-btn" onClick={handleCreateProject} title="Новый проект">
            +
          </button>
        </div>
      </div>
      <div className="header-right">
        <button 
          className={`panel-toggle-btn ${isLeftCollapsed ? 'collapsed' : ''}`}
          onClick={onToggleLeftPanel}
          title={isLeftCollapsed ? 'Показать чат (⌘B)' : 'Скрыть чат (⌘B)'}
        >
          <svg viewBox="0 0 20 20" fill="none">
            <rect x="3" y="4" width="6" height="12" rx="1" stroke="currentColor" strokeWidth="1.5"/>
            <line x1="11" y1="7" x2="16" y2="7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            <line x1="11" y1="10" x2="16" y2="10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            <line x1="11" y1="13" x2="14" y2="13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        </button>
        <button 
          className={`panel-toggle-btn ${isRightCollapsed ? 'collapsed' : ''}`}
          onClick={onToggleRightPanel}
          title={isRightCollapsed ? 'Показать панель объектов (⌘\\)' : 'Скрыть панель объектов (⌘\\)'}
        >
          <svg viewBox="0 0 20 20" fill="none">
            <rect x="11" y="4" width="6" height="12" rx="1" stroke="currentColor" strokeWidth="1.5"/>
            <line x1="4" y1="7" x2="9" y2="7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            <line x1="4" y1="10" x2="9" y2="10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            <line x1="4" y1="13" x2="7" y2="13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        </button>
      </div>
    </div>
  );
};

export default Header;
