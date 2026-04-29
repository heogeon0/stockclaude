interface EmptyStateProps {
  title?: string;
  description?: string;
}

export const EmptyState = ({
  title = "데이터 없음",
  description,
}: EmptyStateProps) => (
  <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-gray-200 bg-white px-6 py-12 text-center">
    <p className="text-sm font-medium text-gray-700">{title}</p>
    {description && (
      <p className="mt-1 text-xs text-gray-500">{description}</p>
    )}
  </div>
);
