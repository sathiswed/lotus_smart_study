export function Notice({kind="info", children}:{kind?:"info"|"error"|"success";children:React.ReactNode}) { return <div className={`notice ${kind}`} role={kind === "error" ? "alert" : "status"}>{children}</div>; }
export function Spinner({label="Loading..."}:{label?:string}) { return <div className="loading-state" aria-live="polite"><span className="spinner" aria-hidden="true" />{label}</div>; }
export function Empty({children}:{children:React.ReactNode}) { return <div className="empty">{children}</div>; }
export function Pill({children}:{children:React.ReactNode}) { const value = typeof children === "string" ? children.toLowerCase().replaceAll(" ", "_") : "default"; return <span className={`pill pill-${value}`}>{children}</span>; }
export function MetricCard({label, value, icon, positive=false}:{label:string;value:React.ReactNode;icon:"tests"|"publish"|"submit"|"review"|"available"|"result";positive?:boolean}) {
  const paths = {
    tests: <><path d="M7 3h10v4H7zM5 5H4v16h16V5h-1M8 12h8M8 16h5" /></>,
    publish: <><path d="M12 16V4M8 8l4-4 4 4M5 13v7h14v-7" /></>,
    submit: <><path d="M4 5h16v14H4zM8 10l2.5 2.5L16 7" /></>,
    review: <><circle cx="10" cy="10" r="6" /><path d="m14.5 14.5 5 5M8 10l1.5 1.5L12.5 8" /></>,
    available: <><path d="M5 4h14v16H5zM8 8h8M8 12h8M8 16h5" /></>,
    result: <><path d="M5 20V10h4v10M10 20V4h4v16M15 20v-7h4v7" /></>,
  };
  return <div className={`card kpi${positive ? " kpi-positive" : ""}`}><span className="kpi-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[icon]}</svg></span><span className="kpi-label">{label}</span><strong>{value}</strong></div>;
}
