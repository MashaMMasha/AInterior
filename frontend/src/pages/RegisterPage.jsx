import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { authApi } from '../services/api';
import { useAuth } from '../context/AuthContext';
import '../styles/auth.css';

const RegisterPage = () => {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [form, setForm] = useState({
    email: '',
    username: '',
    fullName: '',
    password: '',
    confirmPassword: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  if (user) {
    navigate('/', { replace: true });
    return null;
  }

  const update = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (form.password !== form.confirmPassword) {
      setError('Пароли не совпадают');
      return;
    }

    if (form.password.length < 6) {
      setError('Пароль должен быть не менее 6 символов');
      return;
    }

    setLoading(true);

    try {
      await authApi.register(form.email, form.username, form.fullName, form.password);
      navigate(`/verify-email?email=${encodeURIComponent(form.email)}`);
    } catch (err) {
      setError(err.detail || 'Ошибка регистрации');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo">AInterior</div>
        <p className="auth-subtitle">Создайте аккаунт</p>

        <form className="auth-form" onSubmit={handleSubmit}>
          {error && <div className="auth-error">{error}</div>}

          <div className="auth-field">
            <label>Email</label>
            <input
              type="email"
              value={form.email}
              onChange={update('email')}
              placeholder="your@email.com"
              required
              autoFocus
            />
          </div>

          <div className="auth-field">
            <label>Имя пользователя</label>
            <input
              type="text"
              value={form.username}
              onChange={update('username')}
              placeholder="username"
              required
            />
          </div>

          <div className="auth-field">
            <label>Полное имя</label>
            <input
              type="text"
              value={form.fullName}
              onChange={update('fullName')}
              placeholder="Иван Иванов"
              required
            />
          </div>

          <div className="auth-field">
            <label>Пароль</label>
            <input
              type="password"
              value={form.password}
              onChange={update('password')}
              placeholder="Минимум 6 символов"
              required
            />
          </div>

          <div className="auth-field">
            <label>Подтверждение пароля</label>
            <input
              type="password"
              value={form.confirmPassword}
              onChange={update('confirmPassword')}
              placeholder="Повторите пароль"
              required
            />
          </div>

          <button className="auth-btn" type="submit" disabled={loading}>
            {loading ? 'Регистрация...' : 'Зарегистрироваться'}
          </button>
        </form>

        <p className="auth-link">
          Уже есть аккаунт? <Link to="/login">Войти</Link>
        </p>
      </div>
    </div>
  );
};

export default RegisterPage;
