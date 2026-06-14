import { useState } from 'react';
import { TrashIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline';
import { api } from '../api/client';
import { useDemoStore } from '../stores/demoStore';

export default function ClearDataButton() {
  const clearAll = useDemoStore((s) => s.clearAll);
  const [confirming, setConfirming] = useState(false);
  const [cleared, setCleared] = useState(false);

  const handleClear = async () => {
    clearAll();
    try {
      // 前端清空数据时,同步清空 Agent 固定工作目录,避免下次对话读到旧 case。
      await api.agent.clearWorkspace();
    } catch (err) {
      console.error('Failed to clear agent workspace:', err);
    }
    setCleared(true);
    setTimeout(() => {
      setConfirming(false);
      setCleared(false);
    }, 1500);
  };

  if (confirming) {
    return (
      <div className="flex items-center gap-2 p-2 rounded-lg border border-error/30 bg-error-muted">
        <ExclamationTriangleIcon className="w-5 h-5 text-error shrink-0" />
        <p className="text-xs text-error flex-1">
          清空所有 demo 数据 + Agent 上传数据？此操作不可撤销。
        </p>
        <button
          onClick={handleClear}
          className="btn btn-sm bg-error text-white hover:bg-error/90"
          disabled={cleared}
        >
          {cleared ? '已清空' : '确认清空'}
        </button>
        <button
          onClick={() => setConfirming(false)}
          className="btn btn-sm btn-ghost"
          disabled={cleared}
        >
          取消
        </button>
      </div>
    );
  }

  return (
    <button
      onClick={() => setConfirming(true)}
      className="btn btn-ghost text-fg-dim hover:text-error"
      title="清空当前 demo 数据"
    >
      <TrashIcon className="w-4 h-4" />
      清空数据
    </button>
  );
}
