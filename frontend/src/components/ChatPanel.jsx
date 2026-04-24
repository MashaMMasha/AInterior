import React, { useState, useRef, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { api } from '../services/api';
import './ChatPanel.css';

const ChatPanel = ({ onModelLoad }) => {
  const { chatMessages, addChatMessage } = useApp();
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const [conversationId, setConversationId] = useState(null);
  const [currentStage, setCurrentStage] = useState('');

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
    setCurrentStage('Запуск генерации...');

    try {
      const result = await api.sendMessage(message, conversationId);
      setConversationId(result.conversation_id);
      
      // Поллинг статуса генерации
      const pollInterval = setInterval(async () => {
        try {
          const msgs = await api.getConversationMessages(result.conversation_id);
          const currentInteraction = msgs.find(m => m.interaction_id === result.interaction_id);
          
          if (currentInteraction && currentInteraction.stages && currentInteraction.stages.length > 0) {
            const lastStage = currentInteraction.stages[currentInteraction.stages.length - 1];
            
            if (lastStage.stage_name === 'completed') {
              clearInterval(pollInterval);
              setIsLoading(false);
              setCurrentStage('');
              addChatMessage('assistant', 'Сцена успешно сгенерирована!');
              
              // В obllomov результат — это JSON сцены (scene_plan).
              // Если требуется дальнейшая загрузка 3D модели, здесь можно вызвать onModelLoad, 
              // если бэкенд умеет собирать GLB, либо просто обработать JSON.
              console.log('Сгенерированная сцена:', lastStage.scene_plan);
            } else if (lastStage.stage_name === 'error' || lastStage.stage_name === 'failed') {
              clearInterval(pollInterval);
              setIsLoading(false);
              setCurrentStage('');
              addChatMessage('assistant', 'Произошла ошибка при генерации сцены.');
            } else {
              setCurrentStage(`Текущий этап: ${lastStage.stage_name}`);
            }
          }
        } catch (e) {
          console.error('Ошибка поллинга статуса:', e);
        }
      }, 2000);
      
    } catch (error) {
      console.error('Chat error:', error);
      addChatMessage('assistant', 'К сожалению, произошла ошибка. Попробуйте переформулировать запрос.');
      setIsLoading(false);
      setCurrentStage('');
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
            {currentStage && <div style={{marginTop: '8px', fontSize: '0.85em', opacity: 0.8}}>{currentStage}</div>}
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
