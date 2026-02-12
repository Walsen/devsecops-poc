import { Outlet, Link } from 'react-router-dom';
import { Award, Home, Send } from 'lucide-react';

export function Layout() {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-[#232f3e] text-white shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <Link to="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
              <Award className="h-8 w-8 text-[#ff9900]" />
              <span className="font-bold text-xl">AWS Certification Announcer</span>
            </Link>
            <nav className="flex items-center gap-4">
              <Link
                to="/"
                className="flex items-center gap-1 px-3 py-2 rounded-md hover:bg-white/10 transition-colors"
              >
                <Home className="h-4 w-4" />
                <span>Home</span>
              </Link>
              <Link
                to="/publish"
                className="flex items-center gap-1 px-3 py-2 rounded-md hover:bg-white/10 transition-colors"
              >
                <Send className="h-4 w-4" />
                <span>Publish</span>
              </Link>
            </nav>
          </div>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>
      <footer className="bg-[#232f3e] text-gray-400 py-6 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center text-sm">
          <p>AWS Community Certification Announcer</p>
        </div>
      </footer>
    </div>
  );
}
