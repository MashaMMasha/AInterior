import React, { useState, useRef, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { authApi } from '../services/api';
import { useAuth } from '../context/AuthContext';
import '../styles/auth.css';

const CODE_LENGTH = 6;

const VerifyEmailPage = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const email = searchParams.get('email') || '';
  const { saveTokens } = useAuth();

  const [digits, setDigits] = useState(Array(CODE_LENGTH).fill(''));
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);
  const inputRefs = useRef([]);

  useEffect(() => {
    if (!email) navigate('/register', { replace: true });
  }, [email, navigate]);

  useEffect(() => {
    if (resendCooldown <= 0) return;
    const timer = setTimeout(() => setResendCooldown(resendCooldown - 1), 1000);
    return () => clearTimeout(timer);
  }, [resendCooldown]);

  const handleChange = (index, value) => {
    if (!/^\d*$/.test(value)) return;

    const newDigits = [...digits];
    newDigits[index] = value.slice(-1);
    setDigits(newDigits);

    if (value && index < CODE_LENGTH - 1) {
      inputRefs.current[index + 1]?.focus();
    }

    const code = newDigits.join('');
    if (code.length === CODE_LENGTH) {
      submitCode(code);
    }
  };

  const handleKeyDown = (index, e) => {
    if (e.key === 'Backspace' && !digits[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  };

  const handlePaste = (e) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, CODE_LENGTH);
    if (!pasted) return;

    const newDigits = Array(CODE_LENGTH).fill('');
    for (let i = 0; i < pasted.length; i++) {
      newDigits[i] = pasted[i];
    }
    setDigits(newDigits);

    const focusIndex = Math.min(pasted.length, CODE_LENGTH - 1);
    inputRefs.current[focusIndex]?.focus();

    if (pasted.length === CODE_LENGTH) {
      submitCode(pasted);
    }
  };

  const submitCode = async (code) => {
    setError('');
    setLoading(true);

    try {
      const data = await authApi.verifyEmail(email, code);
      saveTokens(data.access_token, data.refresh_token, data.user);
      navigate('/', { replace: true });
    } catch (err) {
      setError(err.detail || 'Неверный код');
      setDigits(Array(CODE_LENGTH).fill(''));
      inputRefs.current[0]?.focus();
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    setResendCooldown(60);
    try {
      await authApi.resendCode(email);
    } catch {
      setError('Ошибка отправки кода');
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo">AInterior</div>
        <p className="auth-subtitle">
          Код отправлен на <strong>{email}</strong>
        </p>

        {error && <div className="auth-error">{error}</div>}

        <div className="auth-code-inputs" onPaste={handlePaste}>
          {digits.map((digit, i) => (
            <input
              key={i}
              ref={(el) => (inputRefs.current[i] = el)}
              type="text"
              inputMode="numeric"
              maxLength={1}
              value={digit}
              onChange={(e) => handleChange(i, e.target.value)}
              onKeyDown={(e) => handleKeyDown(i, e)}
              autoFocus={i === 0}
              disabled={loading}
            />
          ))}
        </div>

        {loading && <div className="auth-info" style={{ marginTop: 16 }}>Проверка кода...</div>}

        <div className="auth-resend">
          {resendCooldown > 0 ? (
            <span>Отправить повторно через {resendCooldown}с</span>
          ) : (
            <button onClick={handleResend}>Отправить код повторно</button>
          )}
        </div>

        <p className="auth-link">
          <a href="/login">Вернуться ко входу</a>
        </p>
      </div>
    </div>
  );
};

export default VerifyEmailPage;
