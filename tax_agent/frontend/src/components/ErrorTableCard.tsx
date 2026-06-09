import { ExclamationTriangleIcon } from '@heroicons/react/24/outline';

interface ErrorTableCardProps {
  errorCode: string;
  errorMessage: string;
  tool: string;
  timestamp: string;
  suggestions: string[];
}

export default function ErrorTableCard({
  errorCode, errorMessage, tool, timestamp, suggestions,
}: ErrorTableCardProps) {
  return (
    <div className="my-2 border border-error/30 rounded-lg overflow-hidden">
      <div className="bg-error-muted px-4 py-2 flex items-center gap-2">
        <ExclamationTriangleIcon className="w-5 h-5 text-error" />
        <p className="font-medium text-error">❌ 出错</p>
      </div>
      <table className="w-full text-sm">
        <tbody>
          <tr className="border-t border-error/10">
            <td className="px-4 py-2 text-fg-dim w-1/4">错误码</td>
            <td className="px-4 py-2 font-mono text-fg">{errorCode}</td>
          </tr>
          <tr className="border-t border-error/10">
            <td className="px-4 py-2 text-fg-dim">错误信息</td>
            <td className="px-4 py-2 text-fg">{errorMessage}</td>
          </tr>
          <tr className="border-t border-error/10">
            <td className="px-4 py-2 text-fg-dim">工具</td>
            <td className="px-4 py-2 font-mono text-fg">{tool}</td>
          </tr>
          <tr className="border-t border-error/10">
            <td className="px-4 py-2 text-fg-dim">时间</td>
            <td className="px-4 py-2 font-mono text-fg-dim">{timestamp}</td>
          </tr>
        </tbody>
      </table>
      {suggestions.length > 0 && (
        <div className="px-4 py-2 border-t border-error/10 bg-bg-elevated">
          <p className="text-xs text-fg-dim mb-1">💡 建议操作</p>
          <ul className="text-sm text-fg space-y-1">
            {suggestions.map((s, i) => (
              <li key={i}>• {s}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
