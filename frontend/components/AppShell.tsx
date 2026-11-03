"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "./AuthProvider";

type IconName = "dashboard" | "spark" | "check" | "users" | "books" | "lock" | "history";
type NavItem = { href: string; label: string; icon: IconName };

const nav: Record<"teacher" | "student", readonly NavItem[]> = {
  teacher: [
    { href: "/teacher", label: "Dashboard", icon: "dashboard" },
    { href: "/teacher/generate", label: "Question & Test Generation", icon: "spark" },
    { href: "/teacher/textbooks", label: "Textbooks", icon: "books" },
    { href: "/teacher/tests", label: "Tests", icon: "check" },
    { href: "/teacher/evaluations", label: "Evaluations", icon: "check" },
    { href: "/teacher/history", label: "Test History", icon: "history" },
    { href: "/teacher/students", label: "Students", icon: "users" },
  ],
  student: [
    { href: "/student", label: "Dashboard", icon: "dashboard" },
    { href: "/student/history", label: "My Test History", icon: "history" },
    { href: "/student/change-password", label: "Change password", icon: "lock" },
  ],
};

function NavIcon({ name }: { name: IconName }) {
  const paths: Record<IconName, React.ReactNode> = {
    dashboard: <><path d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z" /></>,
    spark: <><path d="m12 3 1.4 4.1L17.5 8.5l-4.1 1.4L12 14l-1.4-4.1-4.1-1.4 4.1-1.4L12 3Z" /><path d="m18.5 14 .8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8.8-2.2Z" /></>,
    check: <><path d="M5 12.5 9.2 17 19 7" /><path d="M4 4h16v16H4z" /></>,
    users: <><path d="M16 20v-1.5c0-2.5-2.2-4.5-5-4.5s-5 2-5 4.5V20" /><circle cx="11" cy="8" r="3" /><path d="M16 5.2a3 3 0 0 1 0 5.6M18 14.5c1.5.8 2.5 2.2 2.5 4V20" /></>,
    lock: <><rect x="5" y="10" width="14" height="10" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v2" /></>,
    books: <><path d="M4 5.5A3.5 3.5 0 0 1 7.5 2H12v18H7.5A3.5 3.5 0 0 0 4 23V5.5ZM20 5.5A3.5 3.5 0 0 0 16.5 2H12v18h4.5A3.5 3.5 0 0 1 20 23V5.5Z" /></>,
    history: <><path d="M4 12a8 8 0 1 0 2.3-5.7L4 8.5" /><path d="M4 4v4.5h4.5M12 7v5l3 2" /></>,
  };
  return <svg className="nav-icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}

function isActive(pathname: string, href: string) {
  if (href === "/teacher" || href === "/student") return pathname === href;
  if (href === "/teacher/generate") return pathname.startsWith("/teacher/generate") || pathname.startsWith("/teacher/batches");
  return pathname.startsWith(href);
}

export function AppShell({ role, children }: { role: "teacher" | "student"; children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const passwordChangeRequired = role === "student" && Boolean(user?.must_change_password);
  const links = passwordChangeRequired ? nav.student.filter(item => item.href === "/student/change-password") : nav[role];
  const brandHref = passwordChangeRequired ? "/student/change-password" : `/${role}`;

  return <div className="app-shell">
    <header className="topbar">
      <Link className="brand" href={brandHref} aria-label="Lotus Smart Study dashboard">
        <Image src="/lotus_logo_new.png" alt="Lotus Smart Study" width={150} height={100} className="brand-logo" priority />
      </Link>
      <div className="account-menu">
        <span className="account-avatar" aria-hidden="true">{user?.name?.charAt(0).toUpperCase()}</span>
        <span className="account-copy"><strong>{user?.name}</strong><small>{role === "teacher" ? "Teacher workspace" : "Student workspace"}</small></span>
        <button className="link-button" onClick={() => void logout()}>Log out</button>
      </div>
    </header>
    <nav className="nav-tabs" aria-label={`${role} navigation`}>
      <p className="nav-label">Workspace</p>
      {links.map(item => <Link key={item.href} className={isActive(pathname, item.href) ? "active" : ""} href={item.href}><NavIcon name={item.icon} /><span>{item.label}</span></Link>)}
      <div className="nav-footer"><strong>Curriculum-grounded learning</strong><span>Classes 8-12</span></div>
    </nav>
    <main className="page">{children}</main>
  </div>;
}
