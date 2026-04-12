import React, { useState, useRef, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { api } from '../services/api';
import './ChatPanel.css';

const ChatPanel = ({ onModelLoad }) => {
  const { chatMessages, addChatMessage } = useApp();
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [chatMessages]);

  const handleSend = async () => {
    if (!inputValue.trim() || isLoading) return;

    const message = inputValue.trim();
    addChatMessage('user', message);
    setInputValue('');
    setIsLoading(true);

    try {
      const result = await api.generateModel(message);
      
      if (result.status === 'success') {
        if (result.model_url) {
          addChatMessage('assistant', result.message || 'Модель сгенерирована! Загружаю на сцену...');
          if (onModelLoad) {
            onModelLoad(result.model_url, result.filename || 'generated_model.glb');
          }
        } else {
          addChatMessage('assistant', result.message);
        }
      } else {
        addChatMessage('assistant', result.message || 'Произошла ошибка при генерации модели');
      }
    } catch (error) {
      console.error('Chat error:', error);
      addChatMessage('assistant', 'К сожалению, произошла ошибка. Попробуйте загрузить модель вручную или переформулируйте запрос.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-panel">
      <div className="chat-messages">
        {chatMessages.map((msg, index) => (
          <div key={index} className={`chat-message ${msg.type}`}>
            {msg.text}
          </div>
        ))}
        {isLoading && (
          <div className="chat-message assistant loading-message">
            <div className="loading-dots">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      
      <div className="chat-input-container">
        <textarea
          className="chat-input"
          placeholder="Например: добавь современный диван серого цвета..."
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyPress={handleKeyPress}
          disabled={isLoading}
        />
        <button
          className="chat-send-btn"
          onClick={handleSend}
          disabled={isLoading || !inputValue.trim()}
        >
          {isLoading ? 'Отправка...' : 'Отправить'}
        </button>
      </div>
    </div>
  );
};

export default ChatPanel;
