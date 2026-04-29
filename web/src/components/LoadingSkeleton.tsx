interface LoadingSkeletonProps {
  rows?: number;
  className?: string;
}

export const LoadingSkeleton = ({
  rows = 3,
  className,
}: LoadingSkeletonProps) => (
  <div className={`space-y-2 ${className ?? ""}`}>
    {Array.from({ length: rows }).map((_, i) => (
      <div
        key={i}
        className="h-4 animate-pulse rounded bg-gray-200"
        style={{ width: `${100 - i * 8}%` }}
      />
    ))}
  </div>
);
