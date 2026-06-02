import { Outlet, Link, useLocation } from 'react-router-dom'
import {
  Home,
  FileText,
  Sparkles,
  Heart,
  Settings,
  BookOpen,
  Newspaper,
} from 'lucide-react'

const navigation = [
  { name: 'Dashboard', href: '/', icon: Home },
  { name: 'Papers', href: '/papers', icon: FileText },
  { name: 'Recommendations', href: '/recommendations', icon: Sparkles },
  { name: 'Reports', href: '/reports', icon: Newspaper },
  { name: 'Interests', href: '/interests', icon: Heart },
  { name: 'Settings', href: '/settings', icon: Settings },
]

export default function Layout() {
  const location = useLocation()

  return (
    <div className="flex h-screen bg-white">
      {/* Sidebar */}
      <aside className="w-56 bg-white shadow-[0_4px_12px_rgba(0,0,0,0.08)] flex flex-col">
        {/* Logo */}
        <div className="h-14 flex items-center gap-2.5 px-4">
          <BookOpen className="w-5 h-5 text-[#1A1A1A]" />
          <span className="font-semibold text-[#1A1A1A]">ArXiv Tracker</span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-3 px-2">
          {navigation.map((item) => {
            const isActive = item.href === '/'
              ? location.pathname === item.href
              : location.pathname.startsWith(item.href)
            return (
              <Link
                key={item.name}
                to={item.href}
                className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm mb-0.5 transition-all duration-300 ${
                  isActive
                    ? 'bg-gray-50 text-[#1A1A1A] font-medium'
                    : 'text-gray-500 hover:bg-gray-50 hover:text-[#1A1A1A]'
                }`}
              >
                <item.icon className={`w-4 h-4 ${isActive ? 'text-[#1A1A1A]' : 'text-gray-400'}`} />
                {item.name}
              </Link>
            )
          })}
        </nav>

        {/* Footer */}
        <div className="p-3">
          <p className="text-xs text-gray-400">v0.1.0</p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <div className="max-w-6xl mx-auto px-16 py-12 fade-in">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
