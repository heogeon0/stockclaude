interface ErrorNoticeProps {
  error: unknown;
  title?: string;
}

export const ErrorNotice = ({ error, title = "요청 실패" }: ErrorNoticeProps) => {
  const message = error instanceof Error ? error.message : String(error);
  return (
    <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3">
      <p className="text-sm font-medium text-red-800">{title}</p>
      <p className="mt-1 text-xs text-red-600">{message}</p>
    </div>
  );
};
