import React, { useState, useRef, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { api } from '../services/api';
import './ChatPanel.css';

const WELCOME_TEXT =
  'Привет! Я помогу вам создать интерьер мечты. Опишите, какую квартиру вы хотите создать.';

const storageKeyForProject = (projectId) => `ainterior_conversation_${projectId}`;

const buildMessagesFromApiHistory = (msgs, onModelLoad) => {
  if (!msgs || msgs.length === 0) {
    return [{ type: 'assistant', text: WELCOME_TEXT }];
  }
  const out = [];
  for (const m of msgs) {
    out.push({ type: 'user', text: m.content });
    if (m.stages && m.stages.length > 0) {
      const lastStage = m.stages[m.stages.length - 1];
      if (lastStage.stage_name === 'object_selection' || lastStage.stage_name === 'completed') {
        out.push({ type: 'assistant', text: 'Сцена сгенерирована!' });
        if (onModelLoad && lastStage.scene_plan) {
          setTimeout(() => onModelLoad({ type: 'scene_plan', data: lastStage.scene_plan }), 500);
        }
      }
    }
  }
  return out;
};

const ChatPanel = ({ onModelLoad }) => {
  const { chatMessages, addChatMessage, setChatMessages, currentProject, updateCurrentProject } = useApp();
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const pollRef = useRef(null);

  const [conversationId, setConversationId] = useState(null);
  const [currentStage, setCurrentStage] = useState('');
  const onModelLoadRef = useRef(onModelLoad);
  onModelLoadRef.current = onModelLoad;

  const getConversationIdForProject = (project) => {
    if (!project) return null;
    if (project.conversation_id) return project.conversation_id;
    return localStorage.getItem(storageKeyForProject(project.id));
  };

  const persistConversationId = async (project, convId) => {
    if (!project || !convId) return;
    if (project.id === 'default') {
      localStorage.setItem(storageKeyForProject(project.id), convId);
      updateCurrentProject({ conversation_id: convId });
    } else {
      await api.updateProject(project.id, { conversation_id: convId });
      updateCurrentProject({ conversation_id: convId });
    }
  };

  useEffect(() => {
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, []);

  // При смене проекта загружаем его чат (сервер + привязка в проекте)
  useEffect(() => {
    if (!currentProject) return;
    const project = currentProject;
    let cancelled = false;

    (async () => {
      const convId = getConversationIdForProject(project);
      setCurrentStage('');

      if (!convId) {
        if (!cancelled) {
          setChatMessages([{ type: 'assistant', text: WELCOME_TEXT }]);
          setConversationId(null);
        }
        return;
      }

      setConversationId(convId);
      try {
        const msgs = await api.getConversationMessages(convId);
        if (cancelled) return;
        setChatMessages(buildMessagesFromApiHistory(msgs, onModelLoadRef.current));
      } catch (e) {
        console.error('Failed to load conversation history:', e);
        if (!cancelled) {
          setChatMessages([{ type: 'assistant', text: WELCOME_TEXT }]);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [currentProject?.id, setChatMessages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [chatMessages]);

  const handleSend = async () => {
    if (!inputValue.trim() || isLoading) return;
    if (!currentProject) return;

    const message = inputValue.trim();
    const project = currentProject;
    addChatMessage('user', message);
    setInputValue('');
    setIsLoading(true);
    setCurrentStage('Запуск генерации...');

    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }

    const sendId = getConversationIdForProject(project) || conversationId;

    try {
      const result = await api.sendMessage(message, sendId);
      await persistConversationId(project, result.conversation_id);
      setConversationId(result.conversation_id);

      const pollInterval = setInterval(async () => {
        try {
          const msgs = await api.getConversationMessages(result.conversation_id);
          const currentInteraction = msgs.find((m) => m.interaction_id === result.interaction_id);

          if (currentInteraction && currentInteraction.stages && currentInteraction.stages.length > 0) {
            const lastStage = currentInteraction.stages[currentInteraction.stages.length - 1];
            const name = lastStage.stage_name;

            if (name === 'error' || name === 'failed') {
              if (pollRef.current) {
                clearInterval(pollRef.current);
                pollRef.current = null;
              }
              setIsLoading(false);
              setCurrentStage('');
              addChatMessage('assistant', 'Произошла ошибка при генерации сцены.');
            } else if (name === 'windows' || name === 'object_selection' || name === 'completed') {
              if (onModelLoad && lastStage.scene_plan) {
                onModelLoad({ type: 'scene_plan', data: lastStage.scene_plan });
              }
              if (name === 'completed') {
                if (pollRef.current) {
                  clearInterval(pollRef.current);
                  pollRef.current = null;
                }
                setIsLoading(false);
                setCurrentStage('');
                addChatMessage('assistant', 'Сцена успешно сгенерирована!');
              } else {
                setCurrentStage(`Текущий этап: ${name}`);
              }
            } else {
              setCurrentStage(`Текущий этап: ${name}`);
            }
          }
        } catch (e) {
          console.error('Ошибка поллинга статуса:', e);
        }
      }, 2000);
      pollRef.current = pollInterval;
    } catch (error) {
      console.error('Chat error:', error);
      addChatMessage(
        'assistant',
        'К сожалению, произошла ошибка. Попробуйте переформулировать запрос.'
      );
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
            {currentStage && (
              <div style={{ marginTop: '8px', fontSize: '0.85em', opacity: 0.8 }}>{currentStage}</div>
            )}
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
          disabled={isLoading || !inputValue.trim() || !currentProject}
        >
          {isLoading ? 'Отправка...' : 'Отправить'}
        </button>
      </div>
    </div>
  );
};

export default ChatPanel;
