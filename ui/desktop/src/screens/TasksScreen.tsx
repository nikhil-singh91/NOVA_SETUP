import React from 'react';
import { ActiveTask } from '../types';
import { Layers, CheckCircle2, Clock, AlertTriangle, Circle, Square } from 'lucide-react';

interface TasksScreenProps {
  activeTask: ActiveTask | null;
  onCancelTask: () => void;
}

export const TasksScreen: React.FC<TasksScreenProps> = ({
  activeTask,
  onCancelTask,
}) => {
  return (
    <div className="flex-1 h-full flex flex-col p-6 overflow-y-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b border-white/5">
        <div>
          <h2 className="text-lg font-bold font-display text-white">Autonomous Task Agent</h2>
          <p className="text-xs text-slate-400">Multi-step goal decomposition, dynamic replanning & verification</p>
        </div>
        {activeTask && activeTask.status === 'running' && (
          <button
            onClick={onCancelTask}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-rose-500/20 hover:bg-rose-500/30 border border-rose-500/40 text-rose-200 text-xs font-semibold transition-colors"
          >
            <Square className="w-3.5 h-3.5 fill-rose-400 text-rose-400" />
            <span>Cancel Goal</span>
          </button>
        )}
      </div>

      {/* Task Content */}
      {!activeTask ? (
        <div className="flex-1 flex flex-col items-center justify-center text-center text-slate-500 space-y-3 py-12">
          <Layers className="w-12 h-12 text-cyan-500/30" />
          <h3 className="text-base font-semibold text-slate-300">No Active Multi-Step Task</h3>
          <p className="text-xs text-slate-500 max-w-sm">
            Try issuing a compound goal like:
            <br />
            <span className="font-mono text-cyan-400/80">"Create a folder called DSA Project on Desktop with Arrays, LinkedList and Trees folders"</span>
          </p>
        </div>
      ) : (
        <div className="space-y-6 max-w-3xl">
          {/* Goal Overview Card */}
          <div className="p-5 rounded-2xl glass-card border-white/10 space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-cyan-400 uppercase tracking-wider">Active Goal</span>
              <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-mono font-semibold uppercase ${
                activeTask.status === 'completed'
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                  : activeTask.status === 'failed'
                  ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                  : 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 animate-pulse'
              }`}>
                {activeTask.status}
              </span>
            </div>

            <h3 className="text-base font-bold text-white leading-snug">{activeTask.goal}</h3>

            {/* Progress Bar */}
            <div className="space-y-1.5">
              <div className="flex justify-between text-xs text-slate-400 font-mono">
                <span>Progress</span>
                <span>{activeTask.current_step_index} of {activeTask.total_steps} steps</span>
              </div>
              <div className="w-full h-2 rounded-full bg-white/5 overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-cyan-500 to-indigo-500 transition-all duration-500"
                  style={{
                    width: `${Math.min(100, (activeTask.current_step_index / (activeTask.total_steps || 1)) * 100)}%`,
                  }}
                />
              </div>
            </div>
          </div>

          {/* Steps Timeline */}
          <div className="space-y-3">
            <h4 className="text-xs font-mono text-slate-400 uppercase tracking-wider px-1">Planned Step Execution</h4>
            <div className="space-y-2.5">
              {activeTask.steps.map((step, idx) => {
                const isCompleted = step.status === 'completed';
                const isRunning = step.status === 'running';
                const isFailed = step.status === 'failed';

                return (
                  <div
                    key={idx}
                    className={`p-4 rounded-xl glass-card flex items-start gap-3.5 transition-all ${
                      isRunning
                        ? 'border-cyan-500/50 bg-cyan-500/5 shadow-md shadow-cyan-500/10'
                        : isCompleted
                        ? 'border-emerald-500/30'
                        : 'border-white/5'
                    }`}
                  >
                    {/* Status Icon */}
                    <div className="mt-0.5 shrink-0">
                      {isCompleted && <CheckCircle2 className="w-4 h-4 text-emerald-400" />}
                      {isRunning && <Clock className="w-4 h-4 text-cyan-400 animate-spin" />}
                      {isFailed && <AlertTriangle className="w-4 h-4 text-rose-400" />}
                      {step.status === 'pending' && <Circle className="w-4 h-4 text-slate-600" />}
                    </div>

                    {/* Step Description */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <p className="text-xs font-semibold text-slate-200 truncate">{step.description}</p>
                        <span className="text-[10px] font-mono text-slate-500 ml-2">{step.capability_name}</span>
                      </div>
                      {step.error && <p className="text-[11px] text-rose-400 mt-1">{step.error}</p>}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
