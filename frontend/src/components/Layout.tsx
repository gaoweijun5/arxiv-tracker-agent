import { Outlet, Link, useLocation } from 'react-router-dom'
import {
  Home,
  FileText,
  Sparkles,
  Heart,
  Settings,
  BookOpen,
} from 'lucide-react'

const navigation = [
  { name: 'Dashboard', href: '/', icon: Home },
  { name: 'Papers', href: '/papers', icon: FileText },
  { name: 'Recommendations', href: '/recommendations', icon: Sparkles },
  { name: 'Interests', href: '/interests', icon: Heart },
  { name: 'Settings', href: '/settings', icon: Settings },
]

export default function Layout() {
  const location = useLocation()

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className="w-56 bg-white border-r border-gray-200 flex flex-col">
        {/* Logo */}
        <div className="h-14 flex items-center gap-2.5 px-4 border-b border-gray-200">
          <BookOpen className="w-5 h-5 text-gray-900" />
          <span className="font-semibold text-gray-900">ArXiv Tracker</span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-3 px-2">
          {navigation.map((item) => {
            const isActive = location.pathname === item.href
            return (
              <Link
                key={item.name}
                to={item.href}
                className={`flex items-center gap-2.5 px-3 py-2 rounded-md text-sm mb-0.5 ${
                  isActive
                    ? 'bg-gray-100 text-gray-900 font-medium'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`}
              >
                <item.icon className={`w-4 h-4 ${isActive ? 'text-gray-900' : 'text-gray-400'}`} />
                {item.name}
              </Link>
            )
          })}
        </nav>

        {/* Footer */}
        <div className="p-3 border-t border-gray-200">
          <p className="text-xs text-gray-400">v0.1.0</p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <div className="max-w-6xl mx-auto px-6 py-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
