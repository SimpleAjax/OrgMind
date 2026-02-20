import Link from "next/link";
import {
    LayoutDashboard,
    Search,
    MessageSquare,
    Network,
    Settings
} from "lucide-react";

const navItems = [
    { name: "Dashboard", href: "/", icon: LayoutDashboard },
    { name: "Object Explorer", href: "/objects", icon: Search },
    { name: "Agent Chat", href: "/chat", icon: MessageSquare },
    { name: "Rules", href: "/rules", icon: Network },
    { name: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
    return (
        <div className="flex flex-col w-64 border-r bg-muted/40 p-4 h-full">
            <div className="flex h-12 items-center px-4 mb-4">
                <h1 className="text-xl font-bold">OrgMind</h1>
            </div>
            <nav className="flex-1 space-y-2">
                {navItems.map((item) => (
                    <Link 
                        key={item.href} 
                        href={item.href}
                        className="flex items-center gap-2 w-full px-4 py-2 text-sm font-medium rounded-md hover:bg-accent hover:text-accent-foreground transition-colors"
                    >
                        <item.icon className="w-5 h-5" />
                        {item.name}
                    </Link>
                ))}
            </nav>
        </div>
    );
}
