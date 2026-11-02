"use client";
import { RoleGate } from "@/components/AuthProvider"; import { AppShell } from "@/components/AppShell";
export default function StudentLayout({children}:{children:React.ReactNode}){return <RoleGate role="student"><AppShell role="student">{children}</AppShell></RoleGate>}
