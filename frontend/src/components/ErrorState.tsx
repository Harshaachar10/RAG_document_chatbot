export function ErrorState({
  title = 'Something went wrong',
  message,
  onRetry,
}: {
  title?: string;
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="rounded-[12px] border border-rose-200 bg-rose-50 px-6 py-8" role="alert">
      <h3 className="text-base font-semibold text-rose-900">{title}</h3>
      <p className="mt-2 text-sm text-rose-800">{message || 'The API request failed.'}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-4 rounded-md bg-primary px-3 py-2 text-sm font-medium text-white hover:bg-accent"
        >
          Retry
        </button>
      ) : null}
    </div>
  );
}
