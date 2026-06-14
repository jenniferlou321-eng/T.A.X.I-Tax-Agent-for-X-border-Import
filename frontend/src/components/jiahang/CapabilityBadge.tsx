// 三态平台能力徽章(supported / partial / not_supported / no_action)
import { CheckCircleIcon, ExclamationTriangleIcon, XCircleIcon, MinusCircleIcon } from '@heroicons/react/24/outline'

export type CapabilityStatus = 'supported' | 'partial' | 'not_supported' | 'no_action_required'

const config: Record<
  CapabilityStatus,
  { label: string; classes: string; Icon: React.ElementType }
> = {
  supported: {
    label: '已支持',
    classes: 'bg-success-muted text-success border-success/30',
    Icon: CheckCircleIcon,
  },
  partial: {
    label: '部分支持',
    classes: 'bg-warning-muted text-warning border-warning/30',
    Icon: ExclamationTriangleIcon,
  },
  not_supported: {
    label: '待实现',
    classes: 'bg-error-muted text-error border-error/30',
    Icon: XCircleIcon,
  },
  no_action_required: {
    label: '不需申报',
    classes: 'bg-bg-elevated text-fg-dim border-border',
    Icon: MinusCircleIcon,
  },
}

interface CapabilityBadgeProps {
  status: string | null | undefined
  size?: 'sm' | 'md'
}

export default function CapabilityBadge({ status, size = 'sm' }: CapabilityBadgeProps) {
  if (!status) {
    return (
      <span className="text-fg-dim text-xs">—</span>
    )
  }
  const cfg = config[status as CapabilityStatus]
  if (!cfg) {
    return <span className="text-fg-dim text-xs">{status}</span>
  }
  const { label, classes, Icon } = cfg
  const iconClass = size === 'md' ? 'w-4 h-4' : 'w-3 h-3'
  const textClass = size === 'md' ? 'text-xs' : 'text-[11px]'
  return (
    <span
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border ${classes} ${textClass} font-medium`}
      title={`平台能力: ${label}`}
    >
      <Icon className={iconClass} />
      {label}
    </span>
  )
}
