"use client";
import { RoleGate } from "@/components/AuthProvider"; import { AppShell } from "@/components/AppShell";
export default function TeacherLayout({children}:{children:React.ReactNode}){return <RoleGate role="teacher"><AppShell role="teacher">{children}</AppShell></RoleGate>}
