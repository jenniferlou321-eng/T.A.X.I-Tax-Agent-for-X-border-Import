import type { ReactNode } from 'react';

interface QuickActionButtonProps {
  icon: ReactNode;
  label: string;
  onClick: () => void;
  variant?: 'primary' | 'secondary';
  disabled?: boolean;
}

export default function QuickActionButton({
  icon, label, onClick, variant = 'secondary', disabled = false,
}: QuickActionButtonProps) {
  const baseClass = 'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors';
  const variantClass = variant === 'primary'
    ? 'bg-accent text-white hover:bg-accent/90'
    : 'bg-bg-elevated text-fg hover:bg-bg-elevated/80 border border-fg-dim/20';

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`${baseClass} ${variantClass} ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
    >
      {icon}
      {label}
    </button>
  );
}
