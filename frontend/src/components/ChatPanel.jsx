import React, { useState, useRef, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { api } from '../services/api';
import './ChatPanel.css';

const WELCOME_TEXT =
  'Привет! Я помогу вам создать интерьер мечты. Опишите, какую квартиру вы хотите создать.';

const storageKeyForProject = (projectId) => `ainterior_conversation_${projectId}`;
const TERMINAL_STAGES = new Set(['completed', 'error', 'failed']);
const hasScenePlan = (stage) => Boolean(stage?.scene_plan);
const countSceneObjects = (scenePlan) => {
  if (!scenePlan) return 0;
  return [
    ...(scenePlan.objects || []),
    ...(scenePlan.floor_objects || []),
    ...(scenePlan.wall_objects || []),
    ...(scenePlan.small_objects || []),
    ...(scenePlan.ceiling_objects || []),
  ].length;
};

const completionText = (scenePlan) => {
  const count = countSceneObjects(scenePlan);
  if (count === 0) {
    return 'Сцена сгенерирована, но без интерьерных объектов (только геометрия/проемы).';
  }
  return `Сцена успешно сгенерирована! Объектов интерьера: ${count}.`;
};

const buildMessagesFromApiHistory = (msgs, onModelLoad) => {
  if (!msgs || msgs.length === 0) {
    return [{ type: 'assistant', text: WELCOME_TEXT }];
  }
  const out = [];
  for (const m of msgs) {
    out.push({ type: 'user', text: m.content });
    if (m.stages && m.stages.length > 0) {
      const lastStage = m.stages[m.stages.length - 1];
      if (lastStage.stage_name === 'completed') {
        out.push({ type: 'assistant', text: completionText(lastStage.scene_plan) });
      }
      if (onModelLoad && hasScenePlan(lastStage)) {
          setTimeout(() => onModelLoad({ type: 'scene_plan', data: lastStage.scene_plan }), 500);
      }
    }
  }
  return out;
};

const getLastStage = (interaction) => {
  if (!interaction?.stages?.length) return null;
  return interaction.stages[interaction.stages.length - 1];
};

const ChatPanel = ({ onModelLoad }) => {
  const { chatMessages, addChatMessage, setChatMessages, currentProject, updateCurrentProject } = useApp();
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const pollRef = useRef(null);
  const completionNotifiedRef = useRef(new Set());

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
          setIsLoading(false);
          setCurrentStage('');
        }
        return;
      }

      setConversationId(convId);
      try {
        const msgs = await api.getConversationMessages(convId);
        if (cancelled) return;
        setChatMessages(buildMessagesFromApiHistory(msgs, onModelLoadRef.current));
        const latestInteraction = msgs[msgs.length - 1];
        const lastStage = getLastStage(latestInteraction);
        const stageName = lastStage?.stage_name;

        if (latestInteraction && !TERMINAL_STAGES.has(stageName || '')) {
          setIsLoading(true);
          setCurrentStage(stageName ? `Текущий этап: ${stageName}` : 'Запуск генерации...');
          startPolling(convId, latestInteraction.interaction_id);
        } else {
          setIsLoading(false);
          setCurrentStage('');
        }
      } catch (e) {
        console.error('Failed to load conversation history:', e);
        if (!cancelled) {
          setChatMessages([{ type: 'assistant', text: WELCOME_TEXT }]);
          setIsLoading(false);
          setCurrentStage('');
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

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const startPolling = (targetConversationId, targetInteractionId) => {
    stopPolling();
    const tick = async () => {
      try {
        const msgs = await api.getConversationMessages(targetConversationId);
        const interaction =
          msgs.find((m) => m.interaction_id === targetInteractionId) || msgs[msgs.length - 1];
        if (!interaction) return;

        const lastStage = getLastStage(interaction);
        const name = lastStage?.stage_name;

        if (!name) {
          setCurrentStage('Запуск генерации...');
          return;
        }

        if (name === 'error' || name === 'failed') {
          stopPolling();
          setIsLoading(false);
          setCurrentStage('');
          if (!completionNotifiedRef.current.has(interaction.interaction_id)) {
            completionNotifiedRef.current.add(interaction.interaction_id);
            addChatMessage('assistant', 'Произошла ошибка при генерации сцены.');
          }
          return;
        }

        if (onModelLoadRef.current && hasScenePlan(lastStage)) {
          onModelLoadRef.current({ type: 'scene_plan', data: lastStage.scene_plan });
        }

        if (name === 'completed') {
          stopPolling();
          setIsLoading(false);
          setCurrentStage('');
          if (!completionNotifiedRef.current.has(interaction.interaction_id)) {
            completionNotifiedRef.current.add(interaction.interaction_id);
            addChatMessage('assistant', completionText(lastStage?.scene_plan));
          }
          return;
        }

        setCurrentStage(`Текущий этап: ${name}`);
      } catch (e) {
        console.error('Ошибка поллинга статуса:', e);
      }
    };

    tick();
    pollRef.current = setInterval(tick, 2000);
  };

  const handleSend = async () => {
    if (!inputValue.trim() || isLoading) return;
    if (!currentProject) return;

    const message = inputValue.trim();
    const project = currentProject;
    addChatMessage('user', message);
    setInputValue('');
    setIsLoading(true);
    setCurrentStage('Запуск генерации...');

    stopPolling();

    const sendId = getConversationIdForProject(project) || conversationId;

    try {
      const result = await api.sendMessage(message, sendId);
      await persistConversationId(project, result.conversation_id);
      setConversationId(result.conversation_id);
      startPolling(result.conversation_id, result.interaction_id);
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
