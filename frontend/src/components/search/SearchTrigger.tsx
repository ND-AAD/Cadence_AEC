interface SearchTriggerProps {
  onFocus: () => void;
}

export function SearchTrigger({ onFocus }: SearchTriggerProps) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onFocus}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onFocus(); }}
      className="flex items-center gap-2 px-2 py-1 text-xs text-trace border border-rule
                 hover:border-ink/30 hover:text-graphite transition-colors cursor-pointer
                 select-none shrink-0"
    >
      {/* Magnifying glass icon */}
      <svg className="w-3 h-3" viewBox="0 0 14 14" fill="none">
        <circle cx="6" cy="6" r="4.5" stroke="currentColor" strokeWidth="1.5" />
        <path d="M9.5 9.5L12.5 12.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
      <span>Search items…</span>
      <kbd className="text-[10px] text-trace/60 font-mono">⌘K</kbd>
    </div>
  );
}
