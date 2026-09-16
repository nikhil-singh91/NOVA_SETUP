import React, { useState, useEffect } from 'react';
import { AvatarState, ScreenTab, ChatMessage, ActiveTask, ActivityItem, PrivacyState, UIEventPayload } from './types';
import { backendApi } from './services/backendApi';
import { Sidebar } from './components/Navigation/Sidebar';
import { TopBar } from './components/Header/TopBar';
import { HomeScreen } from './screens/HomeScreen';
import { ChatScreen } from './screens/ChatScreen';
import { VoiceScreen } from './screens/VoiceScreen';
import { TasksScreen } from './screens/TasksScreen';
import { ActivityScreen } from './screens/ActivityScreen';
import { SystemScreen } from './screens/SystemScreen';
import { SettingsScreen } from './screens/SettingsScreen';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<ScreenTab>('home');
  const [avatarState, setAvatarState] = useState<AvatarState>('idle');
  const [statusMessage, setStatusMessage] = useState<string>('Ready.');
  const [userTranscript, setUserTranscript] = useState<string>('');
  const [novaTranscript, setNovaTranscript] = useState<string>('');
  const [isListening, setIsListening] = useState<boolean>(false);
  const [isBackendConnected, setIsBackendConnected] = useState<boolean>(false);
  const [privacyState, setPrivacyState] = useState<PrivacyState>({
    microphone_active: false,
    screen_observation_active: false,
    screen_recording_active: false,
    camera_active: false,
    task_executing: false,
  });

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [activeTask, setActiveTask] = useState<ActiveTask | null>(null);
  const [activities, setActivities] = useState<ActivityItem[]>([]);

  // Subscribe to WebSocket events & connection health
  useEffect(() => {
    const unsubStatus = backendApi.subscribeConnectionStatus((connected) => {
      setIsBackendConnected(connected);
      if (!connected) {
        setAvatarState('offline');
        setStatusMessage('Backend Disconnected (127.0.0.1:8765)');
      } else {
        setAvatarState('idle');
        setStatusMessage('Connected to NOVA.');
      }
    });

    const unsubEvents = backendApi.subscribeEvents((event: UIEventPayload) => {
      handleBackendEvent(event);
    });

    return () => {
      unsubStatus();
      unsubEvents();
    };
  }, []);

  const handleBackendEvent = (event: UIEventPayload) => {
    // 1. Update Avatar State
    if (event.avatar_state) {
      setAvatarState(event.avatar_state);
    }

    // 2. Update Status Message
    if (event.message) {
      setStatusMessage(event.message);
    }

    // 3. Update Privacy Indicators
    if (event.privacy) {
      setPrivacyState(event.privacy);
    }

    // 4. Record in Activities
    if (event.message) {
      setActivities((prev) => [
        {
          timestamp: event.timestamp,
          event_type: event.event_type,
          avatar_state: event.avatar_state,
          message: event.message,
        },
        ...prev.slice(0, 49),
      ]);
    }

    // 5. Handle Event-Specific Payloads
    switch (event.event_type) {
      case 'voice_listening_started':
        setIsListening(true);
        setPrivacyState((p) => ({ ...p, microphone_active: true }));
        break;

      case 'voice_listening_stopped':
        setIsListening(false);
        setPrivacyState((p) => ({ ...p, microphone_active: false }));
        break;

      case 'voice_transcript_partial':
      case 'voice_transcript_final':
        if (event.message) {
          setUserTranscript(event.message);
        }
        break;

      case 'command_received':
        setUserTranscript(event.data?.text || event.message);
        setMessages((prev) => [
          ...prev,
          {
            id: event.event_id,
            sender: 'user',
            text: event.data?.text || event.message,
            timestamp: event.timestamp,
            status: 'Processing',
          },
        ]);
        break;

      case 'speaking_started':
      case 'command_completed':
        if (event.message) {
          setNovaTranscript(event.message);
          setMessages((prev) => [
            ...prev,
            {
              id: event.event_id,
              sender: 'nova',
              text: event.message,
              timestamp: event.timestamp,
              status: 'Completed',
              actionCard: event.data?.action_card,
            },
          ]);
        }
        break;

      case 'task_started':
      case 'task_planned':
        setActiveTask({
          task_id: event.task_id || 'task_active',
          goal: event.message,
          status: 'running',
          steps: event.data?.steps || [
            { step_index: 1, capability_name: 'fs.create_folder', description: 'Initialize project structure', status: 'running' },
            { step_index: 2, capability_name: 'code.create_project', description: 'Generate starter code files', status: 'pending' },
            { step_index: 3, capability_name: 'verification', description: 'Verify filesystem structure', status: 'pending' },
          ],
          current_step_index: 1,
          total_steps: event.data?.steps?.length || 3,
        });
        setPrivacyState((p) => ({ ...p, task_executing: true }));
        break;

      case 'task_step_started':
        setActiveTask((prev) => {
          if (!prev) return null;
          const sIdx = (event.data?.step_index as number) ?? prev.current_step_index;
          return {
            ...prev,
            current_step_index: sIdx,
            status: 'running',
          };
        });
        break;

      case 'task_step_completed':
        if (activeTask) {
          setActiveTask((prev) => {
            if (!prev) return null;
            return {
              ...prev,
              current_step_index: Math.min(prev.total_steps, prev.current_step_index + 1),
            };
          });
        }
        break;

      case 'task_step_failed':
        setActiveTask((prev) => (prev ? { ...prev, status: 'failed' } : null));
        setPrivacyState((p) => ({ ...p, task_executing: false }));
        break;

      case 'task_replanning':
        setActiveTask((prev) => (prev ? { ...prev, status: 'running' } : null));
        break;

      case 'task_completed':
        setActiveTask((prev) => (prev ? { ...prev, status: 'completed' } : null));
        setPrivacyState((p) => ({ ...p, task_executing: false }));
        break;

      case 'task_cancelled':
        setActiveTask((prev) => (prev ? { ...prev, status: 'cancelled' } : null));
        setPrivacyState((p) => ({ ...p, task_executing: false }));
        break;
    }
  };

  const handleSubmitCommand = async (text: string) => {
    setMessages((prev) => [
      ...prev,
      {
        id: Math.random().toString(),
        sender: 'user',
        text,
        timestamp: Date.now() / 1000,
        status: 'Sent',
      },
    ]);
    setUserTranscript(text);
    setAvatarState('thinking');
    await backendApi.submitCommand(text, 'ui_chat');
  };

  const handleToggleVoice = async () => {
    if (isListening) {
      setIsListening(false);
    } else {
      setIsListening(true);
      await backendApi.triggerVoice();
    }
  };

  const handleCancelTask = async () => {
    await backendApi.cancelTasks();
  };

  return (
    <div className="flex h-screen w-screen bg-[#080c14] text-slate-100 overflow-hidden select-none font-sans">
      {/* Left Navigation Sidebar */}
      <Sidebar
        currentTab={currentTab}
        onTabChange={setCurrentTab}
        isBackendConnected={isBackendConnected}
        isMicrophoneActive={privacyState.microphone_active || isListening}
      />

      {/* Main Workspace Area */}
      <div className="flex-1 flex flex-col h-full overflow-hidden relative">
        {/* Top Header with Sensor Privacy Badges */}
        <TopBar
          privacy={privacyState}
          onCancelTask={handleCancelTask}
          isTaskRunning={privacyState.task_executing || activeTask?.status === 'running'}
        />

        {/* Workspace Screen Viewport */}
        <main className="flex-1 flex overflow-hidden relative">
          {currentTab === 'home' && (
            <HomeScreen
              avatarState={avatarState}
              statusMessage={statusMessage}
              onSubmitCommand={handleSubmitCommand}
              onNavigateTab={setCurrentTab}
            />
          )}

          {currentTab === 'chat' && (
            <ChatScreen
              messages={messages}
              avatarState={avatarState}
              onSubmitCommand={handleSubmitCommand}
              onTriggerVoice={handleToggleVoice}
              isListening={isListening}
            />
          )}

          {currentTab === 'voice' && (
            <VoiceScreen
              avatarState={avatarState}
              userTranscript={userTranscript}
              novaTranscript={novaTranscript}
              isListening={isListening}
              onToggleVoice={handleToggleVoice}
              onCancelTask={handleCancelTask}
              isTaskRunning={privacyState.task_executing}
            />
          )}

          {currentTab === 'tasks' && (
            <TasksScreen
              activeTask={activeTask}
              onCancelTask={handleCancelTask}
            />
          )}

          {currentTab === 'activity' && (
            <ActivityScreen activities={activities} />
          )}

          {currentTab === 'system' && (
            <SystemScreen isBackendConnected={isBackendConnected} />
          )}

          {currentTab === 'settings' && <SettingsScreen />}
        </main>
      </div>
    </div>
  );
};
