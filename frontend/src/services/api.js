const getAccessToken = () => localStorage.getItem('access_token');
const getRefreshToken = () => localStorage.getItem('refresh_token');

async function tryRefreshToken() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;

  try {
    const response = await fetch('/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (response.ok) {
      const data = await response.json();
      localStorage.setItem('access_token', data.access_token);
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

export async function authFetch(url, options = {}) {
  const token = getAccessToken();
  const headers = { ...options.headers };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  let response = await fetch(url, { ...options, headers });

  if (response.status === 401) {
    const refreshed = await tryRefreshToken();
    if (refreshed) {
      headers['Authorization'] = `Bearer ${getAccessToken()}`;
      response = await fetch(url, { ...options, headers });
    } else {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      window.location.href = '/login';
      throw new Error('Session expired');
    }
  }

  return response;
}

export const authApi = {
  register: async (email, username, fullName, password) => {
    const response = await fetch('/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, username, full_name: fullName, password }),
    });
    const data = await response.json();
    if (!response.ok) throw { status: response.status, ...data };
    return data;
  },

  verifyEmail: async (email, code) => {
    const response = await fetch('/auth/verify-email', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, code }),
    });
    const data = await response.json();
    if (!response.ok) throw { status: response.status, ...data };
    return data;
  },

  login: async (email, password) => {
    const response = await fetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    const data = await response.json();
    if (!response.ok) throw { status: response.status, ...data };
    return data;
  },

  getMe: async () => {
    const response = await authFetch('/auth/me');
    if (!response.ok) throw new Error('Unauthorized');
    return response.json();
  },

  resendCode: async (email) => {
    const response = await fetch('/auth/resend-code', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    });
    return response.json();
  },
};

export const api = {
  uploadModel: async (file) => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await authFetch('/upload_model', {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Ошибка загрузки');
    }

    return response.json();
  },

  generateModel: async (prompt) => {
    const response = await authFetch('/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: prompt }),
    });

    if (!response.ok) {
      throw new Error('Ошибка генерации модели');
    }

    return response.json();
  },

  getProjects: async () => {
    const response = await authFetch('/projects');
    return response.json();
  },

  createProject: async (name) => {
    const response = await authFetch(`/projects?name=${encodeURIComponent(name)}`, {
      method: 'POST',
    });
    return response.json();
  },

  updateProject: async (projectId, project) => {
    const response = await authFetch(`/projects/${projectId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(project),
    });
    return response.json();
  },

  deleteProject: async (projectId) => {
    const response = await authFetch(`/projects/${projectId}`, {
      method: 'DELETE',
    });
    return response.json();
  },
};
