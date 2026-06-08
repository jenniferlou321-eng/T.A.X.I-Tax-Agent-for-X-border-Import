import { CheckCircle2, FileText } from "lucide-react";

export interface HMRCReceipt {
  processingDate?: string;
  formBundleNumber?: string;
  paymentIndicator?: string;
  chargeRefNumber?: string;
}

interface HMRCReceiptCardProps {
  receipt: HMRCReceipt;
}

export function HMRCReceiptCard({ receipt }: HMRCReceiptCardProps) {
  const fields: { label: string; value?: string }[] = [
    { label: "处理时间", value: receipt.processingDate },
    { label: "Form Bundle Number", value: receipt.formBundleNumber },
    { label: "付款方式", value: receipt.paymentIndicator },
    { label: "Charge Reference", value: receipt.chargeRefNumber },
  ];

  const visibleFields = fields.filter((f) => f.value);

  if (visibleFields.length === 0) {
    return null;
  }

  return (
    <div className="rounded-lg border border-green-200 bg-green-50 p-4">
      <div className="mb-3 flex items-center gap-2">
        <CheckCircle2 className="h-5 w-5 text-green-600" />
        <span className="font-semibold text-green-800">HMRC 受理成功</span>
      </div>

      <div className="space-y-2">
        {visibleFields.map(({ label, value }) => (
          <div key={label} className="flex items-center justify-between">
            <span className="text-sm text-gray-600">{label}</span>
            <span className="font-mono text-sm text-gray-900">{value}</span>
          </div>
        ))}
      </div>

      <div className="mt-3 flex items-center gap-2 border-t border-green-200 pt-3">
        <FileText className="h-4 w-4 text-green-600" />
        <span className="text-sm text-green-700">数据已同步至 HMRC 沙盒</span>
      </div>
    </div>
  );
}
