const API_BASE_URL = '';

export const api = {
  // Модели
  uploadModel: async (file) => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch('/upload_model', {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Ошибка загрузки');
    }

    return response.json();
  },

  // Генерация модели через чат
  generateModel: async (prompt) => {
    const response = await fetch('/generate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ text: prompt })
    });

    if (!response.ok) {
      throw new Error('Ошибка генерации модели');
    }

    return response.json();
  },

  // Проекты
  getProjects: async () => {
    const response = await fetch('/projects');
    return response.json();
  },

  createProject: async (name) => {
    const response = await fetch(`/projects?name=${encodeURIComponent(name)}`, {
      method: 'POST'
    });
    return response.json();
  },

  updateProject: async (projectId, project) => {
    const response = await fetch(`/projects/${projectId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(project)
    });
    return response.json();
  },

  deleteProject: async (projectId) => {
    const response = await fetch(`/projects/${projectId}`, {
      method: 'DELETE'
    });
    return response.json();
  }
};
