const CHAT_SERVICE_URL = import.meta.env.VITE_CHAT_SERVICE_URL || 'http://localhost:8003';
const AUTH_SERVICE_URL = import.meta.env.VITE_AUTH_SERVICE_URL || 'http://localhost:8001';
const BACKEND_SERVICE_URL = import.meta.env.VITE_BACKEND_SERVICE_URL || 'http://localhost:8000';

const getAccessToken = () => localStorage.getItem('access_token');
const getRefreshToken = () => localStorage.getItem('refresh_token');

async function tryRefreshToken() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;

  try {
    const response = await fetch(`${AUTH_SERVICE_URL}/auth/refresh`, {
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
    const response = await fetch(`${AUTH_SERVICE_URL}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, username, full_name: fullName, password }),
    });
    const data = await response.json();
    if (!response.ok) throw { status: response.status, ...data };
    return data;
  },

  verifyEmail: async (email, code) => {
    const response = await fetch(`${AUTH_SERVICE_URL}/auth/verify-email`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, code }),
    });
    const data = await response.json();
    if (!response.ok) throw { status: response.status, ...data };
    return data;
  },

  login: async (email, password) => {
    const response = await fetch(`${AUTH_SERVICE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    const data = await response.json();
    if (!response.ok) throw { status: response.status, ...data };
    return data;
  },

  getMe: async () => {
    const response = await authFetch(`${AUTH_SERVICE_URL}/auth/me`);
    if (!response.ok) throw new Error('Unauthorized');
    return response.json();
  },

  resendCode: async (email) => {
    const response = await fetch(`${AUTH_SERVICE_URL}/auth/resend-code`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    });
    return response.json();
  },
};

async function throwIfNotOk(response, fallbackMessage) {
  if (response.ok) return;
  const err = await response.json().catch(() => ({}));
  const d = err.detail;
  let message = fallbackMessage;
  if (typeof d === 'string') {
    message = d;
  } else if (Array.isArray(d) && d[0]?.msg) {
    message = d[0].msg;
  } else if (d && typeof d === 'object' && d.detail) {
    message = String(d.detail);
  }
  throw new Error(message);
}

export const api = {
  uploadModel: async (file) => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await authFetch(`${BACKEND_SERVICE_URL}/upload_model`, {
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
    const response = await authFetch(`${BACKEND_SERVICE_URL}/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: prompt }),
    });

    if (!response.ok) {
      throw new Error('Ошибка генерации модели');
    }

    return response.json();
  },

  sendMessage: async (message, conversationId = null) => {
    const body = { message };
    if (conversationId) body.conversation_id = conversationId;

    const response = await authFetch(`${CHAT_SERVICE_URL}/chat/message`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!response.ok) throw new Error('Ошибка отправки сообщения');
    return response.json();
  },

  getConversations: async () => {
    const response = await authFetch(`${CHAT_SERVICE_URL}/chat/conversations`);
    if (!response.ok) throw new Error('Ошибка получения списка чатов');
    return response.json();
  },
  
  getConversationMessages: async (conversationId) => {
    const response = await authFetch(`${CHAT_SERVICE_URL}/chat/conversation/${conversationId}/messages`);
    if (!response.ok) throw new Error('Ошибка получения сообщений');
    return response.json();
  },

  getProjects: async () => {
    const response = await authFetch(`${BACKEND_SERVICE_URL}/projects`);
    await throwIfNotOk(response, 'Ошибка загрузки проектов');
    return response.json();
  },

  createProject: async (name) => {
    const response = await authFetch(`${BACKEND_SERVICE_URL}/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    await throwIfNotOk(response, 'Ошибка создания проекта');
    return response.json();
  },

  updateProject: async (projectId, project) => {
    const response = await authFetch(`${BACKEND_SERVICE_URL}/projects/${projectId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(project),
    });
    await throwIfNotOk(response, 'Ошибка обновления проекта');
    return response.json();
  },

  deleteProject: async (projectId) => {
    const response = await authFetch(`${BACKEND_SERVICE_URL}/projects/${projectId}`, {
      method: 'DELETE',
    });
    await throwIfNotOk(response, 'Ошибка удаления проекта');
    return response.json();
  },
};
