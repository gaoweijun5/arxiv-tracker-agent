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
    <div className="flex h-screen overflow-hidden">
      {/* Background gradient orbs for depth */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-[-20%] left-[-10%] w-[500px] h-[500px] bg-purple-500/30 rounded-full blur-[100px]" />
        <div className="absolute bottom-[-20%] right-[-10%] w-[600px] h-[600px] bg-blue-500/30 rounded-full blur-[100px]" />
        <div className="absolute top-[40%] left-[50%] w-[400px] h-[400px] bg-indigo-500/20 rounded-full blur-[80px]" />
      </div>

      {/* Sidebar */}
      <aside className="w-56 glass-card m-4 mr-0 flex flex-col z-10">
        {/* Logo */}
        <div className="h-16 flex items-center gap-2.5 px-5">
          <div className="w-8 h-8 rounded-xl bg-white/20 flex items-center justify-center">
            <BookOpen className="w-4 h-4 text-white" />
          </div>
          <span className="font-bold text-white text-sm" style={{ fontFamily: 'Outfit, sans-serif' }}>
            ArXiv Tracker
          </span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-2 px-3">
          {navigation.map((item, index) => {
            const isActive = item.href === '/'
              ? location.pathname === item.href
              : location.pathname.startsWith(item.href)
            return (
              <Link
                key={item.name}
                to={item.href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-2xl text-sm mb-1 transition-all duration-300 ${
                  isActive
                    ? 'bg-white/20 text-white font-medium shadow-lg shadow-purple-500/20'
                    : 'text-white/70 hover:bg-white/10 hover:text-white'
                }`}
                style={{ animationDelay: `${index * 50}ms` }}
              >
                <item.icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-white/50'}`} />
                {item.name}
              </Link>
            )
          })}
        </nav>

        {/* Footer */}
        <div className="p-4">
          <p className="text-xs text-white/40">v0.1.0</p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto p-4">
        <div className="max-w-6xl mx-auto">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
